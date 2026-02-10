from helixsh import cli


def test_auditor_cannot_run_command(capsys):
    rc = cli.main(["--role", "auditor", "run", "nf-core", "rnaseq"])
    assert rc == 2
    assert "not allowed" in capsys.readouterr().err


def test_auditor_can_doctor(capsys):
    rc = cli.main(["--role", "auditor", "doctor"])
    assert rc == 0
    assert "nextflow" in capsys.readouterr().out
