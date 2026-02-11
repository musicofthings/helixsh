"""Compliance-mode policy checks for clinical workflows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComplianceResult:
    ok: bool
    requires_manual_review: bool
    flags: list[str]


def has_digest_pin(image: str) -> bool:
    image_norm = image.strip()
    return "@sha256:" in image_norm and len(image_norm.split("@sha256:", 1)[1]) > 0


def evaluate_compliance(
    *,
    images: list[str],
    agreement_score: float,
    confidences: list[float],
    evidence_conflict: bool,
) -> ComplianceResult:
    flags: list[str] = []

    if images and not all(has_digest_pin(img) for img in images):
        flags.append("UNPINNED_CONTAINER_DIGEST")

    avg_conf = (sum(confidences) / len(confidences)) if confidences else 1.0
    if agreement_score < 0.67:
        flags.append("AGENT_DISAGREEMENT")
    if avg_conf < 0.7:
        flags.append("LOW_CONFIDENCE")
    if evidence_conflict:
        flags.append("EVIDENCE_CONFLICT")

    requires_manual_review = any(
        f in {"AGENT_DISAGREEMENT", "LOW_CONFIDENCE", "EVIDENCE_CONFLICT"}
        for f in flags
    )

    return ComplianceResult(
        ok=len(flags) == 0,
        requires_manual_review=requires_manual_review,
        flags=flags,
    )
