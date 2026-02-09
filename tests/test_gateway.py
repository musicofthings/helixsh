from helixsh.gateway import approve_proposal, create_proposal, list_proposals


def test_gateway_proposal_lifecycle(tmp_path):
    store = tmp_path / "props.jsonl"
    p1 = create_proposal(str(store), kind="file_patch", summary="fix", payload="diff")
    assert p1.proposal_id == 1
    assert p1.status == "proposed"
    listed = list_proposals(str(store))
    assert len(listed) == 1
    approved = approve_proposal(str(store), 1)
    assert approved.status == "approved"
