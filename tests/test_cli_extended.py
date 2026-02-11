import json

from helixsh import cli


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
