import json

from helixsh import cli


def test_cli_audit_sign_and_verify(tmp_path, capsys):
    old_audit = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    key = tmp_path / "key.txt"
    sig = tmp_path / "sig.txt"
    key.write_text("secret\n", encoding="utf-8")
    cli.AUDIT_FILE.write_text('{"timestamp":"x","command":"c","strict":false,"mode":"run","role":"analyst","execution_hash":"h","provenance_params":{}}\n', encoding="utf-8")
    try:
        assert cli.main(["audit-sign", "--key-file", str(key), "--out", str(sig)]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["signature_file"] == str(sig)
        assert cli.main(["audit-verify-signature", "--key-file", str(key), "--signature-file", str(sig)]) == 0
        verify = json.loads(capsys.readouterr().out)
        assert verify["ok"] is True
    finally:
        cli.AUDIT_FILE = old_audit
