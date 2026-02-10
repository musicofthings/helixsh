"""Bioinformatics profile/recommendation helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileRecommendation:
    assay: str
    pipeline: str
    reference: str
    suggested_args: tuple[str, ...]


def recommend_profile(assay: str, reference: str | None = None, offline: bool = False) -> ProfileRecommendation:
    assay_norm = assay.strip().lower()
    ref = (reference or "GRCh38").strip()

    if assay_norm in {"wgs", "wes"}:
        pipeline = "nf-core/sarek"
        args = ["--genome", ref]
    elif assay_norm in {"chip-seq", "chipseq"}:
        pipeline = "nf-core/chipseq"
        args = ["--genome", ref]
    else:
        pipeline = "nf-core/rnaseq"
        args = ["--genome", ref]

    if offline:
        args.extend(["-offline", "-with-trace"])

    return ProfileRecommendation(assay=assay_norm, pipeline=pipeline, reference=ref, suggested_args=tuple(args))
