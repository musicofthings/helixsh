"""nf-core-style schema validation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: tuple[ValidationIssue, ...]


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_params(schema: dict, params: dict) -> ValidationResult:
    issues: list[ValidationIssue] = []

    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in params:
            issues.append(ValidationIssue(field=field, message="Missing required parameter"))

    for key, value in params.items():
        expected = properties.get(key, {}).get("type")
        if expected == "string" and not isinstance(value, str):
            issues.append(ValidationIssue(field=key, message="Expected string"))
        elif expected == "integer" and not isinstance(value, int):
            issues.append(ValidationIssue(field=key, message="Expected integer"))
        elif expected == "boolean" and not isinstance(value, bool):
            issues.append(ValidationIssue(field=key, message="Expected boolean"))

    for group in schema.get("mutually_exclusive", []):
        present = [name for name in group if params.get(name) not in (None, False)]
        if len(present) > 1:
            issues.append(
                ValidationIssue(
                    field=",".join(group),
                    message=f"Mutually exclusive flags both set: {', '.join(present)}",
                )
            )

    return ValidationResult(ok=(len(issues) == 0), issues=tuple(issues))
