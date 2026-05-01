from helixsh import cli


def test_posix_wrap_prints_command(capsys):
    rc = cli.main(["posix-wrap", "nextflow", "run", "nf-core/rnaseq"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("exec sh -c")


def test_posix_wrap_execute(capsys):
    rc = cli.main(["posix-wrap", "echo", "hello", "--execute"])
    assert rc == 0
