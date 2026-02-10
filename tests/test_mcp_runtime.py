from helixsh.gateway import approve_proposal, create_proposal
from helixsh.mcp_runtime import execute_approved_proposal


def test_execute_approved_proposal_requires_approval(tmp_path):
    store = tmp_path / "props.jsonl"
    p = create_proposal(str(store), kind="claude_plan", summary="s", payload='{"proposed_diff_summary":"x"}')
    r = execute_approved_proposal(str(store), p.proposal_id)
    assert r.executed is False


def test_execute_approved_proposal_rejects_invalid_claude_payload(tmp_path):
    store = tmp_path / "props.jsonl"
    p = create_proposal(str(store), kind="claude_plan", summary="s", payload="not-json")
    approve_proposal(str(store), p.proposal_id)

    r = execute_approved_proposal(str(store), p.proposal_id)

    assert r.executed is False
    assert r.message == "Invalid claude_plan payload JSON"
