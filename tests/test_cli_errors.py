from helixsh import cli


def test_context_check_missing_file_returns_2(capsys):
    rc = cli.main(["context-check", "--samplesheet", "/no/such/file.csv"])
    assert rc == 2
    assert "helixsh error" in capsys.readouterr().err
