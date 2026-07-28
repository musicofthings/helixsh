"""Snakemake → helixsh resource bridge.

Parses Snakemake `Snakefile` rule blocks and extracts `resources:` directives
(threads, mem_mb, runtime) so they can be imported into helixsh's resource
estimation model or compared with helixsh's own estimates.

Supports:
  - `threads: N`
  - `resources: mem_mb=N, runtime=N, disk_mb=N`
  - Wildcard-free static literals only (dynamic expressions are skipped with a warning)

Output can be:
  1. A list of `SnakemakeRule` objects (programmatic use)
  2. A helixsh-compatible calibration JSON (for `fit-calibration` integration)
  3. A comparison report against helixsh's own estimates
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class SnakemakeRule:
    name: str
    threads: int | None
    mem_mb: int | None
    runtime_min: int | None
    disk_mb: int | None
    raw_resources: dict[str, str] = field(default_factory=dict)


@dataclass
class ImportResult:
    rules: list[SnakemakeRule]
    warnings: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


_RULE_RE   = re.compile(r"^rule\s+(\w+)\s*:", re.MULTILINE)
_THREAD_RE = re.compile(r"^\s+threads\s*:\s*(\d+)", re.MULTILINE)
_MEM_RE    = re.compile(r"\bmem_mb\s*=\s*(\d+)")
_RT_RE     = re.compile(r"\bruntime\s*=\s*(\d+)")
_DISK_RE   = re.compile(r"\bdisk_mb\s*=\s*(\d+)")
_RESOURCE_BLOCK_RE = re.compile(r"^\s+resources\s*:(.*?)(?=^\s+\w+\s*:|^rule\s|\Z)", re.MULTILINE | re.DOTALL)


def _extract_block(text: str, start_pos: int) -> str:
    """Extract the indented block belonging to a rule starting at start_pos."""
    lines = text[start_pos:].splitlines(keepends=True)
    block_lines: list[str] = []
    in_block = False
    for line in lines[1:]:   # skip the 'rule NAME:' line itself
        if not line.strip():
            block_lines.append(line)
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            break
        in_block = True
        block_lines.append(line)
    return "".join(block_lines) if in_block else ""


def _int_or_none(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_snakefile(path: str) -> ImportResult:
    """Parse a Snakefile and extract rule resource declarations."""
    p = Path(path)
    if not p.exists():
        return ImportResult(rules=[], warnings=[f"Snakefile not found: {path}"])

    text = p.read_text(encoding="utf-8")
    result = ImportResult(rules=[])

    for m in _RULE_RE.finditer(text):
        rule_name = m.group(1)
        block = _extract_block(text, m.start())
        if not block:
            continue

        # threads
        tm = _THREAD_RE.search(block)
        threads = _int_or_none(tm.group(1)) if tm else None

        # resources block
        rm = _RESOURCE_BLOCK_RE.search(block)
        mem_mb = runtime_min = disk_mb = None
        raw_resources: dict[str, str] = {}
        if rm:
            res_text = rm.group(1)
            # Check for dynamic expressions (lambda, variable references)
            if "lambda" in res_text or re.search(r"\b[a-zA-Z_]\w*\s*\(", res_text):
                result.warnings.append(
                    f"Rule '{rule_name}' has dynamic resources — static values only extracted"
                )
            mem_m = _MEM_RE.search(res_text)
            rt_m  = _RT_RE.search(res_text)
            dk_m  = _DISK_RE.search(res_text)
            mem_mb      = _int_or_none(mem_m.group(1))  if mem_m else None
            runtime_min = _int_or_none(rt_m.group(1))   if rt_m  else None
            disk_mb     = _int_or_none(dk_m.group(1))   if dk_m  else None

            # Capture all key=value pairs as raw_resources for completeness
            for key, val in re.findall(r"(\w+)\s*=\s*([\d.]+)", res_text):
                raw_resources[key] = val

        result.rules.append(SnakemakeRule(
            name=rule_name, threads=threads,
            mem_mb=mem_mb, runtime_min=runtime_min, disk_mb=disk_mb,
            raw_resources=raw_resources,
        ))

    if not result.rules:
        result.warnings.append("No rules found in Snakefile — check formatting")

    return result


def to_helixsh_calibration(rules: list[SnakemakeRule]) -> list[dict]:
    """Convert Snakemake rules into helixsh calibration observation dicts.

    Maps:  threads → expected_cpu,  mem_mb/1024 → expected_memory_gb
    Sets observed_* equal to expected_* (1:1 ratio, neutral calibration).
    Callers can adjust the observed values from actual run metrics.
    """
    observations = []
    for rule in rules:
        if rule.threads is None and rule.mem_mb is None:
            continue
        cpu = rule.threads or 1
        mem_gb = (rule.mem_mb or 1024) / 1024
        observations.append({
            "rule": rule.name,
            "expected_cpu": cpu,
            "observed_cpu": cpu,
            "expected_memory_gb": round(mem_gb, 2),
            "observed_memory_gb": round(mem_gb, 2),
        })
    return observations


def export_calibration_json(rules: list[SnakemakeRule], out_path: str) -> None:
    """Write helixsh-compatible calibration observations to a JSON file."""
    obs = to_helixsh_calibration(rules)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(obs, indent=2), encoding="utf-8")


def import_summary(result: ImportResult) -> dict:
    """Return a JSON-serialisable summary of the import."""
    return {
        "total_rules": len(result.rules),
        "rules_with_resources": sum(1 for r in result.rules if r.mem_mb or r.threads),
        "warnings": result.warnings,
        "rules": [asdict(r) for r in result.rules],
    }
