import json

import pytest

from helixsh import cli
from helixsh.kubernetes import (
    KubernetesConfig,
    render_kubernetes_config,
    validate_kubernetes_config_file,
)
from helixsh.nextflow import RunConfig, build_nextflow_run_command


def test_render_kubernetes_config_uses_nf_k8s_and_shared_storage():
    rendered = render_kubernetes_config(
        KubernetesConfig(
            namespace="genomics",
            service_account="nextflow",
            storage_claim="nextflow-pvc",
        )
    )

    assert "id 'nf-k8s@1.5.5'" in rendered
    assert "process.executor = 'k8s'" in rendered
    assert "storageClaimName = 'nextflow-pvc'" in rendered
    assert "workDir = '/workspace/work'" in rendered


def test_render_kubernetes_config_rejects_injection():
    with pytest.raises(ValueError, match="valid lowercase Kubernetes name"):
        render_kubernetes_config(
            KubernetesConfig(
                namespace="default'; println('unsafe')",
                service_account="nextflow",
                storage_claim="nextflow-pvc",
            )
        )


@pytest.mark.parametrize("namespace", ["team.alpha", "a" * 64, "-genomics"])
def test_render_kubernetes_config_rejects_invalid_namespace(namespace):
    with pytest.raises(ValueError, match="valid lowercase Kubernetes name"):
        render_kubernetes_config(
            KubernetesConfig(
                namespace=namespace,
                service_account="nextflow",
                storage_claim="nextflow-pvc",
            )
        )


def test_render_kubernetes_config_rejects_non_normalized_mount():
    with pytest.raises(ValueError, match="normalized absolute path"):
        render_kubernetes_config(
            KubernetesConfig(
                namespace="default",
                service_account="nextflow",
                storage_claim="nextflow-pvc",
                storage_mount_path="/workspace/../etc",
            )
        )


def test_validate_kubernetes_config_reports_missing_requirements(tmp_path):
    config = tmp_path / "nextflow.config"
    config.write_text("process.executor = 'local'\n", encoding="utf-8")

    issues = validate_kubernetes_config_file(str(config))

    assert len(issues) == 3


def test_kubernetes_run_command_uses_config_without_local_container_profile():
    command = build_nextflow_run_command(
        RunConfig(
            pipeline="nf-core/rnaseq",
            profile="kubernetes",
            config_file="/tmp/nf-k8s.config",
        )
    )

    assert command == [
        "nextflow",
        "-c",
        "/tmp/nf-k8s.config",
        "run",
        "nf-core/rnaseq",
    ]


def test_cli_generates_kubernetes_config(tmp_path, capsys):
    output = tmp_path / "nf-k8s.config"

    rc = cli.main(
        [
            "k8s-config",
            "--namespace",
            "genomics",
            "--service-account",
            "nextflow",
            "--storage-claim",
            "nextflow-pvc",
            "--out",
            str(output),
        ]
    )

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert validate_kubernetes_config_file(str(output)) == ()


def test_cli_requires_config_for_kubernetes(capsys):
    rc = cli.main(["run", "nf-core", "rnaseq", "--runtime", "kubernetes"])

    assert rc == 2
    assert "requires --config" in capsys.readouterr().err
