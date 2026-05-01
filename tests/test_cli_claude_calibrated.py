import json

from helixsh import cli


def test_cli_resource_estimate_with_calibration(tmp_path, capsys):
    cal = tmp_path / "cal.json"
    cal.write_text('{"cpu_multiplier":2.0,"memory_multiplier":1.5}', encoding="utf-8")
    rc = cli.main(["resource-estimate", "--tool", "salmon", "--assay", "rnaseq", "--samples", "2", "--calibration", str(cal)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cpu_per_sample"] == 4
    assert payload["memory_gb_per_sample"] == 12


def test_cli_claude_plan_creates_proposal(tmp_path, capsys):
    old = cli.PROPOSAL_FILE
    cli.PROPOSAL_FILE = tmp_path / "props.jsonl"
    try:
        rc = cli.main(["claude-plan", "--prompt", "fix schema mismatch"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["proposal"]["kind"] == "claude_plan"
    finally:
        cli.PROPOSAL_FILE = old
