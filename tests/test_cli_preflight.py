import json

from helixsh import cli


def test_preflight_pass(tmp_path, capsys):
    schema = tmp_path / "schema.json"
    params = tmp_path / "params.json"
    workflow = tmp_path / "main.nf"
    cache = tmp_path / "cache"
    (cache / "schemas").mkdir(parents=True)
    (cache / "containers").mkdir()
    (cache / "nextflow_assets").mkdir()

    schema.write_text('{"required":["input"],"properties":{"input":{"type":"string"}}}', encoding="utf-8")
    params.write_text('{"input":"samplesheet.csv"}', encoding="utf-8")
    workflow.write_text("process A { container 'img@sha256:abc' }", encoding="utf-8")

    rc = cli.main([
        "preflight",
        "--schema", str(schema),
        "--params", str(params),
        "--workflow", str(workflow),
        "--cache-root", str(cache),
        "--image", "img@sha256:abc",
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True


def test_preflight_fail_on_workflow_violation(tmp_path, capsys):
    workflow = tmp_path / "main.nf"
    workflow.write_text("process A { cpus 1 }", encoding="utf-8")
    rc = cli.main(["preflight", "--workflow", str(workflow)])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["workflow"]["ok"] is False


def test_preflight_requires_schema_and_params_together(tmp_path, capsys):
    schema = tmp_path / "schema.json"
    schema.write_text('{"type":"object"}', encoding="utf-8")

    rc = cli.main(["preflight", "--schema", str(schema)])

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["schema"]["ok"] is False
    assert "must be provided together" in payload["checks"]["schema"]["issues"][0]["message"]


def test_preflight_checks_kubernetes_config_via_runtime_flag(tmp_path, capsys):
    config = tmp_path / "nf-k8s.config"
    config.write_text("process.executor = 'local'\n", encoding="utf-8")

    rc = cli.main(["preflight", "--runtime", "kubernetes", "--config", str(config)])

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["runtime"]["ok"] is False
    assert payload["checks"]["runtime"]["issues"]


def test_preflight_runtime_flag_passes_for_a_valid_k8s_config(tmp_path, capsys):
    config = tmp_path / "nf-k8s.config"
    config.write_text(
        "plugins { id 'nf-k8s@1.5.5' }\nprocess.executor = 'k8s'\nk8s { storageClaimName = 'pvc' }\n",
        encoding="utf-8",
    )

    rc = cli.main(["preflight", "--runtime", "kubernetes", "--config", str(config)])

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["checks"]["runtime"]["ok"] is True
