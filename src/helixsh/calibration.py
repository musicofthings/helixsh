"""Resource calibration model support."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CalibrationProfile:
    cpu_multiplier: float
    memory_multiplier: float


def load_calibration(path: str) -> CalibrationProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return CalibrationProfile(
        cpu_multiplier=float(payload.get("cpu_multiplier", 1.0)),
        memory_multiplier=float(payload.get("memory_multiplier", 1.0)),
    )
