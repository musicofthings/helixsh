from helixsh.executor import build_posix_exec


def test_build_posix_exec_wraps_command():
    wrapped = build_posix_exec(["nextflow", "run", "nf-core/rnaseq"])
    assert wrapped.startswith("exec sh -c")
    assert "nextflow run nf-core/rnaseq" in wrapped
