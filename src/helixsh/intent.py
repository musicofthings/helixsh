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
    elif "atac" in normalized:
        pipeline = "nf-core/atacseq"
    elif "chip" in normalized:
        pipeline = "nf-core/chipseq"
    elif "methyl" in normalized or "bisulfite" in normalized:
        pipeline = "nf-core/methylseq"
    elif "scrna" in normalized or "single.cell" in normalized or "single cell" in normalized:
        pipeline = "nf-core/scrnaseq"
    elif "amplicon" in normalized or "16s" in normalized or "ampliseq" in normalized:
        pipeline = "nf-core/ampliseq"
    elif "rna" in normalized:
        pipeline = "nf-core/rnaseq"

    runtime = "docker"
    if "podman" in normalized:
        runtime = "podman"
    elif "apptainer" in normalized:
        # apptainer is nf-core's preferred successor to singularity on HPC
        runtime = "apptainer"
    elif "singularity" in normalized:
        runtime = "singularity"
    elif "conda" in normalized:
        runtime = "conda"

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
    if intent.runtime == "conda":
        args.append("-with-conda")
    return args
