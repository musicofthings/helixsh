"""Bioinformatics tool resource estimation helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceEstimate:
    tool: str
    assay: str
    samples: int
    cpu_per_sample: int
    memory_gb_per_sample: int
    total_cpu: int
    total_memory_gb: int


DEFAULTS = {
    # RNA-seq
    "star": (8, 32),
    "hisat2": (8, 16),
    "salmon": (2, 8),
    "kallisto": (2, 8),
    "featurecounts": (2, 8),
    "htseq": (1, 4),
    # WGS/WES alignment
    "bwa": (8, 16),
    "bwa-mem2": (8, 24),      # bwa-mem2 uses more memory than bwa
    "minimap2": (8, 16),      # long-read aligner
    "bowtie2": (4, 8),
    # Variant calling
    "gatk": (4, 16),
    "deepvariant": (8, 32),
    "strelka2": (8, 24),
    "mutect2": (4, 16),
    # QC / trimming
    "fastp": (4, 8),
    "trimgalore": (4, 4),
    "fastqc": (2, 4),
    "multiqc": (2, 4),
    # Post-processing
    "samtools": (4, 8),
    "picard": (2, 16),
    "deeptools": (8, 16),
    # Single-cell
    "cellranger": (16, 64),
    "starsolo": (8, 32),
    # Methylation
    "bismark": (4, 16),
}


def estimate_resources(tool: str, assay: str, samples: int, cpu_multiplier: float = 1.0, memory_multiplier: float = 1.0) -> ResourceEstimate:
    tool_norm = tool.strip().lower()
    assay_norm = assay.strip().lower()
    if samples <= 0:
        raise ValueError("samples must be > 0")

    cpu, mem = DEFAULTS.get(tool_norm, (2, 4))

    # Assay-specific memory adjustments for high-depth data
    if assay_norm in {"wgs", "wes"} and tool_norm in {"bwa", "bwa-mem2", "gatk", "deepvariant", "mutect2", "strelka2"}:
        mem += 8
    if assay_norm == "rnaseq" and tool_norm in {"star", "hisat2"}:
        mem += 8
    if assay_norm in {"atac-seq", "atacseq"} and tool_norm in {"bowtie2", "deeptools"}:
        mem += 4

    cpu_adj = max(1, int(round(cpu * cpu_multiplier)))
    mem_adj = max(1, int(round(mem * memory_multiplier)))

    return ResourceEstimate(
        tool=tool_norm,
        assay=assay_norm,
        samples=samples,
        cpu_per_sample=cpu_adj,
        memory_gb_per_sample=mem_adj,
        total_cpu=cpu_adj * samples,
        total_memory_gb=mem_adj * samples,
    )
