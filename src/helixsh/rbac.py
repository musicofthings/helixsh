"""Simple RBAC policy for helixsh command authorization."""

from __future__ import annotations

from dataclasses import dataclass

# Permissions shared by all authenticated roles
_READ_ONLY = {
    "doctor", "explain", "plan", "roadmap-status",
    "audit-export", "audit-verify", "audit-sign", "audit-verify-signature", "audit-show",
    "rbac-check", "report",
    "mcp-check", "mcp-proposals",
    "image-check", "context-check", "offline-check", "preflight",
    "provenance", "posix-wrap",
    "resource-estimate", "profile-suggest",
    # Read-only pipeline intelligence
    "nf-list", "nf-auth",
    "ref-list", "pipeline-list",
    "envmodules-list",
    "tower-auth", "tower-status", "tower-envs",
    "trace-summary",
    "cost-estimate",
}

# Permissions available to analysts (pipeline operators)
_ANALYST_EXTRA = {
    "run", "intent", "validate-schema",
    "parse-workflow", "diagnose", "cache-report",
    "mcp-propose", "mcp-approve", "mcp-execute", "claude-plan",
    "fit-calibration",
    "conda-search", "conda-env",
    "execution-start", "execution-finish",
    "agent-run", "arbitrate", "compliance-check",
    # New feature commands
    "nf-launch",
    "samplesheet-validate", "samplesheet-generate",
    "ref-download",
    "pipeline-update",
    "envmodules-wrap",
    "tower-submit",
    "snakemake-import",
}

# Admin-only additions (e.g. installing system-wide packages)
_ADMIN_EXTRA = {
    "conda-install",
}

ROLE_PERMISSIONS = {
    "admin": _READ_ONLY | _ANALYST_EXTRA | _ADMIN_EXTRA,
    "analyst": _READ_ONLY | _ANALYST_EXTRA,
    # auditor: strictly read-only; cannot execute pipelines or approve proposals
    "auditor": _READ_ONLY,
}


@dataclass(frozen=True)
class AccessDecision:
    role: str
    action: str
    allowed: bool


def check_access(role: str, action: str) -> AccessDecision:
    role_norm = role.strip().lower()
    action_norm = action.strip()
    allowed = action_norm in ROLE_PERMISSIONS.get(role_norm, set())
    return AccessDecision(role=role_norm, action=action_norm, allowed=allowed)
