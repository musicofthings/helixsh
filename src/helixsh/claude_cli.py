"""Claude Code CLI proposal integration shim."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClaudePlan:
    prompt: str
    proposed_diff_summary: str
    confidence: float


def generate_plan(prompt: str) -> ClaudePlan:
    text = prompt.strip()
    summary = "No-op"
    confidence = 0.5
    lowered = text.lower()
    if "memory" in lowered:
        summary = "Propose reducing parallelism and increasing memory limits"
        confidence = 0.82
    elif "container" in lowered:
        summary = "Propose digest-pinned container images for all processes"
        confidence = 0.8
    elif "schema" in lowered:
        summary = "Propose nf-core parameter/schema alignment fixes"
        confidence = 0.78
    return ClaudePlan(prompt=text, proposed_diff_summary=summary, confidence=confidence)
