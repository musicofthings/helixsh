import shlex

import pytest

from helixsh.nextflow import HelixshError, RunConfig, build_nextflow_run_command, format_shell_command, normalize_pipeline, normalize_profiles, validate_runtime


def test_normalize_pipeline_defaults_org():
    assert normalize_pipeline("nf-core", "rnaseq") == "nf-core/rnaseq"


def test_normalize_pipeline_accepts_qualified_name():
    assert normalize_pipeline("ignored", "org/pipeline") == "org/pipeline"


def test_validate_runtime_rejects_invalid():
    try:
        validate_runtime("unknown")
    except HelixshError as exc:
        assert "Unsupported runtime" in str(exc)
    else:
        raise AssertionError("expected HelixshError")


def test_validate_runtime_accepts_conda():
    assert validate_runtime("conda") == "conda"


def test_validate_runtime_accepts_kubernetes():
    assert validate_runtime("kubernetes") == "kubernetes"


def test_build_command():
    cfg = RunConfig("nf-core/rnaseq", "docker", "samplesheet.csv", True, ("--max_cpus", "8"))
    assert build_nextflow_run_command(cfg) == [
        "nextflow",
        "run",
        "nf-core/rnaseq",
        "-profile",
        "docker",
        "--input",
        "samplesheet.csv",
        "-resume",
        "--max_cpus",
        "8",
    ]


def test_shell_formatting_quotes_dangerous_tokens():
    cmd = format_shell_command(["nextflow", "run", "nf-core/rnaseq", "--input", "sample sheet.csv"])
    assert "'sample sheet.csv'" in cmd


def test_shell_formatting_round_trips_through_shlex():
    # The audit record must parse back to exactly the argv that was executed.
    argv = ["nextflow", "run", "nf-core/rnaseq", "--input", "#a", "-c", "b\\c", "-r", "~dev", "-x", "f?.csv"]
    assert shlex.split(format_shell_command(argv)) == argv


# ─────────────────────── profile composition ──────────────────────────────────

def test_extra_profiles_compose_into_one_profile_argument():
    # Nextflow accepts -profile exactly once, so every name must arrive in a
    # single comma-separated value.
    cmd = build_nextflow_run_command(
        RunConfig(pipeline="nf-core/rnaseq", profile="docker", profiles=("test",))
    )
    assert cmd.count("-profile") == 1
    assert cmd[cmd.index("-profile") + 1] == "test,docker"


def test_runtime_profile_is_last_so_it_wins():
    # Later profiles override earlier ones in Nextflow; the container choice
    # must beat whatever a pipeline profile such as nf-core's `test` sets.
    cmd = build_nextflow_run_command(
        RunConfig(pipeline="p", profile="singularity", profiles=("test", "crick"))
    )
    assert cmd[cmd.index("-profile") + 1] == "test,crick,singularity"


def test_local_runtime_requests_no_profile():
    cmd = build_nextflow_run_command(RunConfig(pipeline="/wf/main.nf", profile="local"))
    assert "-profile" not in cmd
    assert "-with-conda" not in cmd
    assert cmd == ["nextflow", "run", "/wf/main.nf"]


def test_conda_keeps_with_conda_and_still_accepts_profiles():
    cmd = build_nextflow_run_command(
        RunConfig(pipeline="p", profile="conda", profiles=("test",))
    )
    assert "-with-conda" in cmd
    assert cmd[cmd.index("-profile") + 1] == "test"


def test_kubernetes_contributes_no_profile_name_of_its_own():
    cmd = build_nextflow_run_command(
        RunConfig(pipeline="p", profile="kubernetes", profiles=("test",))
    )
    assert cmd[cmd.index("-profile") + 1] == "test"


def test_normalize_profiles_accepts_repeated_and_comma_forms():
    assert normalize_profiles(["test", "crick"]) == ("test", "crick")
    assert normalize_profiles(["test,crick"]) == ("test", "crick")
    assert normalize_profiles(["test, crick", "test"]) == ("test", "crick")
    assert normalize_profiles(None) == ()
    assert normalize_profiles([]) == ()


@pytest.mark.parametrize(
    "bad",
    ["evil; rm -rf /", "a b", "-flag", "1abc", "with-dash", "quote'name", ""],
)
def test_normalize_profiles_rejects_names_nextflow_could_not_resolve(bad):
    if bad == "":
        # An empty segment is skipped rather than rejected, so a trailing
        # comma in a copied command does not become an error.
        assert normalize_profiles([bad]) == ()
        return
    with pytest.raises(HelixshError):
        normalize_profiles([bad])


def test_local_is_a_supported_runtime():
    assert validate_runtime("local") == "local"
