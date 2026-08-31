import subprocess
import time

from helixsh import doctor
from helixsh.doctor import CheckResult, collect_doctor_results, run_check


def test_run_check_handles_missing_binary():
    result = run_check("missing", ["definitely-not-a-real-binary", "--version"])
    assert result == CheckResult(name="missing", state="missing", details="binary not found")


def test_run_check_reports_stderr_when_the_command_fails(monkeypatch):
    # `docker info --format` prints a half-filled template to stdout even when
    # the daemon is unreachable; the real diagnosis is on stderr.
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["docker"],
            returncode=1,
            stdout="Docker server \n",
            stderr="failed to connect to the docker API at unix:///var/run/docker.sock\n",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_check("docker", ["docker", "info"])

    assert result.state == "missing"
    assert result.details == "failed to connect to the docker API at unix:///var/run/docker.sock"


def test_run_check_prefers_stdout_on_success(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["docker"], returncode=0, stdout="Docker server 27.0.3\n", stderr="warning\n"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert run_check("docker", ["docker", "info"]).details == "Docker server 27.0.3"


def test_run_check_distinguishes_a_timeout_from_a_missing_binary(monkeypatch):
    monkeypatch.setattr(doctor, "CHECK_TIMEOUT_SECONDS", 1)
    result = run_check("kubernetes", ["sleep", "5"])

    assert result.state == "timeout"
    assert "timed out" in result.details


def test_collect_doctor_results_runs_checks_in_parallel(monkeypatch):
    # Serially this is 4s, which is the behaviour that overran the desktop
    # app's IPC budget. In parallel it is bounded by one timeout.
    monkeypatch.setattr(doctor, "CHECK_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(doctor, "CHECKS", tuple((f"slow{i}", ["sleep", "5"]) for i in range(4)))

    start = time.monotonic()
    results = collect_doctor_results()
    elapsed = time.monotonic() - start

    assert elapsed < 3
    assert [result.name for result in results] == ["slow0", "slow1", "slow2", "slow3"]
    assert all(result.state == "timeout" for result in results)
