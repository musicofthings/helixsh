"""nf-core pipeline version registry and update checker.

Maintains a local snapshot of known nf-core pipeline versions so users can
check whether their pinned pipeline revision is current without leaving the
CLI.  The registry can be refreshed from the nf-co.re API (requires network)
or used offline from the bundled snapshot.

nf-co.re API endpoint:
  https://nf-co.re/pipeline_versions   (returns JSON array of pipeline objects)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Bundled snapshot — version strings current as of April 2026.
# Refresh with `helixsh pipeline-update --refresh --cache <path>`.
_BUNDLED_REGISTRY: list[dict[str, str]] = [
    {"name": "rnaseq",              "latest": "3.14.0", "description": "RNA-seq quantification"},
    {"name": "sarek",               "latest": "3.4.4",  "description": "Germline/somatic variant calling"},
    {"name": "chipseq",             "latest": "2.0.0",  "description": "ChIP-seq peak calling"},
    {"name": "atacseq",             "latest": "2.1.2",  "description": "ATAC-seq chromatin accessibility"},
    {"name": "methylseq",           "latest": "2.7.1",  "description": "Bisulfite / DNA methylation"},
    {"name": "scrnaseq",            "latest": "2.7.1",  "description": "Single-cell RNA-seq"},
    {"name": "ampliseq",            "latest": "2.11.0", "description": "16S / amplicon sequencing"},
    {"name": "mag",                 "latest": "3.0.3",  "description": "Metagenome assembly and binning"},
    {"name": "viralrecon",          "latest": "2.6.0",  "description": "Viral genome reconstruction"},
    {"name": "eager",               "latest": "2.5.2",  "description": "Ancient DNA analysis"},
    {"name": "nanoseq",             "latest": "3.1.0",  "description": "Oxford Nanopore analysis"},
    {"name": "hic",                 "latest": "2.1.0",  "description": "Hi-C conformation capture"},
    {"name": "differentialabundance","latest": "1.5.0", "description": "Differential abundance analysis"},
    {"name": "taxprofiler",         "latest": "1.2.0",  "description": "Metagenomic taxonomic profiling"},
    {"name": "fetchngs",            "latest": "1.12.0", "description": "Fetch public sequencing data"},
    {"name": "smrnaseq",            "latest": "2.3.1",  "description": "Small RNA-seq / miRNA"},
    {"name": "cutandrun",           "latest": "3.2.2",  "description": "CUT&RUN / CUT&TAG"},
    {"name": "circrna",             "latest": "1.1.0",  "description": "Circular RNA analysis"},
    {"name": "proteinfold",         "latest": "1.1.1",  "description": "Protein structure prediction"},
    {"name": "spatialvi",           "latest": "1.1.4",  "description": "Spatial transcriptomics"},
]

_NF_CORE_API = "https://nf-co.re/pipeline_versions"


@dataclass
class PipelineVersion:
    name: str
    latest: str
    pinned: str | None = None
    up_to_date: bool | None = None
    description: str = ""


@dataclass
class RegistryRefreshResult:
    ok: bool
    fetched: int
    cached_at: str
    error: str = ""


def _load_registry(cache_path: str | None) -> list[dict[str, str]]:
    if cache_path:
        p = Path(cache_path)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return _BUNDLED_REGISTRY


def refresh_registry(cache_path: str, timeout: int = 10) -> RegistryRefreshResult:
    """Fetch latest pipeline versions from nf-co.re and write to cache_path."""
    try:
        with urllib.request.urlopen(_NF_CORE_API, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        return RegistryRefreshResult(ok=False, fetched=0,
                                     cached_at="", error=str(exc))

    # nf-co.re returns a list of objects; normalise to our format
    normalised: list[dict[str, str]] = []
    for entry in data:
        name = (entry.get("name") or entry.get("title") or "").strip().lower()
        version = (entry.get("tag_latest") or entry.get("latest") or "").strip()
        desc = (entry.get("description") or "").strip()
        if name and version:
            normalised.append({"name": name, "latest": version, "description": desc})

    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    Path(cache_path).write_text(json.dumps(normalised, indent=2), encoding="utf-8")
    now = datetime.now(UTC).isoformat()
    return RegistryRefreshResult(ok=True, fetched=len(normalised), cached_at=now)


def list_pipelines(cache_path: str | None = None) -> list[PipelineVersion]:
    registry = _load_registry(cache_path)
    return [PipelineVersion(name=r["name"], latest=r["latest"],
                             description=r.get("description", ""))
            for r in registry]


def check_pipeline_version(pipeline: str, pinned: str,
                            cache_path: str | None = None) -> PipelineVersion:
    """Check whether `pinned` matches the latest known version of `pipeline`."""
    name = pipeline.strip().lower().removeprefix("nf-core/")
    registry = _load_registry(cache_path)
    for entry in registry:
        if entry["name"] == name:
            latest = entry["latest"]
            return PipelineVersion(
                name=name, latest=latest, pinned=pinned,
                up_to_date=(pinned == latest),
                description=entry.get("description", ""),
            )
    # Unknown pipeline — return with no version comparison
    return PipelineVersion(name=name, latest="unknown", pinned=pinned,
                           up_to_date=None)
