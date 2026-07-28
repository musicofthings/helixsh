import json

from helixsh.arbitration import arbitrate
from helixsh.compliance import evaluate_compliance
from helixsh.haps import run_agent_task


def test_haps_variant_classification_response_shape():
    response = run_agent_task("claude", "opus-4.6", "variant_classification", "BRCA1:c.68_69delAG")
    assert response.status == "success"
    assert response.result["classification"] == "Pathogenic"
    assert response.acmg_evidence == {"PVS1": True, "PM2": True, "PP3": True}


def test_arbitration_detects_disagreement():
    a = run_agent_task("claude", "m", "variant_classification", "BRCA1:c.68_69delAG")
    b = run_agent_task("codex", "m", "variant_classification", "unknown")
    result = arbitrate([a, b], strategy="majority")
    assert result.agents_compared == 2
    assert "LOW_AGENT_AGREEMENT" in result.disagreement_flags


def test_compliance_manual_review_triggers():
    result = evaluate_compliance(
        images=["ghcr.io/tool:latest"],
        agreement_score=0.5,
        confidences=[0.6, 0.61],
        evidence_conflict=True,
    )
    assert result.ok is False
    assert result.requires_manual_review is True
    assert "UNPINNED_CONTAINER_DIGEST" in result.flags
