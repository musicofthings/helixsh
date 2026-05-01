from helixsh.signing import sign_bytes, verify_file_signature


def test_sign_bytes_stable():
    sig1 = sign_bytes(b"abc", b"key")
    sig2 = sign_bytes(b"abc", b"key")
    assert sig1 == sig2


def test_verify_file_signature(tmp_path):
    data = tmp_path / "audit.log"
    key = tmp_path / "key.txt"
    sig = tmp_path / "sig.txt"
    data.write_text("line\n", encoding="utf-8")
    key.write_text("secret\n", encoding="utf-8")

    from helixsh.signing import sign_file

    sig.write_text(sign_file(str(data), str(key)) + "\n", encoding="utf-8")
    assert verify_file_signature(str(data), str(key), sig.read_text(encoding="utf-8")) is True
