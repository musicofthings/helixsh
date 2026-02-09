import json

from helixsh import cli


def test_run_writes_execution_hash_and_role(tmp_path):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    try:
        rc = cli.main(["--role", "analyst", "run", "nf-core", "rnaseq"])
        assert rc == 0
        line = cli.AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()[-1]
        event = json.loads(line)
        assert event["role"] == "analyst"
        assert event["execution_hash"]
    finally:
        cli.AUDIT_FILE = old


def test_audit_verify_detects_missing_hash(tmp_path, capsys):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    cli.AUDIT_FILE.write_text('{"timestamp":"x","command":"c"}\n', encoding="utf-8")
    try:
        rc = cli.main(["audit-verify"])
        assert rc == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload["missing_hash"] == 1
    finally:
        cli.AUDIT_FILE = old
