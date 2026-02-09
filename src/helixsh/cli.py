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
from helixsh.rbac import check_access
from helixsh.reporting import build_validation_report, write_report
from helixsh.profiles import recommend_profile
from helixsh.provenance import make_provenance_record
from helixsh.container_policy import check_image_policy
from helixsh.context import parse_nextflow_config_defaults, summarize_samplesheet
from helixsh.offline import check_offline_readiness
from helixsh.gateway import approve_proposal, create_proposal, list_proposals
from helixsh.resources import estimate_resources
from helixsh.executor import build_posix_exec, run_posix_exec
from helixsh.roadmap import compute_roadmap_status

AUDIT_FILE = Path(".helixsh_audit.jsonl")
PROPOSAL_FILE = Path(".helixsh_proposals.jsonl")


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    command: str
    strict: bool
    mode: str
    role: str
    execution_hash: str
    provenance_params: dict


def write_audit(event: AuditEvent) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="helixsh")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode.")
    parser.add_argument("--role", default="analyst", help="Role used for RBAC authorization checks.")

    subparsers = parser.add_subparsers(dest="command", required=False)

    run_parser = subparsers.add_parser("run", help="Run an nf-core pipeline via Nextflow.")
    run_parser.add_argument("target", nargs="?", default="nf-core")
    run_parser.add_argument("pipeline", nargs="?", default="rnaseq")
    run_parser.add_argument("--org", default="nf-core")
    run_parser.add_argument("--runtime", default="docker")
    run_parser.add_argument("--input", dest="input_file")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--offline", action="store_true", help="Run Nextflow in offline mode.")
    run_parser.add_argument("--execute", action="store_true", help="Actually execute Nextflow.")
    run_parser.add_argument("--yes", action="store_true", help="Confirm execution in strict mode.")
    run_parser.add_argument("--nf-arg", action="append", default=[], help="Extra argument passed directly to Nextflow (repeatable).")

    subparsers.add_parser("doctor", help="Show environment diagnostics.")

    explain_parser = subparsers.add_parser("explain", help="Explain latest command plan.")
    explain_parser.add_argument("scope", nargs="?", default="last")

    subparsers.add_parser("plan", help="Display planning guidance.")
    subparsers.add_parser("roadmap-status", help="Show roadmap completion status.")

    intent_parser = subparsers.add_parser("intent", help="Map natural language intent to Nextflow plan.")
    intent_parser.add_argument("text")

    schema_parser = subparsers.add_parser("validate-schema", help="Validate params against nf-core style schema JSON.")
    schema_parser.add_argument("--schema", required=True)
    schema_parser.add_argument("--params", required=True)

    mcp_parser = subparsers.add_parser("mcp-check", help="Check MCP gateway capability policy.")
    mcp_parser.add_argument("capability")


    mcp_prop = subparsers.add_parser("mcp-propose", help="Store an MCP proposal for review.")
    mcp_prop.add_argument("--kind", required=True)
    mcp_prop.add_argument("--summary", required=True)
    mcp_prop.add_argument("--payload", required=True)

    subparsers.add_parser("mcp-proposals", help="List MCP proposals.")

    mcp_appr = subparsers.add_parser("mcp-approve", help="Approve an MCP proposal by id.")
    mcp_appr.add_argument("--id", required=True, type=int)

    export_parser = subparsers.add_parser("audit-export", help="Export audit log with reproducible hash.")
    export_parser.add_argument("--out", required=True)

    subparsers.add_parser("audit-verify", help="Verify audit log integrity/shape.")

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


    rbac_parser = subparsers.add_parser("rbac-check", help="Check role-based access for an action.")
    rbac_parser.add_argument("--role", required=True)
    rbac_parser.add_argument("--action", required=True)

    report_parser = subparsers.add_parser("report", help="Generate validation report artifact.")
    report_parser.add_argument("--schema-ok", action="store_true")
    report_parser.add_argument("--container-policy-ok", action="store_true")
    report_parser.add_argument("--cache-percent", type=int, default=0)
    report_parser.add_argument("--diagnostics", default="n/a")
    report_parser.add_argument("--out", required=True)


    res_parser = subparsers.add_parser("resource-estimate", help="Estimate CPU/memory for tool + assay + samples.")
    res_parser.add_argument("--tool", required=True)
    res_parser.add_argument("--assay", required=True)
    res_parser.add_argument("--samples", required=True, type=int)

    prof_parser = subparsers.add_parser("profile-suggest", help="Suggest pipeline/profile args for assay and reference.")
    prof_parser.add_argument("--assay", required=True)
    prof_parser.add_argument("--reference")
    prof_parser.add_argument("--offline", action="store_true")

    prov_parser = subparsers.add_parser("provenance", help="Generate reproducible execution hash record.")
    prov_parser.add_argument("--command", dest="plan_command", required=True)
    prov_parser.add_argument("--params", required=True, help="JSON string of parameters")

    img_parser = subparsers.add_parser("image-check", help="Check container image digest policy.")
    img_parser.add_argument("--image", required=True)


    ctx_parser = subparsers.add_parser("context-check", help="Summarize samplesheet and nextflow.config defaults.")
    ctx_parser.add_argument("--samplesheet")
    ctx_parser.add_argument("--config")

    off_parser = subparsers.add_parser("offline-check", help="Check offline cache readiness.")
    off_parser.add_argument("--cache-root", default=".helixsh_cache")



    posix_parser = subparsers.add_parser("posix-wrap", help="Render/execute explicit POSIX boundary wrapper.")
    posix_parser.add_argument("args", nargs="+", help="Command arguments to wrap")
    posix_parser.add_argument("--execute", action="store_true", help="Execute wrapped command")

    pre_parser = subparsers.add_parser("preflight", help="Run combined preflight checks before execution.")
    pre_parser.add_argument("--schema")
    pre_parser.add_argument("--params")
    pre_parser.add_argument("--workflow")
    pre_parser.add_argument("--cache-root")
    pre_parser.add_argument("--samplesheet")
    pre_parser.add_argument("--config")
    pre_parser.add_argument("--image")

    return parser


def cmd_run(args: argparse.Namespace, strict: bool, role: str) -> int:
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
        extra_args=tuple((["-offline"] if args.offline else []) + args.nf_arg),
    )
    command = build_nextflow_run_command(cfg)
    rendered = format_shell_command(command)

    provenance_params = {"pipeline": pipeline, "runtime": runtime, "resume": args.resume, "offline": args.offline}
    record = make_provenance_record(command=rendered, params=provenance_params)
    write_audit(AuditEvent(timestamp=datetime.now(UTC).isoformat(), command=rendered, strict=strict, mode="run", role=role, execution_hash=record.execution_hash, provenance_params=provenance_params))

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
    print(f"- role:      {event.get('role', 'unknown')}")
    print(f"- hash:      {event.get('execution_hash', 'n/a')}")
    print(f"- params:    {json.dumps(event.get('provenance_params', {}), sort_keys=True)}")
    print(f"- command:   {event['command']}")
    return 0


def cmd_plan() -> int:
    print("helixsh production plan")
    for phase in compute_roadmap_status():
        print(f"{phase.phase}: {phase.status}")
    return 0


def cmd_roadmap_status() -> int:
    phases = compute_roadmap_status()
    payload = []
    for p in phases:
        payload.append({
            "phase": p.phase,
            "status": p.status,
            "completed": list(p.completed),
            "pending": list(p.pending),
        })
    print(json.dumps(payload, indent=2))
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


def cmd_mcp_propose(kind: str, summary: str, payload: str) -> int:
    proposal = create_proposal(str(PROPOSAL_FILE), kind=kind, summary=summary, payload=payload)
    print(json.dumps(asdict(proposal), indent=2))
    return 0


def cmd_mcp_proposals() -> int:
    proposals = list_proposals(str(PROPOSAL_FILE))
    print(json.dumps([asdict(p) for p in proposals], indent=2))
    return 0


def cmd_mcp_approve(proposal_id: int) -> int:
    proposal = approve_proposal(str(PROPOSAL_FILE), proposal_id=proposal_id)
    print(json.dumps(asdict(proposal), indent=2))
    return 0


def cmd_resource_estimate(tool: str, assay: str, samples: int) -> int:
    estimate = estimate_resources(tool=tool, assay=assay, samples=samples)
    print(json.dumps(asdict(estimate), indent=2))
    return 0


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


def cmd_rbac_check(role: str, action: str) -> int:
    decision = check_access(role, action)
    print(json.dumps(asdict(decision), indent=2))
    return 0 if decision.allowed else 2


def cmd_report(schema_ok: bool, container_policy_ok: bool, cache_percent: int, diagnostics: str, out: str) -> int:
    report = build_validation_report(
        schema_ok=schema_ok,
        container_policy_ok=container_policy_ok,
        cache_percent=cache_percent,
        diagnostics=diagnostics,
    )
    write_report(report, out)
    print(f"validation report written: {out}")
    return 0 if report.status == "pass" else 2


def cmd_profile_suggest(assay: str, reference: str | None, offline: bool) -> int:
    rec = recommend_profile(assay=assay, reference=reference, offline=offline)
    print(json.dumps(asdict(rec), indent=2))
    return 0


def cmd_provenance(command: str, params_json: str) -> int:
    params = json.loads(params_json)
    record = make_provenance_record(command=command, params=params)
    print(json.dumps(asdict(record), indent=2))
    return 0


def cmd_image_check(image: str) -> int:
    result = check_image_policy(image)
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.allowed else 2


def cmd_audit_verify() -> int:
    if not AUDIT_FILE.exists():
        print(json.dumps({"ok": False, "reason": "audit file missing"}, indent=2))
        return 2

    invalid = 0
    missing_hash = 0
    mismatched_hash = 0
    lines = 0
    for raw in AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        lines += 1
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            invalid += 1
            continue
        event_hash = event.get("execution_hash")
        if not event_hash:
            missing_hash += 1
            continue
        params = event.get("provenance_params")
        command = event.get("command")
        if isinstance(params, dict) and isinstance(command, str):
            expected = make_provenance_record(command=command, params=params).execution_hash
            if expected != event_hash:
                mismatched_hash += 1

    ok = invalid == 0 and missing_hash == 0 and mismatched_hash == 0 and lines > 0
    print(
        json.dumps(
            {
                "ok": ok,
                "lines": lines,
                "invalid_json": invalid,
                "missing_hash": missing_hash,
                "mismatched_hash": mismatched_hash,
            },
            indent=2,
        )
    )
    return 0 if ok else 2


def authorize(role: str, action: str | None) -> int:
    if not action:
        return 0
    decision = check_access(role, action)
    if decision.allowed:
        return 0
    print(f"helixsh error: role '{decision.role}' is not allowed to run '{decision.action}'", file=sys.stderr)
    return 2


def cmd_context_check(samplesheet: str | None, config: str | None) -> int:
    payload: dict = {}
    if samplesheet:
        payload["samplesheet"] = asdict(summarize_samplesheet(samplesheet))
    if config:
        payload["nextflow_config"] = asdict(parse_nextflow_config_defaults(config))
    if not payload:
        payload["message"] = "No context source provided"
    print(json.dumps(payload, indent=2))
    return 0


def cmd_offline_check(cache_root: str) -> int:
    report = check_offline_readiness(cache_root)
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.ready else 2


def cmd_posix_wrap(args: list[str], execute: bool) -> int:
    wrapped = build_posix_exec(args)
    print(wrapped)
    if execute:
        return run_posix_exec(args)
    return 0


def cmd_preflight(schema: str | None, params: str | None, workflow: str | None, cache_root: str | None, samplesheet: str | None, config: str | None, image: str | None) -> int:
    checks: dict[str, dict] = {}

    if schema and params:
        result = validate_params(load_json(schema), load_json(params))
        checks["schema"] = {"ok": result.ok, "issues": [asdict(i) for i in result.issues]}

    if workflow:
        nodes = parse_process_nodes(Path(workflow).read_text(encoding="utf-8"))
        violations = container_violations(nodes)
        checks["workflow"] = {"ok": len(violations) == 0, "violations": violations}

    if cache_root:
        off = check_offline_readiness(cache_root)
        checks["offline"] = {"ok": off.ready, **asdict(off)}

    if samplesheet or config:
        ctx: dict = {}
        if samplesheet:
            ctx["samplesheet"] = asdict(summarize_samplesheet(samplesheet))
        if config:
            ctx["nextflow_config"] = asdict(parse_nextflow_config_defaults(config))
        checks["context"] = {"ok": True, **ctx}

    if image is not None:
        img = check_image_policy(image)
        checks["image"] = {"ok": img.allowed, **asdict(img)}

    overall_ok = all(item.get("ok", True) for item in checks.values()) if checks else False
    payload = {"ok": overall_ok, "checks": checks}
    print(json.dumps(payload, indent=2))
    return 0 if overall_ok else 2


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    strict = bool(getattr(args, "strict", False))

    auth_rc = authorize(getattr(args, "role", "analyst"), args.command)
    if auth_rc != 0:
        return auth_rc

    try:
        if args.command == "run":
            return cmd_run(args, strict=strict, role=getattr(args, "role", "analyst"))
        if args.command == "doctor":
            return cmd_doctor()
        if args.command == "explain":
            return cmd_explain(args.scope)
        if args.command == "plan":
            return cmd_plan()
        if args.command == "roadmap-status":
            return cmd_roadmap_status()
        if args.command == "intent":
            return cmd_intent(args.text)
        if args.command == "validate-schema":
            return cmd_validate_schema(args.schema, args.params)
        if args.command == "mcp-check":
            return cmd_mcp_check(args.capability)
        if args.command == "mcp-propose":
            return cmd_mcp_propose(args.kind, args.summary, args.payload)
        if args.command == "mcp-proposals":
            return cmd_mcp_proposals()
        if args.command == "mcp-approve":
            return cmd_mcp_approve(args.id)
        if args.command == "audit-export":
            return cmd_audit_export(args.out)
        if args.command == "audit-verify":
            return cmd_audit_verify()
        if args.command == "parse-workflow":
            return cmd_parse_workflow(args.file)
        if args.command == "diagnose":
            return cmd_diagnose(args.process, args.exit_code, args.memory_gb)
        if args.command == "cache-report":
            return cmd_cache_report(args.total, args.cached, args.invalidated)
        if args.command == "rbac-check":
            return cmd_rbac_check(args.role, args.action)
        if args.command == "report":
            return cmd_report(args.schema_ok, args.container_policy_ok, args.cache_percent, args.diagnostics, args.out)
        if args.command == "resource-estimate":
            return cmd_resource_estimate(args.tool, args.assay, args.samples)
        if args.command == "profile-suggest":
            return cmd_profile_suggest(args.assay, args.reference, args.offline)
        if args.command == "provenance":
            return cmd_provenance(args.plan_command, args.params)
        if args.command == "image-check":
            return cmd_image_check(args.image)
        if args.command == "context-check":
            return cmd_context_check(args.samplesheet, args.config)
        if args.command == "offline-check":
            return cmd_offline_check(args.cache_root)
        if args.command == "preflight":
            return cmd_preflight(args.schema, args.params, args.workflow, args.cache_root, args.samplesheet, args.config, args.image)
        if args.command == "posix-wrap":
            return cmd_posix_wrap(args.args, args.execute)

        parser.print_help()
        return 0
    except (HelixshError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"helixsh error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
