"""Safe generation and validation of Nextflow Kubernetes executor config."""

from __future__ import annotations

import re
import posixpath
from dataclasses import dataclass
from pathlib import Path


NF_K8S_PLUGIN_VERSION = "1.5.5"
K8S_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
# Values are interpolated into single-quoted Groovy strings, where a trailing
# backslash escapes the closing quote. An allow-list is used rather than a
# deny-list of dangerous characters so nothing that can break out of the
# quoting reaches the rendered config.
K8S_MOUNT_PATH_RE = re.compile(r"^/(?:[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)?$")


@dataclass(frozen=True)
class KubernetesConfig:
    namespace: str
    service_account: str
    storage_claim: str
    storage_mount_path: str = "/workspace"


def _validate_k8s_name(field: str, value: str, *, subdomain: bool) -> str:
    normalized = value.strip().lower()
    labels = normalized.split(".") if subdomain else [normalized]
    if (
        not normalized
        or len(normalized) > (253 if subdomain else 63)
        or any(not K8S_LABEL_RE.fullmatch(label) for label in labels)
    ):
        raise ValueError(f"{field} must be a valid lowercase Kubernetes name")
    return normalized


def validate_kubernetes_settings(config: KubernetesConfig) -> KubernetesConfig:
    namespace = _validate_k8s_name("namespace", config.namespace, subdomain=False)
    service_account = _validate_k8s_name("service account", config.service_account, subdomain=True)
    storage_claim = _validate_k8s_name("storage claim", config.storage_claim, subdomain=True)
    mount_path = config.storage_mount_path.strip()
    if not K8S_MOUNT_PATH_RE.fullmatch(mount_path) or posixpath.normpath(mount_path) != mount_path:
        raise ValueError("storage mount path must be a normalized absolute path")
    return KubernetesConfig(
        namespace=namespace,
        service_account=service_account,
        storage_claim=storage_claim,
        storage_mount_path=mount_path.rstrip("/") or "/",
    )


def render_kubernetes_config(config: KubernetesConfig) -> str:
    settings = validate_kubernetes_settings(config)
    work_dir = f"{settings.storage_mount_path.rstrip('/')}/work"
    return (
        "plugins {\n"
        f"    id 'nf-k8s@{NF_K8S_PLUGIN_VERSION}'\n"
        "}\n\n"
        "process.executor = 'k8s'\n\n"
        "k8s {\n"
        f"    namespace = '{settings.namespace}'\n"
        f"    serviceAccount = '{settings.service_account}'\n"
        f"    storageClaimName = '{settings.storage_claim}'\n"
        f"    storageMountPath = '{settings.storage_mount_path}'\n"
        "}\n\n"
        f"workDir = '{work_dir}'\n"
    )


def write_kubernetes_config(path: str, config: KubernetesConfig) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_kubernetes_config(config), encoding="utf-8")
    return destination


def _strip_groovy_comments(text: str) -> str:
    """Drop comments so a commented-out directive cannot satisfy a check."""
    without_blocks = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    # (?<!:) keeps a URL scheme such as https:// from being read as a comment.
    return re.sub(r"(?<!:)//[^\n]*", " ", without_blocks)


def validate_kubernetes_config_file(path: str) -> tuple[str, ...]:
    text = _strip_groovy_comments(Path(path).read_text(encoding="utf-8"))
    issues: list[str] = []
    if not re.search(r"\bid\s+['\"]nf-k8s(?:@[0-9][0-9A-Za-z.-]*)?['\"]", text):
        issues.append("Kubernetes config must enable the nf-k8s plugin")
    if not re.search(r"\bprocess\.executor\s*=\s*['\"]k8s['\"]", text):
        issues.append("Kubernetes config must set process.executor to 'k8s'")
    if not re.search(r"\bstorageClaimName\s*=", text):
        issues.append("Kubernetes config must define k8s.storageClaimName")
    return tuple(issues)
