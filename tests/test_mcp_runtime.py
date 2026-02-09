from helixsh.gateway import create_proposal
from helixsh.mcp_runtime import execute_approved_proposal


def test_execute_approved_proposal_requires_approval(tmp_path):
    store = tmp_path / "props.jsonl"
    p = create_proposal(str(store), kind="claude_plan", summary="s", payload='{"proposed_diff_summary":"x"}')
    r = execute_approved_proposal(str(store), p.proposal_id)
    assert r.executed is False
