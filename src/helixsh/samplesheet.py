"""Samplesheet validation and generation helpers.

Supports nf-core samplesheet formats for common pipelines:
  - rnaseq:  sample, fastq_1, fastq_2, strandedness
  - sarek:   patient, sample, lane, fastq_1, fastq_2, status (0/1)
  - chipseq: sample, fastq_1, fastq_2, antibody, control
  - atacseq: sample, fastq_1, fastq_2
  - generic: sample, fastq_1, [fastq_2]

Generation scans a directory for FASTQ files matching common naming patterns
and groups them by sample name extracted from the filename stem.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

# Column requirements per pipeline
_SCHEMA: dict[str, list[str]] = {
    "rnaseq":   ["sample", "fastq_1", "strandedness"],
    "sarek":    ["patient", "sample", "lane", "fastq_1", "status"],
    "chipseq":  ["sample", "fastq_1", "antibody"],
    "atacseq":  ["sample", "fastq_1"],
    "methylseq":["sample", "fastq_1"],
    "scrnaseq": ["sample", "fastq_1"],
    "ampliseq": ["sample", "run", "barcode"],
    "generic":  ["sample", "fastq_1"],
}

# Read-pair suffix patterns that helixsh recognises
_R1_PATTERNS = re.compile(r"(_R1|_1|\.R1|\.1)(_\d{3})?(\.(fastq|fq)(\.gz)?)$", re.IGNORECASE)
_R2_PATTERNS = re.compile(r"(_R2|_2|\.R2|\.2)(_\d{3})?(\.(fastq|fq)(\.gz)?)$", re.IGNORECASE)
_SAMPLE_STEM  = re.compile(r"(_R[12]|_[12])(_\d{3})?(\.(fastq|fq)(\.gz)?)$", re.IGNORECASE)


@dataclass
class ValidationIssue:
    row: int
    field: str
    message: str


@dataclass
class SamplesheetValidationResult:
    ok: bool
    pipeline: str
    row_count: int
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class GeneratedSamplesheet:
    pipeline: str
    rows: list[dict[str, str]]
    csv_text: str
    warnings: list[str] = field(default_factory=list)


def validate_samplesheet(path: str, pipeline: str = "rnaseq") -> SamplesheetValidationResult:
    """Validate a CSV samplesheet against the nf-core schema for `pipeline`."""
    required_cols = _SCHEMA.get(pipeline.strip().lower(), _SCHEMA["generic"])
    p = Path(path)
    if not p.exists():
        return SamplesheetValidationResult(
            ok=False, pipeline=pipeline, row_count=0,
            issues=[ValidationIssue(0, "file", f"File not found: {path}")],
        )

    with p.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return SamplesheetValidationResult(
                ok=False, pipeline=pipeline, row_count=0,
                issues=[ValidationIssue(0, "header", "Empty or missing header row")],
            )
        headers = [h.strip() for h in reader.fieldnames]
        rows = list(reader)

    issues: list[ValidationIssue] = []
    # Check required columns present
    for col in required_cols:
        if col not in headers:
            issues.append(ValidationIssue(0, col, f"Required column '{col}' missing from header"))

    # Per-row checks
    for i, row in enumerate(rows, start=2):
        sample = (row.get("sample") or row.get("patient") or "").strip()
        if not sample:
            issues.append(ValidationIssue(i, "sample", "Empty sample/patient identifier"))

        fastq1 = row.get("fastq_1", "").strip()
        if "fastq_1" in required_cols and not fastq1:
            issues.append(ValidationIssue(i, "fastq_1", "fastq_1 is empty"))
        elif fastq1 and not fastq1.lower().endswith((".fastq.gz", ".fq.gz", ".fastq", ".fq")):
            issues.append(ValidationIssue(i, "fastq_1", f"Unexpected file extension: {fastq1}"))

        # rnaseq: strandedness must be auto|forward|reverse|unstranded
        if pipeline == "rnaseq":
            strand = row.get("strandedness", "").strip().lower()
            if strand and strand not in {"auto", "forward", "reverse", "unstranded"}:
                issues.append(ValidationIssue(i, "strandedness",
                                               f"Invalid strandedness '{strand}' — expected auto/forward/reverse/unstranded"))

        # sarek: status must be 0 or 1
        if pipeline == "sarek":
            status = str(row.get("status", "")).strip()
            if status and status not in {"0", "1"}:
                issues.append(ValidationIssue(i, "status",
                                               f"Status must be 0 (normal) or 1 (tumor), got '{status}'"))

    return SamplesheetValidationResult(
        ok=len(issues) == 0, pipeline=pipeline,
        row_count=len(rows), issues=issues,
    )


def generate_samplesheet(fastq_dir: str, pipeline: str = "rnaseq",
                          strandedness: str = "auto") -> GeneratedSamplesheet:
    """Scan `fastq_dir` for FASTQ files and generate a samplesheet CSV."""
    pipeline_norm = pipeline.strip().lower()
    root = Path(fastq_dir)
    warnings: list[str] = []

    if not root.exists():
        return GeneratedSamplesheet(
            pipeline=pipeline_norm, rows=[], csv_text="",
            warnings=[f"Directory not found: {fastq_dir}"],
        )

    # Collect all fastq files
    fastq_files = sorted(
        f for f in root.rglob("*")
        if f.is_file() and re.search(r"\.(fastq|fq)(\.gz)?$", f.name, re.IGNORECASE)
    )
    if not fastq_files:
        return GeneratedSamplesheet(
            pipeline=pipeline_norm, rows=[], csv_text="",
            warnings=["No FASTQ files found in directory"],
        )

    # Group R1/R2 by sample name
    r1_files: dict[str, Path] = {}
    r2_files: dict[str, Path] = {}
    for f in fastq_files:
        if _R1_PATTERNS.search(f.name):
            sample = _SAMPLE_STEM.sub("", f.name)
            r1_files[sample] = f
        elif _R2_PATTERNS.search(f.name):
            sample = _SAMPLE_STEM.sub("", f.name)
            r2_files[sample] = f

    if not r1_files:
        # Treat all files as single-end R1
        for f in fastq_files:
            r1_files[f.stem.split(".")[0]] = f
        warnings.append("No R1/R2 patterns found — treating all files as single-end reads")

    rows: list[dict[str, str]] = []
    for sample_name in sorted(r1_files):
        r1 = str(r1_files[sample_name])
        r2 = str(r2_files.get(sample_name, ""))

        if pipeline_norm == "rnaseq":
            rows.append({"sample": sample_name, "fastq_1": r1, "fastq_2": r2, "strandedness": strandedness})
        elif pipeline_norm == "sarek":
            rows.append({
                "patient": sample_name, "sample": sample_name, "lane": "L001",
                "fastq_1": r1, "fastq_2": r2, "status": "0",
            })
        elif pipeline_norm in {"chipseq"}:
            rows.append({"sample": sample_name, "fastq_1": r1, "fastq_2": r2,
                         "antibody": "", "control": ""})
        else:
            rows.append({"sample": sample_name, "fastq_1": r1, "fastq_2": r2})

    if not rows:
        warnings.append("No samples could be paired — check filename conventions")

    # Render CSV
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return GeneratedSamplesheet(
        pipeline=pipeline_norm, rows=rows,
        csv_text=buf.getvalue(), warnings=warnings,
    )
