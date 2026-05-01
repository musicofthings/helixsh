"""Execution lifecycle context helpers."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ExecutionContext:
    execution_id: str
    working_dir: str
    container_digest: str | None
    input_hash: str
    agent: str | None
    timestamp: str


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_inputs(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(paths):
        p = Path(file_path)
        digest.update(str(p.resolve()).encode("utf-8"))
        digest.update(sha256_file(str(p)).encode("utf-8"))
    return digest.hexdigest()


def create_execution_context(
    *,
    working_dir: str,
    input_files: list[str],
    agent: str | None = None,
    container_digest: str | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        execution_id=str(uuid.uuid4()),
        working_dir=working_dir,
        container_digest=container_digest,
        input_hash=hash_inputs(input_files) if input_files else hashlib.sha256(b"").hexdigest(),
        agent=agent,
        timestamp=datetime.now(UTC).isoformat(),
    )


def file_size_bytes(path: str) -> int:
    return Path(path).stat().st_size
