import subprocess

from helixsh.executor import build_posix_exec, run_posix_exec


def test_build_posix_exec_wraps_command():
    wrapped = build_posix_exec(["nextflow", "run", "nf-core/rnaseq"])
    assert wrapped.startswith("exec sh -c")
    assert "nextflow run nf-core/rnaseq" in wrapped


def test_build_posix_exec_quotes_shell_metacharacters():
    wrapped = build_posix_exec(["nextflow", "run", "nf-core/rnaseq", "--input", "#notes.csv"])
    assert "'#notes.csv'" in wrapped


def test_run_posix_exec_passes_argv_through_without_a_shell(monkeypatch):
    seen = {}

    def fake_run(command, check):
        seen["command"] = command
        seen["check"] = check
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Arguments a shell would mangle must reach the child verbatim.
    argv = ["nextflow", "run", "nf-core/rnaseq", "--input", "#a", "-c", "b\\c", "-r", "~dev"]
    assert run_posix_exec(argv) == 0
    assert seen["command"] == argv
    assert seen["check"] is False
