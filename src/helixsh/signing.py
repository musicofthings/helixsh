"""Simple audit signing helpers for artifact integrity."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path


def read_key(path: str) -> bytes:
    key = Path(path).read_bytes().strip()
    if not key:
        raise ValueError("Signing key is empty")
    return key


def sign_bytes(data: bytes, key: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def sign_file(path: str, key_path: str) -> str:
    data = Path(path).read_bytes()
    key = read_key(key_path)
    return sign_bytes(data, key)


def verify_file_signature(path: str, key_path: str, expected_hex: str) -> bool:
    actual = sign_file(path, key_path)
    return hmac.compare_digest(actual, expected_hex.strip())
