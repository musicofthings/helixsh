"""Intent parsing for bioinformatics-first command planning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentResult:
    pipeline: str
    runtime: str
    resume: bool
    low_memory_mode: bool
    sample_model: str | None


def parse_intent(text: str) -> IntentResult:
    normalized = text.lower().strip()

    pipeline = "nf-core/rnaseq"
    if "wgs" in normalized:
        pipeline = "nf-core/sarek"
    elif "wes" in normalized:
        pipeline = "nf-core/sarek"
    elif "chip" in normalized:
        pipeline = "nf-core/chipseq"
    elif "rna" in normalized:
        pipeline = "nf-core/rnaseq"

    runtime = "docker"
    if "podman" in normalized:
        runtime = "podman"
    elif "singularity" in normalized or "apptainer" in normalized:
        runtime = "singularity"

    sample_model = None
    if "tumor-normal" in normalized or "tumor normal" in normalized:
        sample_model = "tumor-normal"
    elif "trio" in normalized:
        sample_model = "trio"
    elif "cohort" in normalized:
        sample_model = "cohort"

    return IntentResult(
        pipeline=pipeline,
        runtime=runtime,
        resume=("resume" in normalized),
        low_memory_mode=("low-memory" in normalized or "low memory" in normalized),
        sample_model=sample_model,
    )


def intent_to_nf_args(intent: IntentResult) -> list[str]:
    args: list[str] = []
    if intent.low_memory_mode:
        args.extend(["--max_cpus", "2", "--max_memory", "8.GB"])
    if intent.sample_model == "tumor-normal":
        args.extend(["--tools", "strelka,mutect2"])
    return args
