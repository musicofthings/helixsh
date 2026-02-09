"""Failure diagnostics for common bioinformatics pipeline errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureDiagnosis:
    likely_cause: str
    context: str
    options: tuple[str, ...]


def diagnose_failure(process_name: str, exit_code: int, memory_limit_gb: int | None = None) -> FailureDiagnosis:
    if exit_code == 137:
        context = "Likely out-of-memory condition"
        if memory_limit_gb is not None:
            context += f" (node limit {memory_limit_gb} GB)"
        options = (
            "Increase memory allocation",
            "Reduce parallelism",
            "Switch to a lower-memory tool/profile",
        )
        return FailureDiagnosis("Out-of-memory", context, options)

    if exit_code != 0:
        return FailureDiagnosis(
            "Non-zero process failure",
            f"Process {process_name} exited with code {exit_code}",
            ("Inspect .nextflow.log", "Inspect work directory stderr/stdout", "Re-run with -resume after fix"),
        )

    return FailureDiagnosis("No failure", "Exit code indicates success", tuple())
