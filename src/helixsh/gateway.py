"""Local MCP gateway proposal workflow storage."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Proposal:
    proposal_id: int
    created_at: str
    kind: str
    summary: str
    payload: str
    status: str


def _load(path: Path) -> list[Proposal]:
    if not path.exists():
        return []
    items: list[Proposal] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        items.append(Proposal(**raw))
    return items


def _save(path: Path, proposals: list[Proposal]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for p in proposals:
            handle.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")


def create_proposal(path: str, kind: str, summary: str, payload: str) -> Proposal:
    p = Path(path)
    proposals = _load(p)
    next_id = (max((x.proposal_id for x in proposals), default=0) + 1)
    proposal = Proposal(
        proposal_id=next_id,
        created_at=datetime.now(UTC).isoformat(),
        kind=kind,
        summary=summary,
        payload=payload,
        status="proposed",
    )
    proposals.append(proposal)
    _save(p, proposals)
    return proposal


def list_proposals(path: str) -> list[Proposal]:
    return _load(Path(path))


def approve_proposal(path: str, proposal_id: int) -> Proposal:
    p = Path(path)
    proposals = _load(p)
    updated: Proposal | None = None
    out: list[Proposal] = []
    for item in proposals:
        if item.proposal_id == proposal_id:
            updated = Proposal(
                proposal_id=item.proposal_id,
                created_at=item.created_at,
                kind=item.kind,
                summary=item.summary,
                payload=item.payload,
                status="approved",
            )
            out.append(updated)
        else:
            out.append(item)
    if updated is None:
        raise ValueError(f"Proposal id not found: {proposal_id}")
    _save(p, out)
    return updated
