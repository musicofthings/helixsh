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


def test_strict_execute_requires_yes(capsys, tmp_path):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    try:
        rc = cli.main(["--strict", "run", "nf-core", "rnaseq", "--execute"])
        assert rc == 2
        assert "requires explicit confirmation via --yes" in capsys.readouterr().out
    finally:
        cli.AUDIT_FILE = old


def test_explain_last_handles_empty_audit(capsys, tmp_path):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    cli.AUDIT_FILE.write_text("\n", encoding="utf-8")
    try:
        rc = cli.main(["explain", "last"])
        assert rc == 0
        assert "No previous helixsh audit events found" in capsys.readouterr().out
    finally:
        cli.AUDIT_FILE = old


def test_strict_after_subcommand_is_accepted(capsys, tmp_path):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    try:
        rc = cli.main(["run", "--strict", "nf-core", "rnaseq"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "strict mode active" in out
    finally:
        cli.AUDIT_FILE = old
