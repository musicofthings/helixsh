import json

from helixsh import cli


def test_run_offline_includes_flag(tmp_path, capsys):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    try:
        rc = cli.main(["run", "nf-core", "rnaseq", "--offline"])
        assert rc == 0
        out = capsys.readouterr().out
        assert " -offline" in out or "-offline " in out
    finally:
        cli.AUDIT_FILE = old


def test_offline_check_cli(tmp_path, capsys):
    (tmp_path / "schemas").mkdir()
    (tmp_path / "containers").mkdir()
    (tmp_path / "nextflow_assets").mkdir()
    rc = cli.main(["offline-check", "--cache-root", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is True
