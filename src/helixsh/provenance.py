"""Provenance and reproducibility hash helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ProvenanceRecord:
    execution_hash: str
    command: str
    params: dict


def compute_execution_hash(command: str, params: dict) -> str:
    canonical = json.dumps({"command": command, "params": params}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_provenance_record(command: str, params: dict) -> ProvenanceRecord:
    return ProvenanceRecord(execution_hash=compute_execution_hash(command, params), command=command, params=params)
