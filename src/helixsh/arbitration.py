"""Multi-agent arbitration helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from helixsh.haps import AgentResponse


@dataclass(frozen=True)
class ArbitrationResult:
    final_classification: str
    confidence: float
    agreement_score: float
    disagreement_flags: list[str]
    agents_compared: int
    strategy: str


def _extract_classification(response: AgentResponse) -> str:
    cls = response.result.get("classification")
    return str(cls) if cls else "Unknown"


def arbitrate(responses: list[AgentResponse], strategy: str = "majority") -> ArbitrationResult:
    if not responses:
        raise ValueError("at least one agent response is required")

    strategy_norm = strategy.strip().lower()
    classifications = [_extract_classification(r) for r in responses]
    counts = Counter(classifications)

    if strategy_norm == "weighted_confidence":
        score_by_class: dict[str, float] = {}
        for r, cls in zip(responses, classifications):
            score_by_class[cls] = score_by_class.get(cls, 0.0) + r.confidence
        final_classification = max(score_by_class.items(), key=lambda item: item[1])[0]
        total_score = sum(score_by_class.values()) or 1.0
        confidence = score_by_class[final_classification] / total_score
    else:
        final_classification, winner_count = counts.most_common(1)[0]
        confidence = winner_count / len(classifications)

    agreement_score = counts[final_classification] / len(classifications)

    disagreement_flags: list[str] = []
    if agreement_score < 0.67:
        disagreement_flags.append("LOW_AGENT_AGREEMENT")
    avg_confidence = sum(r.confidence for r in responses) / len(responses)
    if avg_confidence < 0.7:
        disagreement_flags.append("LOW_AVERAGE_CONFIDENCE")

    acmg_blocks = [r.acmg_evidence for r in responses if isinstance(r.acmg_evidence, dict)]
    if len(acmg_blocks) >= 2:
        keys = set().union(*[set(b.keys()) for b in acmg_blocks])
        mismatch = any(len({bool(b.get(k, False)) for b in acmg_blocks}) > 1 for k in keys)
        if mismatch:
            disagreement_flags.append("ACMG_RULE_CONFLICT")

    return ArbitrationResult(
        final_classification=final_classification,
        confidence=round(confidence, 4),
        agreement_score=round(agreement_score, 4),
        disagreement_flags=sorted(set(disagreement_flags)),
        agents_compared=len(responses),
        strategy=strategy_norm,
    )
