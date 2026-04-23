"""Seqera Platform (Tower) API submission helpers.

Provides a thin, zero-dependency wrapper around the Seqera Platform REST API
for launching and monitoring pipeline runs.  All network calls use
`urllib.request` from the standard library.

Required environment variable:
  TOWER_ACCESS_TOKEN  — personal access token from app.cloud.seqera.io

Optional environment variables:
  TOWER_API_ENDPOINT  — default: https://api.cloud.seqera.io
  TOWER_WORKSPACE_ID  — numeric workspace ID

API reference: https://docs.seqera.io/platform/api
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field


def _endpoint() -> str:
    return os.environ.get("TOWER_API_ENDPOINT", "https://api.cloud.seqera.io").rstrip("/")


def _token() -> str | None:
    return os.environ.get("TOWER_ACCESS_TOKEN")


def _workspace_id() -> str | None:
    return os.environ.get("TOWER_WORKSPACE_ID")


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _get(path: str, timeout: int = 10) -> dict:
    url = _endpoint() + path
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(path: str, body: dict, timeout: int = 30) -> dict:
    url = _endpoint() + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class TowerRunConfig:
    pipeline: str
    revision: str = "main"
    profile: str = "docker"
    params: dict[str, str] = field(default_factory=dict)
    workspace_id: str | None = None
    compute_env_id: str | None = None
    work_dir: str = "s3://your-bucket/work"
    label: str = ""


@dataclass
class TowerSubmitResult:
    ok: bool
    workflow_id: str = ""
    run_url: str = ""
    error: str = ""
    dry_run: bool = False


@dataclass
class TowerRunStatus:
    workflow_id: str
    status: str
    pipeline: str
    progress: dict = field(default_factory=dict)
    error: str = ""


def check_auth(timeout: int = 5) -> dict[str, str | bool]:
    """Verify token and connectivity without launching anything."""
    if not _token():
        return {"ok": False, "error": "TOWER_ACCESS_TOKEN not set",
                "endpoint": _endpoint()}
    try:
        data = _get("/user-info", timeout=timeout)
        return {
            "ok": True,
            "endpoint": _endpoint(),
            "user": data.get("user", {}).get("email", "unknown"),
            "workspace_id": _workspace_id() or "default",
        }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}: {exc.reason}",
                "endpoint": _endpoint()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "endpoint": _endpoint()}


def submit_run(cfg: TowerRunConfig, dry_run: bool = True) -> TowerSubmitResult:
    """Submit a pipeline run to Seqera Platform.  Defaults to dry_run=True."""
    workspace_id = cfg.workspace_id or _workspace_id()
    endpoint_path = "/workflow/launch"
    if workspace_id:
        endpoint_path += f"?workspaceId={workspace_id}"

    body = {
        "launch": {
            "pipeline": cfg.pipeline,
            "revision": cfg.revision,
            "profiles": [cfg.profile],
            "params": cfg.params,
            "workDir": cfg.work_dir,
        }
    }
    if cfg.compute_env_id:
        body["launch"]["computeEnvId"] = cfg.compute_env_id
    if cfg.label:
        body["launch"]["configText"] = f'// label: {cfg.label}'

    if dry_run:
        return TowerSubmitResult(
            ok=True, dry_run=True,
            workflow_id="(dry-run)",
            run_url=f"{_endpoint()}/orgs/default/workspaces/default/watch/(dry-run)",
        )

    if not _token():
        return TowerSubmitResult(ok=False, error="TOWER_ACCESS_TOKEN not set")

    try:
        resp = _post(endpoint_path, body)
        wf_id = resp.get("workflowId", "")
        ws = workspace_id or "default"
        run_url = f"{_endpoint()}/orgs/default/workspaces/{ws}/watch/{wf_id}"
        return TowerSubmitResult(ok=True, workflow_id=wf_id, run_url=run_url)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return TowerSubmitResult(ok=False, error=f"HTTP {exc.code}: {body_text}")
    except Exception as exc:  # noqa: BLE001
        return TowerSubmitResult(ok=False, error=str(exc))


def get_run_status(workflow_id: str, workspace_id: str | None = None,
                   timeout: int = 10) -> TowerRunStatus:
    """Fetch run status for a previously submitted workflow."""
    ws = workspace_id or _workspace_id()
    path = f"/workflow/{workflow_id}"
    if ws:
        path += f"?workspaceId={ws}"
    try:
        resp = _get(path, timeout=timeout)
        wf = resp.get("workflow", resp)
        return TowerRunStatus(
            workflow_id=workflow_id,
            status=wf.get("status", "unknown"),
            pipeline=wf.get("manifest", {}).get("name", ""),
            progress=resp.get("progress", {}),
        )
    except urllib.error.HTTPError as exc:
        return TowerRunStatus(workflow_id=workflow_id, status="error",
                              pipeline="", error=f"HTTP {exc.code}: {exc.reason}")
    except Exception as exc:  # noqa: BLE001
        return TowerRunStatus(workflow_id=workflow_id, status="error",
                              pipeline="", error=str(exc))


def list_compute_envs(workspace_id: str | None = None, timeout: int = 10) -> list[dict]:
    """List available compute environments in the workspace."""
    ws = workspace_id or _workspace_id()
    path = "/compute-envs"
    if ws:
        path += f"?workspaceId={ws}"
    try:
        resp = _get(path, timeout=timeout)
        return resp.get("computeEnvs", [])
    except Exception as exc:  # noqa: BLE001
        return [{"error": str(exc)}]
