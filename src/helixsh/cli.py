"""helixsh CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from helixsh.nextflow import (
    HelixshError,
    RunConfig,
    build_nextflow_run_command,
    format_shell_command,
    normalize_pipeline,
    validate_input_file,
    validate_runtime,
)

AUDIT_FILE = Path(".helixsh_audit.jsonl")


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    command: str
    strict: bool
    mode: str


def write_audit(event: AuditEvent) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="helixsh")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode.")

    subparsers = parser.add_subparsers(dest="command", required=False)

    run_parser = subparsers.add_parser("run", help="Run an nf-core pipeline via Nextflow.")
    run_parser.add_argument("target", nargs="?", default="nf-core")
    run_parser.add_argument("pipeline", nargs="?", default="rnaseq")
    run_parser.add_argument("--org", default="nf-core")
    run_parser.add_argument("--runtime", default="docker")
    run_parser.add_argument("--input", dest="input_file")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--execute", action="store_true", help="Actually execute Nextflow.")
    run_parser.add_argument(
        "--nf-arg",
        action="append",
        default=[],
        help="Extra argument passed directly to Nextflow (repeatable).",
    )

    subparsers.add_parser("doctor", help="Show environment diagnostics.")

    explain_parser = subparsers.add_parser("explain", help="Explain latest command plan.")
    explain_parser.add_argument("scope", nargs="?", default="last")

    subparsers.add_parser("plan", help="Display planning guidance.")
    return parser


def cmd_run(args: argparse.Namespace, strict: bool) -> int:
    if args.target != "nf-core":
        raise HelixshError("Only 'nf-core' target is currently supported in this phase.")

    runtime = validate_runtime(args.runtime)
    input_file = validate_input_file(args.input_file)
    pipeline = normalize_pipeline(args.org, args.pipeline)

    cfg = RunConfig(
        pipeline=pipeline,
        profile=runtime,
        input_file=input_file,
        resume=args.resume,
        extra_args=tuple(args.nf_arg),
    )
    command = build_nextflow_run_command(cfg)
    rendered = format_shell_command(command)

    write_audit(
        AuditEvent(
            timestamp=datetime.now(UTC).isoformat(),
            command=rendered,
            strict=strict,
            mode="run",
        )
    )

    print(f"[helixsh] planned: {rendered}")
    print("[helixsh] execution boundary: POSIX shell / Nextflow")

    if strict and not args.execute:
        print("[helixsh] strict mode active: no execution without --execute")
        return 0

    if args.execute:
        completed = subprocess.run(command, check=False)
        return completed.returncode

    print("[helixsh] dry-run complete (use --execute to run).")
    return 0


def cmd_doctor() -> int:
    checks = [
        ("nextflow", ["nextflow", "-version"]),
        ("docker", ["docker", "--version"]),
        ("podman", ["podman", "--version"]),
        ("singularity", ["singularity", "--version"]),
        ("apptainer", ["apptainer", "--version"]),
    ]

    for name, command in checks:
        result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        state = "ok" if result.returncode == 0 else "missing"
        details = (result.stdout.strip() or result.stderr.strip() or "not available").splitlines()[0]
        print(f"{name:11} {state:7} {details}")
    return 0


def cmd_explain(scope: str) -> int:
    if scope != "last":
        raise HelixshError("Only 'last' explanation scope is currently supported.")
    if not AUDIT_FILE.exists():
        print("No previous helixsh audit events found.")
        return 0

    last_line = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()[-1]
    event = json.loads(last_line)
    print("Last planned command:")
    print(f"- timestamp: {event['timestamp']}")
    print(f"- strict:    {event['strict']}")
    print(f"- mode:      {event['mode']}")
    print(f"- command:   {event['command']}")
    return 0


def cmd_plan() -> int:
    print("helixsh production plan (Phase 1)")
    print("1. Validate nf-core inputs and runtime selection")
    print("2. Build deterministic Nextflow command")
    print("3. Write audit log entry")
    print("4. Optionally execute through POSIX boundary")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)

    strict = bool(getattr(args, "strict", False))

    try:
        if args.command == "run":
            return cmd_run(args, strict=strict)
        if args.command == "doctor":
            return cmd_doctor()
        if args.command == "explain":
            return cmd_explain(args.scope)
        if args.command == "plan":
            return cmd_plan()

        parser.print_help()
        return 0
    except HelixshError as exc:
        print(f"helixsh error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
