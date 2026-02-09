"""Empirical calibration fitting from observed runtime resources."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Observation:
    expected_cpu: float
    observed_cpu: float
    expected_memory_gb: float
    observed_memory_gb: float


@dataclass(frozen=True)
class FittedCalibration:
    cpu_multiplier: float
    memory_multiplier: float
    samples_used: int


def fit_calibration(observations: list[Observation]) -> FittedCalibration:
    if not observations:
        raise ValueError("at least one observation is required")

    valid_samples = [o for o in observations if o.expected_cpu > 0 and o.expected_memory_gb > 0]
    if not valid_samples:
        raise ValueError("observations must include positive expected cpu/memory")

    cpu_ratios = [o.observed_cpu / o.expected_cpu for o in valid_samples]
    mem_ratios = [o.observed_memory_gb / o.expected_memory_gb for o in valid_samples]

    cpu_multiplier = sum(cpu_ratios) / len(cpu_ratios)
    memory_multiplier = sum(mem_ratios) / len(mem_ratios)
    return FittedCalibration(
        cpu_multiplier=cpu_multiplier,
        memory_multiplier=memory_multiplier,
        samples_used=len(valid_samples),
    )


def fit_calibration_from_file(path: str) -> FittedCalibration:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    observations = [Observation(**item) for item in payload]
    return fit_calibration(observations)


def write_calibration(path: str, calibration: FittedCalibration) -> None:
    Path(path).write_text(json.dumps(asdict(calibration), indent=2), encoding="utf-8")
