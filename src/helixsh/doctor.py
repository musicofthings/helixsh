"""Environment diagnostics for helixsh."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

CHECK_TIMEOUT_SECONDS = 10


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
    ("docker", ["docker", "info", "--format", "Docker server {{.ServerVersion}}"]),
    ("kubectl", ["kubectl", "version", "--client"]),
    ("kubernetes", ["kubectl", "cluster-info"]),
    ("podman", ["podman", "--version"]),
    ("singularity", ["singularity", "--version"]),
    ("apptainer", ["apptainer", "--version"]),
    ("conda", ["conda", "--version"]),
    ("mamba", ["mamba", "--version"]),
    ("micromamba", ["micromamba", "--version"]),
    ("git", ["git", "--version"]),
)


def _first_line(*candidates: str) -> str:
    """Return the first non-empty line across the given streams, in order."""
    for candidate in candidates:
        stripped = candidate.strip()
        if stripped:
            return stripped.splitlines()[0]
    return "not available"


def run_check(name: str, command: list[str]) -> CheckResult:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return CheckResult(name=name, state="missing", details="binary not found")
    except OSError as error:
        # Anything else the exec itself can fail with, most often EACCES: a
        # directory on PATH the user cannot read makes execvp report a
        # permission error rather than a missing file. Unhandled, one such
        # entry took down the whole doctor run -- every other check with it --
        # and the desktop app reported the backend as unavailable.
        return CheckResult(name=name, state="missing", details=f"could not be run: {error.strerror}")
    except subprocess.TimeoutExpired:
        # A timeout is not the same as an absent binary: the tool is installed
        # but unresponsive, which points at a different fix.
        return CheckResult(
            name=name,
            state="timeout",
            details=f"check timed out after {CHECK_TIMEOUT_SECONDS}s",
        )

    if result.returncode == 0:
        # java -version prints to stderr; prefer stdout, fall back to stderr
        return CheckResult(name=name, state="ok", details=_first_line(result.stdout, result.stderr))

    # On failure the diagnosis lives on stderr. `docker info --format` still
    # prints a half-filled template to stdout when the daemon is unreachable,
    # so preferring stdout here would report "Docker server" and discard the
    # actual reason the check failed.
    return CheckResult(name=name, state="missing", details=_first_line(result.stderr, result.stdout))


def collect_doctor_results() -> list[CheckResult]:
    """Every check, including the cloud ones that run no command at all.

    Credential discovery is pure inspection of environment variables and file
    locations, so it is appended rather than run through the pool: there is
    nothing to time out and nothing to wait on.
    """
    # The checks are independent and each can block for CHECK_TIMEOUT_SECONDS
    # (`kubectl cluster-info` against an unreachable cluster, a stalled Docker
    # socket). Run serially, the worst case was the sum of every timeout, which
    # overran the desktop app's IPC budget on a machine with no cluster. In
    # parallel it is bounded by the slowest single check.
    # Imported here rather than at module scope: cloud_credentials reuses
    # CheckResult from this module, so a top-level import would be a cycle.
    from helixsh.cloud_credentials import collect_cloud_credentials

    with ThreadPoolExecutor(max_workers=max(1, len(CHECKS))) as pool:
        results = list(pool.map(lambda check: run_check(*check), CHECKS))
    return results + collect_cloud_credentials()
