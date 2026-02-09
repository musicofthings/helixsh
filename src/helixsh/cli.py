"""helixsh CLI entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from helixsh.doctor import collect_doctor_results
from helixsh.intent import intent_to_nf_args, parse_intent
from helixsh.mcp import evaluate_capability
from helixsh.nextflow import (
    HelixshError,
    RunConfig,
    build_nextflow_run_command,
    format_shell_command,
    normalize_pipeline,
    validate_input_file,
    validate_runtime,
)
from helixsh.schema import load_json, validate_params
from helixsh.workflow import container_violations, parse_process_nodes
from helixsh.diagnostics import diagnose_failure
from helixsh.cache import summarize_cache

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
    run_parser.add_argument("--yes", action="store_true", help="Confirm execution in strict mode.")
    run_parser.add_argument("--nf-arg", action="append", default=[], help="Extra argument passed directly to Nextflow (repeatable).")

    subparsers.add_parser("doctor", help="Show environment diagnostics.")

    explain_parser = subparsers.add_parser("explain", help="Explain latest command plan.")
    explain_parser.add_argument("scope", nargs="?", default="last")

    subparsers.add_parser("plan", help="Display planning guidance.")

    intent_parser = subparsers.add_parser("intent", help="Map natural language intent to Nextflow plan.")
    intent_parser.add_argument("text")

    schema_parser = subparsers.add_parser("validate-schema", help="Validate params against nf-core style schema JSON.")
    schema_parser.add_argument("--schema", required=True)
    schema_parser.add_argument("--params", required=True)

    mcp_parser = subparsers.add_parser("mcp-check", help="Check MCP gateway capability policy.")
    mcp_parser.add_argument("capability")

    export_parser = subparsers.add_parser("audit-export", help="Export audit log with reproducible hash.")
    export_parser.add_argument("--out", required=True)

    wf_parser = subparsers.add_parser("parse-workflow", help="Parse Nextflow process blocks and check container policy.")
    wf_parser.add_argument("--file", required=True)

    diag_parser = subparsers.add_parser("diagnose", help="Diagnose failed process by exit code.")
    diag_parser.add_argument("--process", required=True)
    diag_parser.add_argument("--exit-code", required=True, type=int)
    diag_parser.add_argument("--memory-gb", type=int)

    cache_parser = subparsers.add_parser("cache-report", help="Summarize cache/resume efficiency.")
    cache_parser.add_argument("--total", required=True, type=int)
    cache_parser.add_argument("--cached", required=True, type=int)
    cache_parser.add_argument("--invalidated", action="append", default=[])

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

    write_audit(AuditEvent(timestamp=datetime.now(UTC).isoformat(), command=rendered, strict=strict, mode="run"))

    print(f"[helixsh] planned: {rendered}")
    print("[helixsh] execution boundary: POSIX shell / Nextflow")

    if strict and not args.execute:
        print("[helixsh] strict mode active: no execution without --execute")
        return 0
    if strict and args.execute and not args.yes:
        print("[helixsh] strict mode requires explicit confirmation via --yes")
        return 2
    if args.execute:
        completed = subprocess.run(command, check=False)
        return completed.returncode

    print("[helixsh] dry-run complete (use --execute to run).")
    return 0


def cmd_doctor() -> int:
    for result in collect_doctor_results():
        print(f"{result.name:11} {result.state:7} {result.details}")
    return 0


def cmd_explain(scope: str) -> int:
    if scope != "last":
        raise HelixshError("Only 'last' explanation scope is currently supported.")
    if not AUDIT_FILE.exists():
        print("No previous helixsh audit events found.")
        return 0

    lines = [line for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        print("No previous helixsh audit events found.")
        return 0

    event = json.loads(lines[-1])
    print("Last planned command:")
    print(f"- timestamp: {event['timestamp']}")
    print(f"- strict:    {event['strict']}")
    print(f"- mode:      {event['mode']}")
    print(f"- command:   {event['command']}")
    return 0


def cmd_plan() -> int:
    print("helixsh production plan")
    print("Phase 1: foundation (implemented)")
    print("Phase 2: AI planning + MCP gateway scaffolding (in progress)")
    print("Phase 3: bioinformatics intelligence profiles (in progress)")
    print("Phase 4: enterprise hardening export hooks (in progress)")
    return 0


def cmd_intent(text: str) -> int:
    intent = parse_intent(text)
    payload = {
        "pipeline": intent.pipeline,
        "runtime": intent.runtime,
        "resume": intent.resume,
        "low_memory_mode": intent.low_memory_mode,
        "sample_model": intent.sample_model,
        "suggested_nf_args": intent_to_nf_args(intent),
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_validate_schema(schema_path: str, params_path: str) -> int:
    schema = load_json(schema_path)
    params = load_json(params_path)
    result = validate_params(schema, params)
    if result.ok:
        print("schema validation: ok")
        return 0
    print("schema validation: failed")
    for issue in result.issues:
        print(f"- {issue.field}: {issue.message}")
    return 2


def cmd_mcp_check(capability: str) -> int:
    decision = evaluate_capability(capability)
    print(json.dumps(asdict(decision), indent=2))
    return 0 if decision.allowed else 2


def cmd_audit_export(out_path: str) -> int:
    content = AUDIT_FILE.read_text(encoding="utf-8") if AUDIT_FILE.exists() else ""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    payload = {
        "exported_at": datetime.now(UTC).isoformat(),
        "audit_sha256": digest,
        "line_count": len([x for x in content.splitlines() if x.strip()]),
        "audit_file": str(AUDIT_FILE),
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"audit export written: {out}")
    return 0


def cmd_parse_workflow(file_path: str) -> int:
    text = Path(file_path).read_text(encoding="utf-8")
    nodes = parse_process_nodes(text)
    violations = container_violations(nodes)
    payload = {
        "processes": [asdict(n) for n in nodes],
        "container_policy_ok": len(violations) == 0,
        "violations": violations,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not violations else 2


def cmd_diagnose(process: str, exit_code: int, memory_gb: int | None) -> int:
    result = diagnose_failure(process, exit_code, memory_gb)
    print(json.dumps(asdict(result), indent=2))
    return 0 if exit_code == 0 else 2


def cmd_cache_report(total: int, cached: int, invalidated: list[str]) -> int:
    report = summarize_cache(total, cached, invalidated)
    print(json.dumps(asdict(report), indent=2))
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
        if args.command == "intent":
            return cmd_intent(args.text)
        if args.command == "validate-schema":
            return cmd_validate_schema(args.schema, args.params)
        if args.command == "mcp-check":
            return cmd_mcp_check(args.capability)
        if args.command == "audit-export":
            return cmd_audit_export(args.out)
        if args.command == "parse-workflow":
            return cmd_parse_workflow(args.file)
        if args.command == "diagnose":
            return cmd_diagnose(args.process, args.exit_code, args.memory_gb)
        if args.command == "cache-report":
            return cmd_cache_report(args.total, args.cached, args.invalidated)

        parser.print_help()
        return 0
    except HelixshError as exc:
        print(f"helixsh error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
