"""SQLite-backed provenance store for helixsh executions."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS executions (
  id TEXT PRIMARY KEY,
  command TEXT NOT NULL,
  workflow TEXT,
  agent TEXT,
  model TEXT,
  status TEXT,
  start_time DATETIME,
  end_time DATETIME,
  container_digest TEXT,
  input_hash TEXT,
  output_hash TEXT,
  exit_code INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inputs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  execution_id TEXT,
  file_path TEXT,
  sha256 TEXT,
  size_bytes INTEGER,
  FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS containers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  execution_id TEXT,
  image_name TEXT,
  image_digest TEXT,
  runtime TEXT,
  version TEXT,
  FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  execution_id TEXT,
  agent_name TEXT,
  model TEXT,
  reasoning TEXT,
  confidence REAL,
  execution_time_ms INTEGER,
  raw_output TEXT,
  FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS acmg_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  execution_id TEXT,
  rule_code TEXT,
  triggered BOOLEAN,
  strength TEXT,
  explanation TEXT,
  FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  execution_id TEXT,
  artifact_type TEXT,
  path TEXT,
  sha256 TEXT,
  FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  execution_id TEXT,
  event_type TEXT,
  message TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


def create_execution(
    db_path: str,
    *,
    execution_id: str,
    command: str,
    workflow: str | None,
    agent: str | None,
    model: str | None,
    status: str,
    start_time: str,
    container_digest: str | None,
    input_hash: str,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO executions
            (id, command, workflow, agent, model, status, start_time, container_digest, input_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (execution_id, command, workflow, agent, model, status, start_time, container_digest, input_hash),
        )


def finish_execution(
    db_path: str,
    *,
    execution_id: str,
    status: str,
    end_time: str,
    output_hash: str | None,
    exit_code: int | None,
) -> None:
    with _connect(db_path) as conn:
        updated = conn.execute(
            """
            UPDATE executions
            SET status = ?, end_time = ?, output_hash = ?, exit_code = ?
            WHERE id = ?
            """,
            (status, end_time, output_hash, exit_code, execution_id),
        )
        if updated.rowcount == 0:
            raise ValueError(f"Execution id not found: {execution_id}")


def insert_input(db_path: str, *, execution_id: str, file_path: str, sha256: str, size_bytes: int) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO inputs (execution_id, file_path, sha256, size_bytes) VALUES (?, ?, ?, ?)",
            (execution_id, file_path, sha256, size_bytes),
        )


def insert_container(db_path: str, *, execution_id: str, image_name: str, image_digest: str | None, runtime: str, version: str | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO containers (execution_id, image_name, image_digest, runtime, version) VALUES (?, ?, ?, ?, ?)",
            (execution_id, image_name, image_digest, runtime, version),
        )


def insert_agent(
    db_path: str,
    *,
    execution_id: str,
    agent_name: str,
    model: str,
    reasoning: str,
    confidence: float,
    execution_time_ms: int,
    raw_output: str,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agents (execution_id, agent_name, model, reasoning, confidence, execution_time_ms, raw_output)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (execution_id, agent_name, model, reasoning, confidence, execution_time_ms, raw_output),
        )


def insert_acmg_evidence(
    db_path: str,
    *,
    execution_id: str,
    rule_code: str,
    triggered: bool,
    strength: str,
    explanation: str,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO acmg_evidence (execution_id, rule_code, triggered, strength, explanation)
            VALUES (?, ?, ?, ?, ?)
            """,
            (execution_id, rule_code, int(triggered), strength, explanation),
        )


def insert_artifact(db_path: str, *, execution_id: str, artifact_type: str, path: str, sha256: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO artifacts (execution_id, artifact_type, path, sha256) VALUES (?, ?, ?, ?)",
            (execution_id, artifact_type, path, sha256),
        )


def add_audit_event(db_path: str, *, execution_id: str, event_type: str, message: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_events (execution_id, event_type, message) VALUES (?, ?, ?)",
            (execution_id, event_type, message),
        )


def get_execution_bundle(db_path: str, execution_id: str) -> dict[str, Any]:
    with _connect(db_path) as conn:
        execution = conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
        if execution is None:
            raise ValueError(f"Execution id not found: {execution_id}")

        def rows(query: str) -> list[dict[str, Any]]:
            return [dict(r) for r in conn.execute(query, (execution_id,)).fetchall()]

        return {
            "execution": dict(execution),
            "inputs": rows("SELECT * FROM inputs WHERE execution_id = ? ORDER BY id"),
            "containers": rows("SELECT * FROM containers WHERE execution_id = ? ORDER BY id"),
            "agents": rows("SELECT * FROM agents WHERE execution_id = ? ORDER BY id"),
            "acmg_evidence": rows("SELECT * FROM acmg_evidence WHERE execution_id = ? ORDER BY id"),
            "artifacts": rows("SELECT * FROM artifacts WHERE execution_id = ? ORDER BY id"),
            "audit_events": rows("SELECT * FROM audit_events WHERE execution_id = ? ORDER BY id"),
        }
