"""Bioinformatics profile/recommendation helpers."""

from __future__ import annotations

from dataclasses import dataclass

# Known nf-core pipelines: assay key -> pipeline name
_ASSAY_PIPELINE = {
    "wgs": "nf-core/sarek",
    "wes": "nf-core/sarek",
    "chip-seq": "nf-core/chipseq",
    "chipseq": "nf-core/chipseq",
    "atac-seq": "nf-core/atacseq",
    "atacseq": "nf-core/atacseq",
    "methyl": "nf-core/methylseq",
    "methylseq": "nf-core/methylseq",
    "methylation": "nf-core/methylseq",
    "scrnaseq": "nf-core/scrnaseq",
    "scrna": "nf-core/scrnaseq",
    "ampliseq": "nf-core/ampliseq",
    "amplicon": "nf-core/ampliseq",
    "16s": "nf-core/ampliseq",
}


@dataclass(frozen=True)
class ProfileRecommendation:
    assay: str
    pipeline: str
    reference: str
    suggested_args: tuple[str, ...]


def recommend_profile(assay: str, reference: str | None = None, offline: bool = False) -> ProfileRecommendation:
    assay_norm = assay.strip().lower()
    ref = (reference or "GRCh38").strip()

    pipeline = _ASSAY_PIPELINE.get(assay_norm, "nf-core/rnaseq")
    args: list[str] = ["--genome", ref]

    if offline:
        # -offline is the Nextflow run-time flag for air-gapped execution
        args.append("-offline")

    return ProfileRecommendation(assay=assay_norm, pipeline=pipeline, reference=ref, suggested_args=tuple(args))
