import json

from helixsh import cli


def _read_json_output(capsys):
    return json.loads(capsys.readouterr().out)


def test_cli_fit_calibration(tmp_path, capsys):
    obs = tmp_path / "obs.json"
    out = tmp_path / "cal.json"
    obs.write_text('[{"expected_cpu":2,"observed_cpu":4,"expected_memory_gb":4,"observed_memory_gb":8}]', encoding="utf-8")
    rc = cli.main(["fit-calibration", "--observations", str(obs), "--out", str(out)])
    assert rc == 0
    payload = _read_json_output(capsys)
    assert payload["calibration"]["cpu_multiplier"] == 2.0


def test_cli_mcp_execute(tmp_path, capsys):
    old = cli.PROPOSAL_FILE
    cli.PROPOSAL_FILE = tmp_path / "props.jsonl"
    try:
        cli.main(["mcp-propose", "--kind", "claude_plan", "--summary", "s", "--payload", '{"proposed_diff_summary":"x"}'])
        _read_json_output(capsys)

        rc = cli.main(["mcp-execute", "--id", "1"])
        assert rc == 2
        first = _read_json_output(capsys)
        assert first["message"] == "Proposal is not approved"

        cli.main(["mcp-approve", "--id", "1"])
        _read_json_output(capsys)

        rc2 = cli.main(["mcp-execute", "--id", "1"])
        assert rc2 == 0
        second = _read_json_output(capsys)
        assert second["executed"] is True
    finally:
        cli.PROPOSAL_FILE = old


def test_cli_mcp_execute_invalid_claude_payload(tmp_path, capsys):
    old = cli.PROPOSAL_FILE
    cli.PROPOSAL_FILE = tmp_path / "props.jsonl"
    try:
        cli.main(["mcp-propose", "--kind", "claude_plan", "--summary", "s", "--payload", "not-json"])
        _read_json_output(capsys)

        cli.main(["mcp-approve", "--id", "1"])
        _read_json_output(capsys)

        rc = cli.main(["mcp-execute", "--id", "1"])
        assert rc == 2
        payload = _read_json_output(capsys)
        assert payload["message"] == "Invalid claude_plan payload JSON"
    finally:
        cli.PROPOSAL_FILE = old
