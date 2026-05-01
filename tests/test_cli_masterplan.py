import json

from helixsh import cli


def test_cli_execution_lifecycle_and_audit_show(tmp_path, capsys):
    db = tmp_path / "db.sqlite"
    input_file = tmp_path / "input.txt"
    input_file.write_text("abc", encoding="utf-8")

    rc = cli.main([
        "execution-start",
        "--command", "nextflow run nf-core/rnaseq",
        "--workflow", "nf-core/rnaseq",
        "--db", str(db),
        "--input", str(input_file),
        "--image", "ghcr.io/nf-core/rnaseq@sha256:abc",
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    execution_id = payload["execution_context"]["execution_id"]

    rc = cli.main([
        "execution-finish",
        "--execution-id", execution_id,
        "--status", "completed",
        "--db", str(db),
    ])
    assert rc == 0
    _ = capsys.readouterr().out

    rc = cli.main(["audit-show", "--execution-id", execution_id, "--db", str(db)])
    assert rc == 0
    bundle = json.loads(capsys.readouterr().out)
    assert bundle["execution"]["status"] == "completed"
    assert len(bundle["inputs"]) == 1


def test_cli_agent_run_arbitrate_and_compliance(tmp_path, capsys):
    responses = tmp_path / "responses.json"

    rc = cli.main([
        "agent-run",
        "--agent", "claude",
        "--task", "variant_classification",
        "--model", "opus-4.6",
        "--payload", "BRCA1:c.68_69delAG",
    ])
    assert rc == 0
    first = json.loads(capsys.readouterr().out)

    second = dict(first)
    second["agent"] = "codex"
    second["result"] = {"classification": "Likely Pathogenic"}
    second["confidence"] = 0.72
    second["acmg_evidence"] = {"PVS1": True, "PM2": False, "PP3": True}
    responses.write_text(json.dumps([first, second]), encoding="utf-8")

    rc = cli.main(["arbitrate", "--responses", str(responses), "--strategy", "majority"])
    assert rc == 0
    arb = json.loads(capsys.readouterr().out)
    assert arb["agents_compared"] == 2

    rc = cli.main([
        "compliance-check",
        "--image", "ghcr.io/tool:latest",
        "--agreement-score", "0.5",
        "--confidence", "0.6",
        "--confidence", "0.7",
        "--evidence-conflict",
    ])
    assert rc == 2
    comp = json.loads(capsys.readouterr().out)
    assert comp["requires_manual_review"] is True
