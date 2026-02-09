import json

from helixsh import cli


def test_parse_workflow_command(tmp_path, capsys):
    nf = tmp_path / "main.nf"
    nf.write_text("process A { cpus 1 }", encoding="utf-8")
    rc = cli.main(["parse-workflow", "--file", str(nf)])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["container_policy_ok"] is False


def test_cache_report_command(capsys):
    rc = cli.main(["cache-report", "--total", "10", "--cached", "8", "--invalidated", "ALIGN_READS"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cached_percent"] == 80


def test_diagnose_command(capsys):
    rc = cli.main(["diagnose", "--process", "QUANTIFY", "--exit-code", "137", "--memory-gb", "4"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["likely_cause"] == "Out-of-memory"
