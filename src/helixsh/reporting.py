"""Validation/audit report generation utilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ValidationReport:
    generated_at: str
    status: str
    summary: dict


def build_validation_report(*, schema_ok: bool, container_policy_ok: bool, cache_percent: int, diagnostics: str) -> ValidationReport:
    checks = {
        "schema_ok": schema_ok,
        "container_policy_ok": container_policy_ok,
        "cache_percent": cache_percent,
        "diagnostics": diagnostics,
    }
    status = "pass" if schema_ok and container_policy_ok else "warn"
    return ValidationReport(
        generated_at=datetime.now(UTC).isoformat(),
        status=status,
        summary=checks,
    )


def write_report(report: ValidationReport, out_path: str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
