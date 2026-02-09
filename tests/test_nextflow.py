from helixsh.nextflow import HelixshError, RunConfig, build_nextflow_run_command, format_shell_command, normalize_pipeline, validate_runtime


def test_normalize_pipeline_defaults_org():
    assert normalize_pipeline("nf-core", "rnaseq") == "nf-core/rnaseq"


def test_normalize_pipeline_accepts_qualified_name():
    assert normalize_pipeline("ignored", "org/pipeline") == "org/pipeline"


def test_validate_runtime_rejects_invalid():
    try:
        validate_runtime("conda")
    except HelixshError as exc:
        assert "Unsupported runtime" in str(exc)
    else:
        raise AssertionError("expected HelixshError")


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
