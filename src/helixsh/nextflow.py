"""Deterministic Nextflow command composition and validation."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# conda enables Nextflow -with-conda; kubernetes uses a validated nf-k8s config.
SUPPORTED_RUNTIMES = {
    "docker",
    "podman",
    "singularity",
    "apptainer",
    "conda",
    "kubernetes",
}


class HelixshError(ValueError):
    """Raised for user-facing validation errors."""


@dataclass(frozen=True)
class RunConfig:
    pipeline: str
    profile: str
    input_file: str | None = None
    resume: bool = False
    extra_args: tuple[str, ...] = ()
    outdir: str | None = None
    config_file: str | None = None


def normalize_pipeline(org: str, pipeline: str) -> str:
    pipeline = pipeline.strip()
    if not pipeline:
        raise HelixshError("Pipeline name cannot be empty.")
    if "/" in pipeline:
        return pipeline
    if not org.strip():
        raise HelixshError("Pipeline org cannot be empty when pipeline has no namespace.")
    return f"{org.strip()}/{pipeline}"


def validate_runtime(runtime: str) -> str:
    runtime = runtime.strip().lower()
    if runtime not in SUPPORTED_RUNTIMES:
        options = ", ".join(sorted(SUPPORTED_RUNTIMES))
        raise HelixshError(f"Unsupported runtime '{runtime}'. Supported: {options}.")
    return runtime


def validate_input_file(input_file: str | None) -> str | None:
    if input_file is None:
        return None
    path = Path(input_file)
    if not path.exists():
        raise HelixshError(f"Input file not found: {input_file}")
    return input_file


def build_nextflow_run_command(config: RunConfig) -> list[str]:
    cmd: list[str] = ["nextflow"]
    if config.config_file:
        cmd.extend(["-c", config.config_file])
    cmd.extend(["run", config.pipeline])

    # Conda and Kubernetes are executors, not nf-core profiles.
    if config.profile == "conda":
        cmd.append("-with-conda")
    elif config.profile != "kubernetes":
        cmd.extend(["-profile", config.profile])
    if config.input_file:
        cmd.extend(["--input", config.input_file])
    if config.outdir:
        cmd.extend(["--outdir", config.outdir])
    if config.resume:
        cmd.append("-resume")
    cmd.extend(config.extra_args)
    return cmd


def format_shell_command(args: Iterable[str]) -> str:
    """Render a shell-safe command string suitable for audit logs.

    Quoting is delegated to :func:`shlex.quote` so the rendered string is a
    faithful record of the argv it came from. A hand-rolled deny-list missed
    ``#``, ``\\``, ``~`` and ``?``, which let an audited command differ from
    the one a shell would actually run.
    """
    return " ".join(shlex.quote(arg) for arg in args)
