import json

from helixsh import cli
from helixsh.doctor import CheckResult


def test_intent_command_outputs_json(capsys):
    rc = cli.main(["intent", "run rnaseq use docker resume"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["pipeline"] == "nf-core/rnaseq"
    assert payload["resume"] is True


def test_mcp_check_denied(capsys):
    rc = cli.main(["mcp-check", "execute_commands"])
    assert rc == 2
    assert '"mode": "deny"' in capsys.readouterr().out


def test_doctor_json_output(capsys, monkeypatch):
    monkeypatch.setattr(
        cli,
        "collect_doctor_results",
        lambda: [CheckResult(name="nextflow", state="ok", details="version")],
    )

    rc = cli.main(["doctor", "--json"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == [
        {"name": "nextflow", "state": "ok", "details": "version"}
    ]
