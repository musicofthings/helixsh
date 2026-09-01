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
            status="in_progress",
            completed=(
                "POSIX shell wrapper",
                "Nextflow command interception",
                "nf-core-style schema validation scaffold",
                "Container enforcement scaffolding",
                "Execution-time preflight enforcement",
                "Sandboxed Electron desktop planner and runner",
                "Docker daemon and Kubernetes cluster readiness checks",
                "Validated nf-k8s shared-storage configuration generation",
                "Runs that survive the desktop app closing, and are picked up again",
                "Post-run results, reports and per-process resource summary",
                "Samplesheet generation and validation from a directory of FASTQ files",
                "Validated AWS Batch and Google Batch executor configuration",
                "Cloud executors in the desktop app, with credential sources reported",
                "Real-execution integration tiers and a GUI eval battery in CI",
            ),
            pending=(
                "Interactive POSIX shell and intent-first command interception",
                "Full Nextflow AST/DAG parsing including inputs, outputs, and when conditions",
                "nf-core schema acquisition and complete JSON Schema validation",
                "End-to-end host-binary blocking and digest-pinned container enforcement across runtimes",
            ),
        ),
        PhaseStatus(
            phase="Phase 2 — AI Planning",
            status="in_progress",
            completed=(
                "Intent → parameter mapping scaffold",
                "MCP capability policy",
                "Proposal workflow store",
                "Deterministic Claude-plan proposal shim",
            ),
            pending=(
                "Live Claude Code CLI and MCP gateway integration",
                "Validated proposal diff application",
                "End-to-end intent to preflighted execution plans",
            ),
        ),
        PhaseStatus(
            phase="Phase 3 — Bioinformatics Intelligence",
            status="in_progress",
            completed=(
                "RNA-seq/WGS/WES profile suggestions",
                "Tool memory/CPU estimation scaffold",
                "Reference genome parameter hints",
                "Empirical tool performance model calibration",
            ),
            pending=(
                "Workflow-aware resource mismatch and bottleneck prediction",
                "Semantic parameter and tool explanations",
                "Reference asset awareness and cache invalidation reasoning",
            ),
        ),
        PhaseStatus(
            phase="Phase 4 — Enterprise Hardening",
            status="in_progress",
            completed=(
                "Offline checks",
                "RBAC enforcement",
                "Audit exports and verification",
                "Validation reports",
                "Signed audit artifact workflow",
            ),
            pending=(
                "Full command, parameter, and container-digest provenance",
                "Strict-mode confirmation for every mutating operation",
                "Clinical validation and compliance hardening",
                # Blocked on an Apple Developer identity and a Mac to build and
                # verify on, rather than on anything in this repository.
                "Signed and notarized universal macOS app with bundled Python/Nextflow",
                "Apple App Sandbox entitlement and production update channel",
            ),
        ),
    ]
