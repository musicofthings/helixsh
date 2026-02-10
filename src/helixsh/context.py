"""Context ingestion helpers for samplesheets and Nextflow config defaults."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SampleSheetSummary:
    row_count: int
    has_tumor_normal: bool
    sample_ids: tuple[str, ...]


@dataclass(frozen=True)
class ConfigDefaults:
    cpus: str | None
    memory: str | None
    time: str | None


def summarize_samplesheet(path: str) -> SampleSheetSummary:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    with p.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    sample_ids: list[str] = []
    tumor_normal = False
    for row in rows:
        sample = (row.get("sample") or row.get("sample_id") or "").strip()
        if sample:
            sample_ids.append(sample)
        role = (row.get("condition") or row.get("type") or "").strip().lower()
        if role in {"tumor", "normal"}:
            tumor_normal = True

    return SampleSheetSummary(row_count=len(rows), has_tumor_normal=tumor_normal, sample_ids=tuple(sample_ids))


def parse_nextflow_config_defaults(path: str) -> ConfigDefaults:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    text = p.read_text(encoding="utf-8")

    def extract(key: str) -> str | None:
        m = re.search(rf"\b{key}\s*=\s*([^\n]+)", text)
        if not m:
            return None
        return m.group(1).strip().strip('"\'')

    return ConfigDefaults(cpus=extract("cpus"), memory=extract("memory"), time=extract("time"))
