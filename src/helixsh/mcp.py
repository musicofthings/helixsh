"""MCP gateway policy primitives."""

from __future__ import annotations

from dataclasses import dataclass


ALLOWED_CAPABILITIES = {
    "read_logs": True,
    "inspect_dag": True,
    "modify_files": "proposal_only",
    "execute_commands": False,
}


@dataclass(frozen=True)
class CapabilityDecision:
    capability: str
    allowed: bool
    mode: str


def evaluate_capability(capability: str) -> CapabilityDecision:
    value = ALLOWED_CAPABILITIES.get(capability)
    if value is True:
        return CapabilityDecision(capability=capability, allowed=True, mode="allow")
    if value == "proposal_only":
        return CapabilityDecision(capability=capability, allowed=True, mode="proposal_only")
    return CapabilityDecision(capability=capability, allowed=False, mode="deny")
