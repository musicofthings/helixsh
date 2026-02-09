"""Bioinformatics tool resource estimation helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceEstimate:
    tool: str
    assay: str
    samples: int
    cpu_per_sample: int
    memory_gb_per_sample: int
    total_cpu: int
    total_memory_gb: int


DEFAULTS = {
    "star": (8, 32),
    "salmon": (2, 8),
    "bwa": (8, 16),
    "gatk": (4, 16),
}


def estimate_resources(tool: str, assay: str, samples: int, cpu_multiplier: float = 1.0, memory_multiplier: float = 1.0) -> ResourceEstimate:
    tool_norm = tool.strip().lower()
    assay_norm = assay.strip().lower()
    if samples <= 0:
        raise ValueError("samples must be > 0")

    cpu, mem = DEFAULTS.get(tool_norm, (2, 4))

    if assay_norm in {"wgs", "wes"} and tool_norm in {"bwa", "gatk"}:
        mem += 8
    if assay_norm == "rnaseq" and tool_norm == "star":
        mem += 8

    cpu_adj = max(1, int(round(cpu * cpu_multiplier)))
    mem_adj = max(1, int(round(mem * memory_multiplier)))

    return ResourceEstimate(
        tool=tool_norm,
        assay=assay_norm,
        samples=samples,
        cpu_per_sample=cpu_adj,
        memory_gb_per_sample=mem_adj,
        total_cpu=cpu_adj * samples,
        total_memory_gb=mem_adj * samples,
    )
