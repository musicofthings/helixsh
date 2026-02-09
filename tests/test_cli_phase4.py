import json

from helixsh import cli


def test_profile_suggest_cli(capsys):
    rc = cli.main(["profile-suggest", "--assay", "wgs", "--offline"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pipeline"] == "nf-core/sarek"


def test_provenance_cli(capsys):
    rc = cli.main(["provenance", "--command", "nextflow run x", "--params", '{"a":1}'])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "execution_hash" in payload


def test_image_check_cli_denied(capsys):
    rc = cli.main(["image-check", "--image", ""])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["allowed"] is False
