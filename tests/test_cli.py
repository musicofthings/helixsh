from pathlib import Path

from helixsh import cli


def test_run_dry_run_writes_audit(tmp_path, capsys):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    try:
        rc = cli.main(["run", "nf-core", "rnaseq", "--runtime", "docker", "--resume", "--nf-arg=--max_cpus", "--nf-arg", "8"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "nextflow run nf-core/rnaseq -profile docker -resume --max_cpus 8" in out
        assert cli.AUDIT_FILE.exists()
    finally:
        cli.AUDIT_FILE = old


def test_explain_last_without_audit(capsys, tmp_path):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "missing.jsonl"
    try:
        rc = cli.main(["explain", "last"])
        assert rc == 0
        assert "No previous helixsh audit events found" in capsys.readouterr().out
    finally:
        cli.AUDIT_FILE = old
