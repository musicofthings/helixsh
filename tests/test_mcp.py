from helixsh.mcp import evaluate_capability


def test_execute_commands_denied():
    d = evaluate_capability("execute_commands")
    assert d.allowed is False
    assert d.mode == "deny"


def test_modify_files_proposal_only():
    d = evaluate_capability("modify_files")
    assert d.allowed is True
    assert d.mode == "proposal_only"
