import json

from helixsh import cli


def test_cli_mcp_proposal_flow(tmp_path, capsys):
    old = cli.PROPOSAL_FILE
    cli.PROPOSAL_FILE = tmp_path / "props.jsonl"
    try:
        assert cli.main(["mcp-propose", "--kind", "file_patch", "--summary", "s", "--payload", "p"]) == 0
        assert cli.main(["mcp-proposals"]) == 0
        out = capsys.readouterr().out
        assert "file_patch" in out
        assert cli.main(["mcp-approve", "--id", "1"]) == 0
        approved = json.loads(capsys.readouterr().out)
        assert approved["status"] == "approved"
    finally:
        cli.PROPOSAL_FILE = old


def test_cli_resource_estimate(capsys):
    rc = cli.main(["resource-estimate", "--tool", "salmon", "--assay", "rnaseq", "--samples", "3"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_memory_gb"] == 24
