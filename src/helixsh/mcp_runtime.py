"""Execution/runtime helpers for approved MCP proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass

from helixsh.gateway import Proposal, list_proposals


@dataclass(frozen=True)
class RuntimeResult:
    proposal_id: int
    executed: bool
    message: str


def execute_approved_proposal(store_path: str, proposal_id: int) -> RuntimeResult:
    proposals = {p.proposal_id: p for p in list_proposals(store_path)}
    proposal: Proposal | None = proposals.get(proposal_id)
    if proposal is None:
        raise ValueError(f"Proposal id not found: {proposal_id}")
    if proposal.status != "approved":
        return RuntimeResult(proposal_id=proposal_id, executed=False, message="Proposal is not approved")

    if proposal.kind == "claude_plan":
        details = json.loads(proposal.payload)
        return RuntimeResult(
            proposal_id=proposal_id,
            executed=True,
            message=f"Executed plan: {details.get('proposed_diff_summary', 'n/a')}",
        )

    return RuntimeResult(
        proposal_id=proposal_id,
        executed=True,
        message=f"Executed proposal kind: {proposal.kind}",
    )
