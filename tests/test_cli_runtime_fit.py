import json

from helixsh import cli


def test_cli_fit_calibration(tmp_path, capsys):
    obs = tmp_path / "obs.json"
    out = tmp_path / "cal.json"
    obs.write_text('[{"expected_cpu":2,"observed_cpu":4,"expected_memory_gb":4,"observed_memory_gb":8}]', encoding="utf-8")
    rc = cli.main(["fit-calibration", "--observations", str(obs), "--out", str(out)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["calibration"]["cpu_multiplier"] == 2.0


def test_cli_mcp_execute(tmp_path, capsys):
    old = cli.PROPOSAL_FILE
    cli.PROPOSAL_FILE = tmp_path / "props.jsonl"
    try:
        cli.main(["mcp-propose", "--kind", "claude_plan", "--summary", "s", "--payload", '{"proposed_diff_summary":"x"}'])
        rc = cli.main(["mcp-execute", "--id", "1"])
        assert rc == 2
        cli.main(["mcp-approve", "--id", "1"])
        rc2 = cli.main(["mcp-execute", "--id", "1"])
        assert rc2 == 0
    finally:
        cli.PROPOSAL_FILE = old



def test_cli_mcp_execute_invalid_claude_payload(tmp_path, capsys):
    old = cli.PROPOSAL_FILE
    cli.PROPOSAL_FILE = tmp_path / "props.jsonl"
    try:
        cli.main(["mcp-propose", "--kind", "claude_plan", "--summary", "s", "--payload", "not-json"])
        capsys.readouterr()
        cli.main(["mcp-approve", "--id", "1"])
        capsys.readouterr()
        rc = cli.main(["mcp-execute", "--id", "1"])
        assert rc == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload["message"] == "Invalid claude_plan payload JSON"
    finally:
        cli.PROPOSAL_FILE = old
