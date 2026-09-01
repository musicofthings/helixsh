"""Integration tests that execute Nextflow for real.

Every other test in this suite stops at the command string: they assert that
Helixsh assembled the arguments it intended, with ``subprocess`` mocked out.
That leaves the whole execution path -- argv handling, exit-code propagation,
output publishing, resume -- unverified. These tests close that gap by running
the real thing through :func:`helixsh.cli.main`.

They are excluded from the default suite because they need Nextflow (and, for
the nf-core tier, a Docker daemon) and take minutes rather than milliseconds::

    pytest -m integration           # local workflow; needs nextflow + java
    pytest -m integration_nfcore    # real nf-core pipeline; also needs docker
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from helixsh import cli

FIXTURES = Path(__file__).parent / "fixtures"
WORKFLOW = FIXTURES / "count_seqs.nf"

# Two sequences in one file, three in the other, so a wrong result is
# distinguishable from an empty one.
SAMPLES = {
    "sample_a.fasta": ">seq1\nACGT\n>seq2\nTTGA\n",
    "sample_b.fasta": ">seq1\nACGT\n>seq2\nTTGA\n>seq3\nGGCA\n",
}
EXPECTED_COUNTS = {"sample_a.count": "2", "sample_b.count": "3"}


def _require(binary: str) -> None:
    if shutil.which(binary) is None:
        pytest.skip(f"{binary} is not installed; skipping real-execution test")


def _require_docker_daemon() -> None:
    _require("docker")
    try:
        probe = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("docker daemon is not reachable; skipping nf-core test")
    if probe.returncode != 0:
        pytest.skip("docker daemon is not reachable; skipping nf-core test")


@pytest.fixture
def nextflow_env(tmp_path, monkeypatch):
    """Give each test its own working directory.

    Nextflow puts `work/` and `.nextflow.log` beside the process working
    directory, so this is what keeps runs from colliding and from littering
    the repository.

    NXF_HOME is deliberately left alone. It is the framework and plugin
    cache, not run state: pointing it at a per-test directory made every
    test re-download the ~100MB Nextflow distribution, which is slow and
    turns any network blip into a failure.
    """
    _require("nextflow")
    _require("java")
    # The launcher otherwise reaches out to check for a newer release on every
    # invocation, which is slow and fails closed in sandboxed CI.
    monkeypatch.setenv("NXF_DISABLE_CHECK_LATEST", "true")
    monkeypatch.setenv("CAPSULE_LOG", "none")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def reads_dir(nextflow_env) -> Path:
    directory = nextflow_env / "reads"
    directory.mkdir()
    for name, content in SAMPLES.items():
        (directory / name).write_text(content, encoding="utf-8")
    return directory


def _run(workflow: Path, reads: Path, outdir: Path, *extra: str) -> int:
    """Invoke Helixsh exactly as a user would, through its own entry point."""
    return cli.main(
        [
            "run",
            "nf-core",
            str(workflow),
            "--runtime",
            "local",
            "--outdir",
            str(outdir),
            f"--nf-arg=--reads={reads}",
            "--execute",
            *extra,
        ]
    )


@pytest.mark.integration
def test_executes_a_real_workflow_and_publishes_output(nextflow_env, reads_dir):
    """The headline check: a pipeline actually runs and produces real files."""
    outdir = nextflow_env / "published"

    assert _run(WORKFLOW, reads_dir, outdir) == 0

    produced = {path.name: path.read_text(encoding="utf-8").strip()
                for path in sorted(outdir.glob("*.count"))}
    assert produced == EXPECTED_COUNTS


@pytest.mark.integration
def test_propagates_a_pipeline_failure_as_a_nonzero_exit(nextflow_env, reads_dir):
    """A failed process must not be reported as a successful run."""
    outdir = nextflow_env / "published-fail"

    exit_code = _run(WORKFLOW, reads_dir, outdir, "--nf-arg=--fail=true")

    assert exit_code != 0
    assert not list(outdir.glob("*.count"))


@pytest.mark.integration
def test_resume_reuses_the_cached_run(nextflow_env, reads_dir):
    """--resume must reach Nextflow and hit the cache rather than recompute."""
    outdir = nextflow_env / "published-resume"
    assert _run(WORKFLOW, reads_dir, outdir) == 0

    assert _run(WORKFLOW, reads_dir, outdir, "--resume") == 0

    log = (nextflow_env / ".nextflow.log").read_text(encoding="utf-8", errors="replace")
    assert "Cached process" in log, "second run recomputed instead of using the cache"


@pytest.mark.integration
def test_local_runtime_adds_no_profile(nextflow_env, reads_dir, capsys):
    """The local runtime runs against PATH, so it must not request a profile."""
    outdir = nextflow_env / "published-plan"
    cli.main(
        [
            "run", "nf-core", str(WORKFLOW), "--runtime", "local",
            "--outdir", str(outdir), f"--nf-arg=--reads={reads_dir}",
        ]
    )
    planned = [line for line in capsys.readouterr().out.splitlines()
               if line.startswith("[helixsh] planned:")]
    assert planned and "-profile" not in planned[0]


@pytest.mark.integration_nfcore
def test_executes_a_real_nf_core_pipeline(nextflow_env):
    """nf-core/demo under its own test profile, the way a user would run it.

    This is the check that `-profile test,docker` composes correctly against a
    pipeline that is not ours -- the case Nextflow rejects outright when the
    profile arrives as a repeated flag.
    """
    _require_docker_daemon()
    outdir = nextflow_env / "nf-core-results"

    # Pin the pipeline. 1.0.1 sets `process.shell` as a multi-line string,
    # which Nextflow resolves to 'bash\n\nset -e ...' and then cannot launch,
    # failing every task with `.command.run: Permission denied` (exit 126).
    # 1.2.0 uses the list form and declares nextflowVersion '!>=25.10.4',
    # which is what NXF_VER pins in CI.
    exit_code = cli.main(
        [
            "run", "nf-core", "demo",
            "--runtime", "docker",
            "--profile", "test",
            "--outdir", str(outdir),
            "--nf-arg=-r", "--nf-arg=1.2.0",
            "--execute",
        ]
    )

    assert exit_code == 0
    assert list(outdir.rglob("multiqc_report.html")), "no MultiQC report produced"
