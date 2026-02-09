"""Simple RBAC policy for helixsh command authorization."""

from __future__ import annotations

from dataclasses import dataclass


ROLE_PERMISSIONS = {
    "admin": {"run", "doctor", "explain", "plan", "intent", "validate-schema", "mcp-check", "audit-export", "parse-workflow", "diagnose", "cache-report", "report"},
    "analyst": {"run", "doctor", "explain", "plan", "intent", "validate-schema", "parse-workflow", "diagnose", "cache-report", "report"},
    "auditor": {"doctor", "explain", "plan", "mcp-check", "audit-export", "report"},
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
