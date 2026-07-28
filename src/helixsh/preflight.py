"""Reusable preflight validation for plans and execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from helixsh.container_policy import check_image_policy
from helixsh.context import parse_nextflow_config_defaults, summarize_samplesheet
from helixsh.kubernetes import validate_kubernetes_config_file
from helixsh.offline import check_offline_readiness
from helixsh.schema import load_json, validate_params
from helixsh.workflow import container_violations, parse_process_nodes


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    checks: dict[str, dict]


def run_preflight(
    *,
    schema: str | None = None,
    params: str | None = None,
    workflow: str | None = None,
    cache_root: str | None = None,
    samplesheet: str | None = None,
    config: str | None = None,
    image: str | None = None,
    runtime: str | None = None,
) -> PreflightResult:
    """Run every requested check and return one machine-readable result."""

    checks: dict[str, dict] = {}

    if schema or params:
        if not schema or not params:
            checks["schema"] = {
                "ok": False,
                "issues": [
                    {
                        "field": "schema,params",
                        "message": "--schema and --params must be provided together",
                    }
                ],
            }
        else:
            result = validate_params(load_json(schema), load_json(params))
            checks["schema"] = {
                "ok": result.ok,
                "issues": [asdict(issue) for issue in result.issues],
            }

    if workflow:
        nodes = parse_process_nodes(Path(workflow).read_text(encoding="utf-8"))
        violations = container_violations(nodes)
        checks["workflow"] = {
            "ok": len(violations) == 0,
            "process_count": len(nodes),
            "violations": violations,
        }

    if cache_root:
        offline = check_offline_readiness(cache_root)
        checks["offline"] = {"ok": offline.ready, **asdict(offline)}

    if samplesheet or config:
        context: dict = {}
        if samplesheet:
            context["samplesheet"] = asdict(summarize_samplesheet(samplesheet))
        if config:
            context["nextflow_config"] = asdict(parse_nextflow_config_defaults(config))
        checks["context"] = {"ok": True, **context}

    if runtime == "kubernetes":
        issues = (
            validate_kubernetes_config_file(config)
            if config
            else ("Kubernetes execution requires a Nextflow config file",)
        )
        checks["kubernetes"] = {"ok": not issues, "issues": list(issues)}

    if image is not None:
        policy = check_image_policy(image)
        checks["image"] = {"ok": policy.allowed, **asdict(policy)}

    return PreflightResult(
        ok=bool(checks) and all(check.get("ok", False) for check in checks.values()),
        checks=checks,
    )
