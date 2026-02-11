"""Offline-mode utilities and cache checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OfflineReadiness:
    schema_cache_exists: bool
    container_cache_exists: bool
    nextflow_assets_cache_exists: bool
    ready: bool


def check_offline_readiness(cache_root: str) -> OfflineReadiness:
    root = Path(cache_root)
    schema_cache = root / "schemas"
    container_cache = root / "containers"
    assets_cache = root / "nextflow_assets"

    schema_ok = schema_cache.exists()
    container_ok = container_cache.exists()
    assets_ok = assets_cache.exists()

    return OfflineReadiness(
        schema_cache_exists=schema_ok,
        container_cache_exists=container_ok,
        nextflow_assets_cache_exists=assets_ok,
        ready=(schema_ok and container_ok and assets_ok),
    )
