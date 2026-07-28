"""Failure diagnostics for common bioinformatics pipeline errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureDiagnosis:
    likely_cause: str
    context: str
    options: tuple[str, ...]


def diagnose_failure(process_name: str, exit_code: int, memory_limit_gb: int | None = None) -> FailureDiagnosis:
    if exit_code == 0:
        return FailureDiagnosis("No failure", "Exit code indicates success", tuple())

    if exit_code == 137:
        context = "Likely out-of-memory condition (SIGKILL)"
        if memory_limit_gb is not None:
            context += f" (node limit {memory_limit_gb} GB)"
        return FailureDiagnosis(
            "Out-of-memory",
            context,
            (
                "Increase memory allocation",
                "Reduce parallelism",
                "Switch to a lower-memory tool/profile",
            ),
        )

    if exit_code == 139:
        return FailureDiagnosis(
            "Segmentation fault (SIGSEGV)",
            f"Process {process_name} crashed with SIGSEGV (exit 139)",
            (
                "Check input file integrity (truncated/corrupt BAM/FASTQ?)",
                "Verify container image digest is correct",
                "Try a newer or alternative tool version",
            ),
        )

    if exit_code == 143:
        return FailureDiagnosis(
            "Process killed (SIGTERM/cluster timeout)",
            f"Process {process_name} received SIGTERM (exit 143) — likely wall-time exceeded",
            (
                "Increase wall-time limit in nextflow.config",
                "Split job into smaller batches",
                "Use -resume to restart from the last checkpoint",
            ),
        )

    if exit_code == 127:
        return FailureDiagnosis(
            "Command not found (exit 127)",
            f"Process {process_name} could not locate a required binary",
            (
                "Verify the tool is installed in the container/environment",
                "Check PATH inside the container",
                "Use a digest-pinned container image",
            ),
        )

    if exit_code == 1:
        return FailureDiagnosis(
            "Generic process failure (exit 1)",
            f"Process {process_name} exited with code 1",
            (
                "Inspect work directory stderr/stdout",
                "Re-run with -resume after fix",
                "Enable -with-trace for per-task resource metrics",
            ),
        )

    return FailureDiagnosis(
        "Non-zero process failure",
        f"Process {process_name} exited with code {exit_code}",
        ("Inspect .nextflow.log", "Inspect work directory stderr/stdout", "Re-run with -resume after fix"),
    )
