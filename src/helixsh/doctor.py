"""Environment diagnostics for helixsh."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    state: str
    details: str


CHECKS = (
    ("nextflow", ["nextflow", "-version"]),
    ("docker", ["docker", "info", "--format", "Docker server {{.ServerVersion}}"]),
    ("kubectl", ["kubectl", "version", "--client"]),
    ("kubernetes", ["kubectl", "cluster-info"]),
    ("podman", ["podman", "--version"]),
    ("singularity", ["singularity", "--version"]),
    ("apptainer", ["apptainer", "--version"]),
)


def run_check(name: str, command: list[str]) -> CheckResult:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return CheckResult(name=name, state="missing", details="binary not found")
    except subprocess.TimeoutExpired:
        return CheckResult(name=name, state="missing", details="check timed out")

    state = "ok" if result.returncode == 0 else "missing"
    raw = result.stdout.strip() or result.stderr.strip() or "not available"
    return CheckResult(name=name, state=state, details=raw.splitlines()[0])


def collect_doctor_results() -> list[CheckResult]:
    return [run_check(name, cmd) for name, cmd in CHECKS]
