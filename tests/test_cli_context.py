import json

from helixsh import cli


def test_context_check_cli(tmp_path, capsys):
    samplesheet = tmp_path / "samplesheet.csv"
    config = tmp_path / "nextflow.config"
    samplesheet.write_text("sample,condition\nS1,tumor\n", encoding="utf-8")
    config.write_text("cpus = 4\n", encoding="utf-8")

    rc = cli.main(["context-check", "--samplesheet", str(samplesheet), "--config", str(config)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["samplesheet"]["row_count"] == 1
    assert payload["nextflow_config"]["cpus"] == "4"
