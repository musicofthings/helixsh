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
from helixsh.signing import sign_file, verify_file_signature
from helixsh.calibration import load_calibration
from helixsh.claude_cli import generate_plan
from helixsh.empirical import fit_calibration_from_file, write_calibration
from helixsh.mcp_runtime import execute_approved_proposal
from helixsh.lifecycle import create_execution_context
from helixsh.lifecycle import sha256_file, file_size_bytes
from helixsh.provenance_db import (
    add_audit_event,
    create_execution,
    finish_execution,
    get_execution_bundle,
    init_db,
    insert_container,
    insert_input,
)
from helixsh.haps import AgentResponse, run_agent_task
from helixsh.arbitration import arbitrate
from helixsh.compliance import evaluate_compliance
from helixsh.bioconda import (
    build_install_command,
    create_env,
    install_packages,
    list_known_tools,
    search_package,
)

# Curated list of popular nf-core pipelines for `nf-list`
_NF_CORE_PIPELINES = [
    {"name": "nf-core/rnaseq", "description": "RNA-seq quantification (STAR/Salmon/HISAT2)"},
    {"name": "nf-core/sarek", "description": "Germline and somatic variant calling (WGS/WES)"},
    {"name": "nf-core/chipseq", "description": "ChIP-seq peak calling and differential analysis"},
    {"name": "nf-core/atacseq", "description": "ATAC-seq peak calling and annotation"},
    {"name": "nf-core/methylseq", "description": "Bisulfite sequencing / DNA methylation analysis"},
    {"name": "nf-core/scrnaseq", "description": "Single-cell RNA-seq analysis (STARsolo/Alevin/Cellranger)"},
    {"name": "nf-core/ampliseq", "description": "Amplicon sequencing / 16S rRNA analysis"},
    {"name": "nf-core/mag", "description": "Metagenome assembly and binning"},
    {"name": "nf-core/viralrecon", "description": "Viral genome reconstruction (SARS-CoV-2 etc.)"},
    {"name": "nf-core/eager", "description": "Ancient DNA analysis (aDNA)"},
    {"name": "nf-core/nanoseq", "description": "Oxford Nanopore long-read analysis"},
    {"name": "nf-core/hic", "description": "Hi-C chromatin conformation analysis"},
    {"name": "nf-core/differentialabundance", "description": "Differential abundance analysis for RNA/proteomics"},
    {"name": "nf-core/taxprofiler", "description": "Metagenomic taxonomic profiling"},
    {"name": "nf-core/fetchngs", "description": "Fetch public sequencing data (SRA/ENA)"},
]

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
    run_parser.add_argument("--outdir", dest="outdir", default=None, help="Output directory (--outdir passed to pipeline).")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--offline", action="store_true", help="Run Nextflow in offline mode (-offline flag).")
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

    claude_parser = subparsers.add_parser("claude-plan", help="Generate a Claude-style plan proposal and store it.")
    claude_parser.add_argument("--prompt", required=True)

    mcp_exec = subparsers.add_parser("mcp-execute", help="Execute an approved MCP proposal.")
    mcp_exec.add_argument("--id", required=True, type=int)

    export_parser = subparsers.add_parser("audit-export", help="Export audit log with reproducible hash.")
    export_parser.add_argument("--out", required=True)

    subparsers.add_parser("audit-verify", help="Verify audit log integrity/shape.")

    sign_parser = subparsers.add_parser("audit-sign", help="Sign audit log with HMAC key.")
    sign_parser.add_argument("--key-file", required=True)
    sign_parser.add_argument("--out", required=True, help="Path to write signature hex")

    verify_sig = subparsers.add_parser("audit-verify-signature", help="Verify audit log signature with HMAC key.")
    verify_sig.add_argument("--key-file", required=True)
    verify_sig.add_argument("--signature-file", required=True)

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
    res_parser.add_argument("--calibration", help="Path to calibration JSON with cpu/memory multipliers")

    fit_parser = subparsers.add_parser("fit-calibration", help="Fit calibration multipliers from observation JSON.")
    fit_parser.add_argument("--observations", required=True)
    fit_parser.add_argument("--out", required=True)

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

    # ── Execution lifecycle ────────────────────────────────────────────────────
    exec_start = subparsers.add_parser("execution-start", help="Record execution start in provenance DB.")
    exec_start.add_argument("--command", dest="run_command", required=True)
    exec_start.add_argument("--workflow")
    exec_start.add_argument("--db", required=True, help="Path to SQLite provenance DB.")
    exec_start.add_argument("--input", dest="input_files", action="append", default=[], help="Input file path (repeatable).")
    exec_start.add_argument("--image", help="Container image reference.")
    exec_start.add_argument("--agent")
    exec_start.add_argument("--model")

    exec_finish = subparsers.add_parser("execution-finish", help="Record execution completion in provenance DB.")
    exec_finish.add_argument("--execution-id", required=True)
    exec_finish.add_argument("--status", required=True)
    exec_finish.add_argument("--db", required=True)
    exec_finish.add_argument("--exit-code", type=int)
    exec_finish.add_argument("--output-hash")

    audit_show = subparsers.add_parser("audit-show", help="Show full execution bundle from provenance DB.")
    audit_show.add_argument("--execution-id", required=True)
    audit_show.add_argument("--db", required=True)

    # ── Agent tasks ────────────────────────────────────────────────────────────
    agent_run = subparsers.add_parser("agent-run", help="Run an agent task via HAPS v1.")
    agent_run.add_argument("--agent", required=True)
    agent_run.add_argument("--task", required=True)
    agent_run.add_argument("--model", required=True)
    agent_run.add_argument("--payload", required=True)

    arbitrate_p = subparsers.add_parser("arbitrate", help="Arbitrate between multiple agent responses.")
    arbitrate_p.add_argument("--responses", required=True, help="JSON file with list of agent response dicts.")
    arbitrate_p.add_argument("--strategy", default="majority", choices=["majority", "weighted_confidence"])

    compliance_p = subparsers.add_parser("compliance-check", help="Evaluate clinical compliance policy.")
    compliance_p.add_argument("--image", action="append", default=[], dest="images")
    compliance_p.add_argument("--agreement-score", type=float, required=True)
    compliance_p.add_argument("--confidence", action="append", type=float, default=[], dest="confidences")
    compliance_p.add_argument("--evidence-conflict", action="store_true")

    # ── Bioconda integration ───────────────────────────────────────────────────
    conda_search_p = subparsers.add_parser("conda-search", help="Search Bioconda for a package.")
    conda_search_p.add_argument("--package", required=True)

    conda_install_p = subparsers.add_parser("conda-install", help="Install packages from Bioconda (dry-run by default).")
    conda_install_p.add_argument("--package", action="append", required=True, dest="packages")
    conda_install_p.add_argument("--env", dest="env_name", default=None)
    conda_install_p.add_argument("--execute", action="store_true", help="Actually run the install (default: dry-run).")

    conda_env_p = subparsers.add_parser("conda-env", help="Create a Bioconda environment (dry-run by default).")
    conda_env_p.add_argument("--name", required=True)
    conda_env_p.add_argument("--tool", action="append", default=[], dest="tools")
    conda_env_p.add_argument("--python", default="3.12")
    conda_env_p.add_argument("--execute", action="store_true", help="Actually create the environment.")

    subparsers.add_parser("nf-list", help="List curated nf-core pipelines.")

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
        outdir=getattr(args, "outdir", None),
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


def cmd_claude_plan(prompt: str) -> int:
    plan = generate_plan(prompt)
    payload = json.dumps(asdict(plan), ensure_ascii=False)
    proposal = create_proposal(str(PROPOSAL_FILE), kind="claude_plan", summary=plan.proposed_diff_summary, payload=payload)
    print(json.dumps({"plan": asdict(plan), "proposal": asdict(proposal)}, indent=2))
    return 0



def cmd_mcp_approve(proposal_id: int) -> int:
    proposal = approve_proposal(str(PROPOSAL_FILE), proposal_id=proposal_id)
    print(json.dumps(asdict(proposal), indent=2))
    return 0


def cmd_mcp_execute(proposal_id: int) -> int:
    result = execute_approved_proposal(str(PROPOSAL_FILE), proposal_id)
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.executed else 2


def cmd_fit_calibration(observations: str, out: str) -> int:
    fitted = fit_calibration_from_file(observations)
    write_calibration(out, fitted)
    print(json.dumps({"out": out, "calibration": asdict(fitted)}, indent=2))
    return 0



def cmd_resource_estimate(tool: str, assay: str, samples: int, calibration: str | None) -> int:
    cpu_mult = 1.0
    mem_mult = 1.0
    if calibration:
        c = load_calibration(calibration)
        cpu_mult = c.cpu_multiplier
        mem_mult = c.memory_multiplier
    estimate = estimate_resources(tool=tool, assay=assay, samples=samples, cpu_multiplier=cpu_mult, memory_multiplier=mem_mult)
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


def cmd_audit_sign(key_file: str, out_path: str) -> int:
    if not AUDIT_FILE.exists():
        raise FileNotFoundError(str(AUDIT_FILE))
    sig = sign_file(str(AUDIT_FILE), key_file)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sig + "\n", encoding="utf-8")
    print(json.dumps({"signature_file": str(out), "signature": sig}, indent=2))
    return 0


def cmd_audit_verify_signature(key_file: str, signature_file: str) -> int:
    if not AUDIT_FILE.exists():
        raise FileNotFoundError(str(AUDIT_FILE))
    expected = Path(signature_file).read_text(encoding="utf-8").strip()
    ok = verify_file_signature(str(AUDIT_FILE), key_file, expected)
    print(json.dumps({"ok": ok, "signature_file": signature_file}, indent=2))
    return 0 if ok else 2


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


def cmd_execution_start(
    command: str,
    db: str,
    workflow: str | None,
    input_files: list[str],
    image: str | None,
    agent: str | None,
    model: str | None,
) -> int:
    init_db(db)
    ctx = create_execution_context(
        working_dir=str(Path(db).parent.resolve()),
        input_files=input_files,
        agent=agent,
        container_digest=image,
    )
    create_execution(
        db,
        execution_id=ctx.execution_id,
        command=command,
        workflow=workflow,
        agent=agent,
        model=model,
        status="running",
        start_time=ctx.timestamp,
        container_digest=ctx.container_digest,
        input_hash=ctx.input_hash,
    )
    for path in input_files:
        try:
            h = sha256_file(path)
            sz = file_size_bytes(path)
        except OSError:
            h, sz = "", 0
        insert_input(db, execution_id=ctx.execution_id, file_path=path, sha256=h, size_bytes=sz)
    if image:
        insert_container(
            db,
            execution_id=ctx.execution_id,
            image_name=image.split("@")[0],
            image_digest=image.split("@sha256:")[-1] if "@sha256:" in image else None,
            runtime="docker",
        )
    add_audit_event(db, execution_id=ctx.execution_id, event_type="start", message=command)
    print(json.dumps({"execution_context": asdict(ctx)}, indent=2))
    return 0


def cmd_execution_finish(execution_id: str, db: str, status: str, exit_code: int | None, output_hash: str | None) -> int:
    finish_execution(
        db,
        execution_id=execution_id,
        status=status,
        end_time=datetime.now(UTC).isoformat(),
        output_hash=output_hash,
        exit_code=exit_code,
    )
    add_audit_event(db, execution_id=execution_id, event_type="finish", message=status)
    print(json.dumps({"execution_id": execution_id, "status": status}, indent=2))
    return 0


def cmd_audit_show(execution_id: str, db: str) -> int:
    bundle = get_execution_bundle(db, execution_id)
    print(json.dumps(bundle, indent=2))
    return 0


def cmd_agent_run(agent: str, task: str, model: str, payload: str) -> int:
    response = run_agent_task(agent, model, task, payload)
    print(json.dumps(asdict(response), indent=2))
    return 0


def cmd_arbitrate(responses_path: str, strategy: str) -> int:
    raw = json.loads(Path(responses_path).read_text(encoding="utf-8"))
    responses = [
        AgentResponse(
            agent=r["agent"],
            model=r["model"],
            task=r["task"],
            status=r["status"],
            result=r["result"],
            reasoning=r["reasoning"],
            confidence=r["confidence"],
            execution_time_ms=r["execution_time_ms"],
            acmg_evidence=r.get("acmg_evidence"),
        )
        for r in raw
    ]
    result = arbitrate(responses, strategy=strategy)
    print(json.dumps(asdict(result), indent=2))
    return 0


def cmd_compliance_check(images: list[str], agreement_score: float, confidences: list[float], evidence_conflict: bool) -> int:
    result = evaluate_compliance(
        images=images,
        agreement_score=agreement_score,
        confidences=confidences,
        evidence_conflict=evidence_conflict,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.ok else 2


def cmd_conda_search(package: str) -> int:
    info = search_package(package)
    print(json.dumps({"name": info.name, "channel": info.channel, "versions": info.versions}, indent=2))
    return 0


def cmd_conda_install(packages: list[str], env_name: str | None, execute: bool) -> int:
    result = install_packages(packages, env_name=env_name, dry_run=not execute)
    payload = {
        "command": result.command,
        "dry_run": not execute,
        "ok": result.ok,
    }
    if execute:
        payload["returncode"] = result.returncode
        if result.stderr:
            payload["stderr"] = result.stderr
    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 2


def cmd_conda_env(name: str, tools: list[str], python_version: str, execute: bool) -> int:
    result = create_env(name, tools, python_version=python_version, dry_run=not execute)
    payload = {
        "command": result.command,
        "dry_run": not execute,
        "ok": result.ok,
    }
    if execute:
        payload["returncode"] = result.returncode
        if result.stderr:
            payload["stderr"] = result.stderr
    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 2


def cmd_nf_list() -> int:
    print(json.dumps(_NF_CORE_PIPELINES, indent=2))
    return 0


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
        if args.command == "claude-plan":
            return cmd_claude_plan(args.prompt)
        if args.command == "mcp-execute":
            return cmd_mcp_execute(args.id)
        if args.command == "audit-export":
            return cmd_audit_export(args.out)
        if args.command == "audit-verify":
            return cmd_audit_verify()
        if args.command == "audit-sign":
            return cmd_audit_sign(args.key_file, args.out)
        if args.command == "audit-verify-signature":
            return cmd_audit_verify_signature(args.key_file, args.signature_file)
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
            return cmd_resource_estimate(args.tool, args.assay, args.samples, args.calibration)
        if args.command == "fit-calibration":
            return cmd_fit_calibration(args.observations, args.out)
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
        if args.command == "execution-start":
            return cmd_execution_start(
                command=args.run_command,
                db=args.db,
                workflow=args.workflow,
                input_files=args.input_files,
                image=args.image,
                agent=args.agent,
                model=args.model,
            )
        if args.command == "execution-finish":
            return cmd_execution_finish(
                execution_id=args.execution_id,
                db=args.db,
                status=args.status,
                exit_code=args.exit_code,
                output_hash=args.output_hash,
            )
        if args.command == "audit-show":
            return cmd_audit_show(args.execution_id, args.db)
        if args.command == "agent-run":
            return cmd_agent_run(args.agent, args.task, args.model, args.payload)
        if args.command == "arbitrate":
            return cmd_arbitrate(args.responses, args.strategy)
        if args.command == "compliance-check":
            return cmd_compliance_check(args.images, args.agreement_score, args.confidences, args.evidence_conflict)
        if args.command == "conda-search":
            return cmd_conda_search(args.package)
        if args.command == "conda-install":
            return cmd_conda_install(args.packages, args.env_name, args.execute)
        if args.command == "conda-env":
            return cmd_conda_env(args.name, args.tools, args.python, args.execute)
        if args.command == "nf-list":
            return cmd_nf_list()

        parser.print_help()
        return 0
    except (HelixshError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"helixsh error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
