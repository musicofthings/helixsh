import json

from helixsh import cli


def test_cli_roadmap_status_json(capsys):
    rc = cli.main(["roadmap-status"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 4
    assert payload[0]["phase"].startswith("Phase 1")
