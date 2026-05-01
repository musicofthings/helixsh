"""Environment diagnostics for helixsh."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    state: str
    details: str


# Nextflow 25.x requires Java 17+; checked via java -version (outputs to stderr)
CHECKS = (
    ("nextflow", ["nextflow", "-version"]),
    # java -version writes to stderr, so we capture both streams
    ("java", ["java", "-version"]),
    ("docker", ["docker", "--version"]),
    ("podman", ["podman", "--version"]),
    ("singularity", ["singularity", "--version"]),
    ("apptainer", ["apptainer", "--version"]),
    ("conda", ["conda", "--version"]),
    ("mamba", ["mamba", "--version"]),
    ("micromamba", ["micromamba", "--version"]),
    ("git", ["git", "--version"]),
)


def run_check(name: str, command: list[str]) -> CheckResult:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return CheckResult(name=name, state="missing", details="binary not found")

    state = "ok" if result.returncode == 0 else "missing"
    # java -version prints to stderr; prefer stdout, fall back to stderr
    raw = result.stdout.strip() or result.stderr.strip() or "not available"
    return CheckResult(name=name, state=state, details=raw.splitlines()[0])


def collect_doctor_results() -> list[CheckResult]:
    return [run_check(name, cmd) for name, cmd in CHECKS]
