"""Roadmap status model for implementation tracking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseStatus:
    phase: str
    status: str
    completed: tuple[str, ...]
    pending: tuple[str, ...]


def compute_roadmap_status() -> list[PhaseStatus]:
    return [
        PhaseStatus(
            phase="Phase 1 — Foundation",
            status="completed",
            completed=(
                "POSIX shell wrapper",
                "Nextflow command interception",
                "nf-core schema ingestion",
                "Container enforcement scaffolding",
            ),
            pending=tuple(),
        ),
        PhaseStatus(
            phase="Phase 2 — AI Planning",
            status="completed",
            completed=(
                "Intent → parameter mapping scaffold",
                "MCP capability policy",
                "Proposal workflow store",
                "Claude Code CLI integration shim",
                "End-to-end MCP proposal execution runtime",
            ),
            pending=tuple(),
        ),
        PhaseStatus(
            phase="Phase 3 — Bioinformatics Intelligence",
            status="completed",
            completed=(
                "RNA-seq/WGS/WES profile suggestions",
                "Tool memory/CPU estimation scaffold",
                "Reference genome parameter hints",
                "Empirical tool performance model calibration",
            ),
            pending=tuple(),
        ),
        PhaseStatus(
            phase="Phase 4 — Enterprise Hardening",
            status="completed",
            completed=(
                "Offline checks",
                "RBAC enforcement",
                "Audit exports and verification",
                "Validation reports",
                "Signed audit artifact workflow",
            ),
            pending=tuple(),
        ),
    ]
