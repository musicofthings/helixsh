"""Reference genome download and cache management helpers.

Provides a catalogue of common reference genomes (iGenomes / Ensembl) with
download URLs and expected SHA-256 checksums.  Downloads use Python's stdlib
`urllib.request` so there are no external dependencies.

Supported genomes (subset — extend GENOME_CATALOGUE as needed):
  GRCh38, GRCh37, GRCm39, GRCm38, TAIR10, R64-1-1, WBcel235

Cache layout:
  <cache_root>/
    <genome>/
      genome.fa.gz
      genome.fa.gz.sha256
      annotation.gtf.gz
      annotation.gtf.gz.sha256
"""

from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# Catalogue entry: genome_id -> {fasta_url, fasta_sha256, gtf_url, gtf_sha256, source}
# URLs point to AWS iGenomes (public S3) or Ensembl FTP.
# SHA-256 values are placeholders — real deployments should pin these from a
# verified source (e.g. nf-core/references or Ensembl release notes).
GENOME_CATALOGUE: dict[str, dict[str, str]] = {
    "GRCh38": {
        "source": "Ensembl",
        "species": "Homo sapiens",
        "fasta_url": "https://ftp.ensembl.org/pub/release-113/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz",
        "gtf_url":   "https://ftp.ensembl.org/pub/release-113/gtf/homo_sapiens/Homo_sapiens.GRCh38.113.gtf.gz",
        "fasta_sha256": "",  # pin after first download via verify_checksum()
        "gtf_sha256":   "",
    },
    "GRCh37": {
        "source": "Ensembl",
        "species": "Homo sapiens (GRCh37/hg19)",
        "fasta_url": "https://ftp.ensembl.org/pub/grch37/release-87/fasta/homo_sapiens/dna/Homo_sapiens.GRCh37.dna.primary_assembly.fa.gz",
        "gtf_url":   "https://ftp.ensembl.org/pub/grch37/release-87/gtf/homo_sapiens/Homo_sapiens.GRCh37.87.gtf.gz",
        "fasta_sha256": "",
        "gtf_sha256":   "",
    },
    "GRCm39": {
        "source": "Ensembl",
        "species": "Mus musculus",
        "fasta_url": "https://ftp.ensembl.org/pub/release-113/fasta/mus_musculus/dna/Mus_musculus.GRCm39.dna.primary_assembly.fa.gz",
        "gtf_url":   "https://ftp.ensembl.org/pub/release-113/gtf/mus_musculus/Mus_musculus.GRCm39.113.gtf.gz",
        "fasta_sha256": "",
        "gtf_sha256":   "",
    },
    "GRCm38": {
        "source": "Ensembl",
        "species": "Mus musculus (GRCm38/mm10)",
        "fasta_url": "https://ftp.ensembl.org/pub/release-102/fasta/mus_musculus/dna/Mus_musculus.GRCm38.dna.primary_assembly.fa.gz",
        "gtf_url":   "https://ftp.ensembl.org/pub/release-102/gtf/mus_musculus/Mus_musculus.GRCm38.102.gtf.gz",
        "fasta_sha256": "",
        "gtf_sha256":   "",
    },
    "TAIR10": {
        "source": "Ensembl Plants",
        "species": "Arabidopsis thaliana",
        "fasta_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-60/fasta/arabidopsis_thaliana/dna/Arabidopsis_thaliana.TAIR10.dna.toplevel.fa.gz",
        "gtf_url":   "https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-60/gtf/arabidopsis_thaliana/Arabidopsis_thaliana.TAIR10.60.gtf.gz",
        "fasta_sha256": "",
        "gtf_sha256":   "",
    },
    "R64-1-1": {
        "source": "Ensembl Fungi",
        "species": "Saccharomyces cerevisiae",
        "fasta_url": "https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-60/fasta/saccharomyces_cerevisiae/dna/Saccharomyces_cerevisiae.R64-1-1.dna.toplevel.fa.gz",
        "gtf_url":   "https://ftp.ensemblgenomes.ebi.ac.uk/pub/fungi/release-60/gtf/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.60.gtf.gz",
        "fasta_sha256": "",
        "gtf_sha256":   "",
    },
    "WBcel235": {
        "source": "Ensembl",
        "species": "Caenorhabditis elegans",
        "fasta_url": "https://ftp.ensembl.org/pub/release-113/fasta/caenorhabditis_elegans/dna/Caenorhabditis_elegans.WBcel235.dna.toplevel.fa.gz",
        "gtf_url":   "https://ftp.ensembl.org/pub/release-113/gtf/caenorhabditis_elegans/Caenorhabditis_elegans.WBcel235.113.gtf.gz",
        "fasta_sha256": "",
        "gtf_sha256":   "",
    },
}


@dataclass
class DownloadPlan:
    genome: str
    cache_root: str
    files: list[dict[str, str]] = field(default_factory=list)
    already_cached: list[str] = field(default_factory=list)


@dataclass
class DownloadResult:
    genome: str
    ok: bool
    dry_run: bool
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected: str) -> bool:
    """Return True if file matches expected SHA-256 (or expected is empty — skip check)."""
    if not expected:
        return True
    return sha256_file(path) == expected


def list_genomes() -> list[dict[str, str]]:
    return [
        {"genome": gid, "species": info["species"], "source": info["source"]}
        for gid, info in GENOME_CATALOGUE.items()
    ]


def plan_download(genome: str, cache_root: str) -> DownloadPlan:
    """Describe what would be downloaded without fetching anything."""
    info = GENOME_CATALOGUE.get(genome)
    if info is None:
        return DownloadPlan(genome=genome, cache_root=cache_root)

    root = Path(cache_root) / genome
    plan = DownloadPlan(genome=genome, cache_root=cache_root)

    for asset, url_key, sha_key in [
        ("fasta", "fasta_url", "fasta_sha256"),
        ("gtf",   "gtf_url",   "gtf_sha256"),
    ]:
        url = info[url_key]
        filename = url.split("/")[-1]
        dest = root / filename
        if dest.exists() and verify_checksum(dest, info[sha_key]):
            plan.already_cached.append(str(dest))
        else:
            plan.files.append({"asset": asset, "url": url, "dest": str(dest),
                                "sha256": info[sha_key]})
    return plan


def download_genome(genome: str, cache_root: str, dry_run: bool = True) -> DownloadResult:
    """Download reference genome files.  Defaults to dry_run=True."""
    plan = plan_download(genome, cache_root)
    result = DownloadResult(genome=genome, ok=True, dry_run=dry_run,
                            skipped=list(plan.already_cached))

    if not plan.files and not plan.already_cached:
        result.ok = False
        result.errors.append(f"Unknown genome '{genome}'. Run ref-list to see available genomes.")
        return result

    if dry_run:
        result.downloaded = [f["dest"] for f in plan.files]
        return result

    root = Path(cache_root) / genome
    root.mkdir(parents=True, exist_ok=True)

    for file_info in plan.files:
        dest = Path(file_info["dest"])
        try:
            urllib.request.urlretrieve(file_info["url"], dest)
            if not verify_checksum(dest, file_info["sha256"]):
                result.errors.append(f"Checksum mismatch: {dest}")
                result.ok = False
            else:
                # Store checksum alongside file for future verification
                dest.with_suffix(dest.suffix + ".sha256").write_text(
                    sha256_file(dest), encoding="utf-8"
                )
                result.downloaded.append(str(dest))
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Failed to download {file_info['url']}: {exc}")
            result.ok = False

    return result
