"""Seqera Platform / nextflow launch integration helpers.

`nextflow launch` was introduced in Nextflow 25.x and allows submitting
pipelines to Seqera Platform (formerly Tower) without manually constructing
the full `nextflow run` command.  This module provides a dry-run-safe wrapper
that composes the launch command and optionally executes it.

Environment variables honoured:
  TOWER_ACCESS_TOKEN  — Seqera Platform personal access token
  TOWER_WORKSPACE_ID  — numeric workspace ID (optional)
  TOWER_API_ENDPOINT  — defaults to https://api.cloud.seqera.io
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class LaunchConfig:
    pipeline: str
    revision: str = "main"
    profile: str = "docker"
    workspace_id: str | None = None
    compute_env: str | None = None
    outdir: str = "results"
    params: dict[str, str] = field(default_factory=dict)
    extra_args: list[str] = field(default_factory=list)


@dataclass
class LaunchResult:
    ok: bool
    command: str
    dry_run: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    run_url: str | None = None


def _token() -> str | None:
    return os.environ.get("TOWER_ACCESS_TOKEN")


def build_launch_command(cfg: LaunchConfig) -> list[str]:
    """Compose `nextflow launch` command arguments (does NOT execute)."""
    cmd = ["nextflow", "launch", cfg.pipeline]
    cmd += ["-r", cfg.revision]
    cmd += ["-profile", cfg.profile]
    if cfg.workspace_id:
        cmd += ["--workspace-id", cfg.workspace_id]
    if cfg.compute_env:
        cmd += ["--compute-env", cfg.compute_env]
    # Pipeline parameters passed as --params-file is safer; inline for simple cases
    for key, val in cfg.params.items():
        cmd += [f"--{key}", val]
    cmd += ["--outdir", cfg.outdir]
    cmd.extend(cfg.extra_args)
    return cmd


def launch_pipeline(cfg: LaunchConfig, dry_run: bool = True) -> LaunchResult:
    """Submit a pipeline via `nextflow launch`.  Defaults to dry_run=True."""
    cmd = build_launch_command(cfg)
    rendered = " ".join(cmd)

    if dry_run:
        return LaunchResult(ok=True, command=rendered, dry_run=True)

    token = _token()
    env = dict(os.environ)
    if token:
        env["TOWER_ACCESS_TOKEN"] = token

    try:
        result = subprocess.run(
            cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )
        ok = result.returncode == 0
        # Extract run URL from stdout if present ("Workflow submitted: <url>")
        run_url: str | None = None
        for line in result.stdout.splitlines():
            if "http" in line and "tower" in line.lower():
                run_url = line.strip().split()[-1]
                break
        return LaunchResult(
            ok=ok, command=rendered, dry_run=False,
            stdout=result.stdout, stderr=result.stderr,
            returncode=result.returncode, run_url=run_url,
        )
    except FileNotFoundError as exc:
        return LaunchResult(ok=False, command=rendered, dry_run=False,
                            stderr=str(exc), returncode=127)


def check_auth() -> dict[str, str | bool]:
    """Return authentication status without making a network call."""
    token = _token()
    endpoint = os.environ.get("TOWER_API_ENDPOINT", "https://api.cloud.seqera.io")
    workspace = os.environ.get("TOWER_WORKSPACE_ID")
    return {
        "token_set": bool(token),
        "endpoint": endpoint,
        "workspace_id": workspace or "default",
    }
