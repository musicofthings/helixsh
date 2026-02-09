import json

from helixsh import cli


def test_cli_rbac_check_denied(capsys):
    rc = cli.main(["rbac-check", "--role", "auditor", "--action", "run"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["allowed"] is False


def test_cli_report_writes_file(tmp_path, capsys):
    out = tmp_path / "validation.json"
    rc = cli.main(["report", "--schema-ok", "--cache-percent", "90", "--diagnostics", "ok", "--out", str(out)])
    assert rc == 2
    assert out.exists()
    assert "validation report written" in capsys.readouterr().out
