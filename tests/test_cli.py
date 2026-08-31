import json
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


def test_run_blocks_execution_when_preflight_fails(tmp_path, capsys, monkeypatch):
    workflow = tmp_path / "main.nf"
    workflow.write_text("process ALIGN { cpus 2 }", encoding="utf-8")
    executed = False
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"

    def fake_run_posix_exec(_command):
        nonlocal executed
        executed = True
        return 0

    try:
        monkeypatch.setattr(cli, "run_posix_exec", fake_run_posix_exec)
        rc = cli.main(["run", "nf-core", "rnaseq", "--workflow", str(workflow), "--execute"])

        assert rc == 2
        assert executed is False
        assert cli.AUDIT_FILE.exists()
        assert "execution blocked: preflight validation failed" in capsys.readouterr().out
    finally:
        cli.AUDIT_FILE = old


def test_run_uses_posix_boundary_after_successful_preflight(tmp_path, monkeypatch):
    workflow = tmp_path / "main.nf"
    workflow.write_text("process ALIGN { container 'image@sha256:abc' }", encoding="utf-8")
    commands = []
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"

    def fake_run_posix_exec(command):
        commands.append(command)
        return 0

    try:
        monkeypatch.setattr(cli, "run_posix_exec", fake_run_posix_exec)
        rc = cli.main(["run", "nf-core", "rnaseq", "--workflow", str(workflow), "--execute"])

        assert rc == 0
        assert commands == [["nextflow", "run", "nf-core/rnaseq", "-profile", "docker"]]
    finally:
        cli.AUDIT_FILE = old


def test_run_always_preflights_even_without_optional_inputs(tmp_path, capsys, monkeypatch):
    # A bare run used to skip preflight entirely because no optional input was
    # passed; the runtime check must always be present.
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    monkeypatch.setattr(cli, "run_posix_exec", lambda _command: 0)
    try:
        rc = cli.main(["run", "nf-core", "rnaseq", "--runtime", "docker"])
        assert rc == 0
        line = next(
            line for line in capsys.readouterr().out.splitlines()
            if line.startswith("[helixsh] preflight: ")
        )
        payload = json.loads(line.removeprefix("[helixsh] preflight: "))
        assert payload["ok"] is True
        assert payload["checks"]["runtime"]["runtime"] == "docker"
    finally:
        cli.AUDIT_FILE = old
