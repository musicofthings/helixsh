"""Bioconda integration helpers for helixsh.

Bioconda is the primary conda channel for bioinformatics software.  This
module provides dry-run-safe wrappers around conda/mamba to search, install,
and manage environments — matching the zero-external-dependency philosophy
of helixsh (all functionality uses subprocess + stdlib only).

Channel priority (from Bioconda docs, updated Aug 2024):
  conda-forge  (highest)
  bioconda
  (defaults channel removed from recommendation set)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

# Standard Bioconda channel stack — order matters for priority
BIOCONDA_CHANNELS = ["conda-forge", "bioconda"]

# Curated list of popular bioinformatics tools available on Bioconda
KNOWN_TOOLS: dict[str, str] = {
    # Aligners
    "bwa": "bwa",
    "bwa-mem2": "bwa-mem2",
    "minimap2": "minimap2",
    "hisat2": "hisat2",
    "bowtie2": "bowtie2",
    "star": "star",
    "salmon": "salmon",
    "kallisto": "kallisto",
    "bismark": "bismark",
    # Variant calling
    "gatk4": "gatk4",
    "gatk": "gatk4",
    "deepvariant": "deepvariant",
    "strelka": "strelka",
    "freebayes": "freebayes",
    "bcftools": "bcftools",
    "vcftools": "vcftools",
    # QC
    "fastqc": "fastqc",
    "fastp": "fastp",
    "trimgalore": "trim-galore",
    "trim-galore": "trim-galore",
    "multiqc": "multiqc",
    "fastq-screen": "fastq-screen",
    # Post-processing
    "samtools": "samtools",
    "picard": "picard",
    "deeptools": "deeptools",
    "bedtools": "bedtools",
    "subread": "subread",       # featureCounts
    # Single-cell
    "cellranger": "cellranger",
    "starsolo": "star",         # STARsolo ships with STAR
    # Workflow managers
    "nextflow": "nextflow",
    "snakemake": "snakemake",
    # General
    "wget": "wget",
    "curl": "curl",
}


@dataclass
class CondaResult:
    ok: bool
    command: str
    stdout: str
    stderr: str
    returncode: int


@dataclass
class PackageInfo:
    name: str
    channel: str
    versions: list[str]


def _prefer_manager() -> str:
    """Return 'mamba', 'micromamba', or 'conda' — whichever is available."""
    for manager in ("mamba", "micromamba", "conda"):
        try:
            result = subprocess.run(
                [manager, "--version"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                return manager
        except FileNotFoundError:
            continue
    return "conda"  # fallback — will fail gracefully at runtime


def _channel_flags() -> list[str]:
    flags: list[str] = []
    for ch in BIOCONDA_CHANNELS:
        flags.extend(["-c", ch])
    flags.extend(["--strict-channel-priority"])
    return flags


def search_package(package: str) -> PackageInfo:
    """Search Bioconda for a package and return available versions (dry-run safe)."""
    manager = _prefer_manager()
    cmd = [manager, "search", "-c", "bioconda", package, "--json"]
    try:
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        return PackageInfo(name=package, channel="bioconda", versions=[])

    versions: list[str] = []
    if result.returncode == 0:
        import json
        try:
            data = json.loads(result.stdout)
            entries = data.get(package, [])
            seen: set[str] = set()
            for entry in entries:
                v = entry.get("version", "")
                if v and v not in seen:
                    versions.append(v)
                    seen.add(v)
            versions.sort(reverse=True)
        except (json.JSONDecodeError, AttributeError):
            pass

    return PackageInfo(name=package, channel="bioconda", versions=versions)


def build_install_command(packages: list[str], env_name: str | None = None) -> list[str]:
    """Return the conda/mamba install command (does NOT execute it)."""
    manager = _prefer_manager()
    cmd = [manager, "install"]
    if env_name:
        cmd.extend(["-n", env_name])
    cmd.extend(_channel_flags())
    cmd.extend(packages)
    return cmd


def install_packages(packages: list[str], env_name: str | None = None, dry_run: bool = True) -> CondaResult:
    """Install packages from Bioconda.  Defaults to dry_run=True for safety."""
    cmd = build_install_command(packages, env_name)
    if dry_run:
        rendered = " ".join(cmd)
        return CondaResult(ok=True, command=rendered, stdout="", stderr="", returncode=0)
    try:
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return CondaResult(
            ok=result.returncode == 0,
            command=" ".join(cmd),
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )
    except FileNotFoundError as exc:
        return CondaResult(ok=False, command=" ".join(cmd), stdout="", stderr=str(exc), returncode=127)


def build_create_env_command(env_name: str, packages: list[str], python_version: str = "3.12") -> list[str]:
    """Return the conda/mamba env create command (does NOT execute it)."""
    manager = _prefer_manager()
    cmd = [manager, "create", "-n", env_name]
    cmd.extend(_channel_flags())
    cmd.extend([f"python={python_version}"])
    cmd.extend(packages)
    return cmd


def create_env(env_name: str, packages: list[str], python_version: str = "3.12", dry_run: bool = True) -> CondaResult:
    """Create a new conda environment with Bioconda packages."""
    cmd = build_create_env_command(env_name, packages, python_version)
    if dry_run:
        rendered = " ".join(cmd)
        return CondaResult(ok=True, command=rendered, stdout="", stderr="", returncode=0)
    try:
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return CondaResult(
            ok=result.returncode == 0,
            command=" ".join(cmd),
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )
    except FileNotFoundError as exc:
        return CondaResult(ok=False, command=" ".join(cmd), stdout="", stderr=str(exc), returncode=127)


def list_known_tools() -> list[dict[str, str]]:
    """Return a curated list of known Bioconda tools."""
    return [{"tool": alias, "package": pkg} for alias, pkg in sorted(KNOWN_TOOLS.items())]
