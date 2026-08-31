"""Deterministic Nextflow command composition and validation."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# conda enables Nextflow -with-conda; kubernetes uses a validated nf-k8s
# config; local runs the workflow with whatever is already on PATH, for
# workstations and module-based HPC environments.
SUPPORTED_RUNTIMES = {
    "docker",
    "podman",
    "singularity",
    "apptainer",
    "conda",
    "kubernetes",
    "local",
}

# Runtimes that are executors or environment switches rather than Nextflow
# profiles, so they contribute no name to -profile.
_NON_PROFILE_RUNTIMES = {"conda", "kubernetes", "local"}

# Nextflow profile names are Groovy config block identifiers.
PROFILE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
    # Additional Nextflow profiles composed with the runtime, e.g. ("test",)
    # for an nf-core test run or an institutional profile.
    profiles: tuple[str, ...] = ()


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


def normalize_profiles(values: Iterable[str] | None) -> tuple[str, ...]:
    """Split and validate requested profile names, preserving order.

    Accepts repeated flags and comma-separated lists interchangeably, because
    Nextflow itself only accepts the comma form and users copy both from
    pipeline docs.
    """
    if not values:
        return ()
    names: list[str] = []
    for value in values:
        for name in str(value).split(","):
            name = name.strip()
            if not name:
                continue
            if not PROFILE_RE.match(name):
                raise HelixshError(
                    f"Invalid Nextflow profile name '{name}'. "
                    "Profile names may contain letters, digits and underscores."
                )
            if name not in names:
                names.append(name)
    return tuple(names)


def compose_profiles(config: RunConfig) -> list[str]:
    """Return the ordered profile names for a single -profile argument.

    Nextflow rejects a repeated -profile flag outright, so every profile has
    to arrive as one comma-separated value. The runtime goes last because
    later profiles win in Nextflow, and the container choice should override
    whatever a pipeline profile such as nf-core's `test` sets.
    """
    names = [name for name in config.profiles]
    if config.profile not in _NON_PROFILE_RUNTIMES and config.profile not in names:
        names.append(config.profile)
    return names


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

    # Conda is an environment switch, not an nf-core profile; kubernetes and
    # local contribute no profile name of their own.
    if config.profile == "conda":
        cmd.append("-with-conda")
    profiles = compose_profiles(config)
    if profiles:
        cmd.extend(["-profile", ",".join(profiles)])
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
