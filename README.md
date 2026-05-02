# helixsh

**Bioinformatics-first AI shell for Nextflow and nf-core.**

helixsh is a zero-dependency Python CLI that wraps Nextflow and nf-core pipelines with intent parsing, schema validation, resource estimation, audit trails, cloud cost estimates, HPC environment module generation, Seqera Platform integration, and more — all without any PyPI dependencies beyond Python 3.10+.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Zero dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Desktop UI](#desktop-ui)
- [Commands Reference](#commands-reference)
  - [Core Execution](#core-execution)
  - [Intent Parsing](#intent-parsing)
  - [nf-core Pipelines](#nf-core-pipelines)
  - [Samplesheet Tools](#samplesheet-tools)
  - [Reference Genomes](#reference-genomes)
  - [Bioconda Integration](#bioconda-integration)
  - [Trace & Cost Analysis](#trace--cost-analysis)
  - [Seqera Platform (Tower)](#seqera-platform-tower)
  - [HPC Environment Modules](#hpc-environment-modules)
  - [Snakemake Bridge](#snakemake-bridge)
  - [Schema & Validation](#schema--validation)
  - [Resource Estimation](#resource-estimation)
  - [AI Planning (MCP)](#ai-planning-mcp)
  - [Diagnostics](#diagnostics)
  - [Audit & Provenance](#audit--provenance)
  - [Security & Compliance](#security--compliance)
- [RBAC: Role-Based Access](#rbac-role-based-access)
- [Environment Variables](#environment-variables)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Local Development](#local-development)
- [Packaging](#packaging)
  - [CLI executable (.pyz)](#cli-executable-pyz)
  - [Desktop app](#desktop-app)

---

## Features

| Category | Capabilities |
|---|---|
| **Execution** | Nextflow run with Docker, Podman, Singularity, Apptainer, Conda |
| **Intent** | Natural-language → Nextflow plan (RNA-seq, WGS, WES, ChIP-seq, ATAC-seq, …) |
| **Pipelines** | 20-pipeline bundled registry with version checks |
| **Samplesheets** | Validate and auto-generate nf-core CSV samplesheets |
| **References** | Download and cache GRCh38, GRCh37, GRCm39, TAIR10, and more |
| **Bioconda** | Search, install packages, create environments (dry-run safe) |
| **Tracing** | Parse Nextflow `trace.txt` into per-process summaries |
| **Cost** | AWS / GCP / Azure on-demand and spot cost estimates |
| **Tower** | Submit, monitor, and list compute envs on Seqera Platform |
| **HPC** | Generate `modules.config` for Lmod / Environment Modules clusters |
| **Snakemake** | Import rule-level resource declarations into helixsh calibration |
| **Audit** | SQLite provenance DB, HMAC-signed JSONL audit log |
| **RBAC** | Auditor / Analyst / Admin roles with per-command enforcement |
| **MCP** | Claude Code proposal → approve → execute pipeline |

---

## Installation

### Option 1 — pip (editable install)

```bash
git clone https://github.com/musicofthings/helixsh
cd helixsh
python -m venv .venv
source .venv/bin/activate
pip install -e .
helixsh doctor
```

### Option 2 — single-file executable (`.pyz`)

Build a self-contained zipapp that runs on any Python 3.10+ without a venv:

```bash
./scripts/package_local.sh
./dist/helixsh.pyz doctor
```

Copy `dist/helixsh.pyz` anywhere on your `$PATH` and rename it `helixsh`.

### Option 3 — run without installing

```bash
python -m helixsh doctor
```

### Option 4 — Desktop UI (Tauri app)

Download the pre-built installer for your platform from the [Releases](https://github.com/musicofthings/helixsh/releases) page:

| Platform | File |
|---|---|
| **Linux (deb)** | `helixsh_<version>_amd64.deb` |
| **Linux (AppImage)** | `helixsh_<version>_amd64.AppImage` |
| **macOS** | `helixsh_<version>_x64.dmg` |
| **Windows** | `helixsh_<version>_x64-setup.exe` |

Or build from source — see [Desktop app](#desktop-app) under Packaging.

The desktop app automatically detects the helixsh CLI via: bundled sidecar → `PATH` → `python3 -m helixsh`.

### Requirements

| Requirement | Notes |
|---|---|
| Python 3.10+ | No third-party packages needed |
| Nextflow 25.x | `java` 17+ must be on `$PATH` |
| Docker / Podman / Singularity / Apptainer | At least one container runtime |
| conda / mamba (optional) | For `-with-conda` workflows |

---

## Quick Start

```bash
# Check your environment
helixsh doctor

# Parse a natural-language intent into a Nextflow plan
helixsh intent "run nf-core rnaseq on tumor-normal samples using docker"

# Suggest a pipeline and profile for an assay
helixsh profile-suggest --assay wgs --reference GRCh38

# Validate a samplesheet
helixsh samplesheet-validate --file samplesheet.csv --pipeline rnaseq

# Auto-generate a samplesheet from a FASTQ directory
helixsh samplesheet-generate --fastq-dir /data/fastq --pipeline rnaseq --out samplesheet.csv

# Run an nf-core pipeline (dry-run by default, add --execute to run for real)
helixsh run nf-core/rnaseq --runtime docker --input samplesheet.csv --resume

# Estimate cloud cost before submitting
helixsh cost-estimate --cpu 32 --memory-gb 128 --hours 6 --provider aws

# View Nextflow trace summary
helixsh trace-summary --file results/pipeline_info/trace.txt

# Download a reference genome
helixsh ref-download --genome GRCh38 --cache-root /ref --execute

# Submit to Seqera Platform
helixsh tower-submit --pipeline nf-core/rnaseq --profile docker \
    --work-dir s3://my-bucket/work --execute
```

---

## Desktop UI

helixsh ships a native desktop application built with [Tauri v2](https://tauri.app) + Svelte. It provides a Warp-inspired shell interface with real-time streaming output, intent mode, and integrated environment management — all backed by the same helixsh CLI.

### Interface overview

```
┌─────────────────────────────────────────────────┐
│  ● ─ ■   helixsh                     _  □  ✕   │  ← custom titlebar
├──────────┬──────────────────────────────────────┤
│ tools    │                                      │
│ pipeline │   Command output blocks appear here   │  ← main area
│ history  │   (streaming stdout/stderr, status)   │
│          │                                      │
│  Environ │                                      │
│  ─────── │                                      │
│  ✔ java  │                                      │
│  ✔ nf    │                                      │
│  ✘ conda │                                      │
│          │                                      │
│  Role    │                                      │
│  analyst │                                      │
├──────────┴──────────────────────────────────────┤
│ ❯  Enter a helixsh command…              🔓  ▶  │  ← command bar
└─────────────────────────────────────────────────┘
```

### Command bar

| Action | How |
|---|---|
| Run a command | Type command and press **Enter** |
| Intent mode | Click **⚡** (or type a natural-language description) |
| Autocomplete | Start typing — suggestions appear above the bar; **Tab** to accept |
| Command history | **↑ / ↓** arrow keys |
| Strict mode | Click **🔒** to require `--execute` on all side-effecting commands |

**Command mode** — type helixsh commands directly:

```
run nf-core/rnaseq --input samplesheet.csv --runtime docker
```

**Intent mode** (click ⚡ to switch) — describe what you want in plain English:

```
run RNA-seq on tumor-normal samples using docker, reference GRCh38
```

helixsh translates the description into a Nextflow plan before executing.

### Sidebar tabs

**Tools** — Environment doctor shows which required tools (Nextflow, Java, Docker, Conda, etc.) are installed, with version details. Click **↻ Refresh** to re-check after installing something.

**Pipelines** — Browsable list of all nf-core pipelines in the bundled registry.

**History** — Previous commands from the current session.

### Role selector

Select your access role in the **Tools** tab to enforce RBAC policy on every command:

| Role | Access |
|---|---|
| `auditor` | Read-only (no execution commands) |
| `analyst` | Standard pipeline execution (default) |
| `admin` | Full access including provenance and security commands |

The role is injected as `--role <role>` on every invocation.

### Output blocks

Each command produces a collapsible output block showing:
- Command name and arguments
- Streaming stdout/stderr lines in real time
- Exit status badge (`success` / `error`) and exit code
- Timestamp

---

## Commands Reference

Global flags available on every command:

```
helixsh [--strict] [--role auditor|analyst|admin] <command> [options]
```

- `--strict` — require explicit `--execute` and `--yes` for all side-effecting commands
- `--role` — enforce RBAC policy (default: `analyst`)

---

### Core Execution

#### `run`

Run an nf-core pipeline via Nextflow.

```bash
helixsh run nf-core/rnaseq \
    --runtime docker \
    --input samplesheet.csv \
    --resume \
    --outdir results/

# With additional nextflow args
helixsh run nf-core/sarek \
    --runtime singularity \
    --input samplesheet.csv \
    -- --genome GRCh38 --tools haplotypecaller
```

Options:

| Flag | Description |
|---|---|
| `--runtime` | `docker`, `podman`, `singularity`, `apptainer`, `conda` |
| `--input` | Path to samplesheet CSV |
| `--resume` | Add `-resume` to resume from cache |
| `--outdir` | Output directory |
| `--offline` | Add `-offline` flag (use cached containers) |
| `--execute` | Actually run (default is dry-run preview) |

#### `doctor`

Check that all required tools are installed and show their versions.

```bash
helixsh doctor
```

Checks: `nextflow`, `java`, `docker`, `podman`, `singularity`, `apptainer`, `conda`, `mamba`, `micromamba`, `git`.

#### `plan`

Display planning guidance for building a Nextflow command.

```bash
helixsh plan
```

#### `posix-wrap`

Render an explicit POSIX `exec sh -c` boundary wrapper.

```bash
helixsh posix-wrap nextflow run nf-core/rnaseq -profile docker --input s.csv
# Add --execute to actually run it
helixsh posix-wrap --execute nextflow run nf-core/rnaseq -profile docker --input s.csv
```

#### `preflight`

Run all pre-flight checks in one shot before execution.

```bash
helixsh preflight \
    --schema nextflow_schema.json \
    --params params.json \
    --workflow main.nf \
    --cache-root .helixsh_cache \
    --samplesheet samplesheet.csv \
    --config nextflow.config \
    --image ghcr.io/nf-core/rnaseq@sha256:abc123
```

---

### Intent Parsing

#### `intent`

Map a natural-language request to a concrete Nextflow plan.

```bash
helixsh intent "run nf-core rnaseq on tumor-normal samples using docker"
helixsh intent "analyse chip-seq data with singularity resume if possible"
helixsh intent "run scrna-seq offline with apptainer"
helixsh intent "process amplicon 16S data with conda"
```

Supported pipelines detected by intent: `rnaseq`, `sarek`, `chipseq`, `atacseq`, `methylseq`, `scrnaseq`, `ampliseq`.

#### `profile-suggest`

Suggest a pipeline and Nextflow profile arguments based on assay and reference.

```bash
helixsh profile-suggest --assay rnaseq --reference GRCh38
helixsh profile-suggest --assay wgs --reference GRCh37 --offline
helixsh profile-suggest --assay chip-seq
```

---

### nf-core Pipelines

#### `nf-list`

List all curated nf-core pipelines with descriptions.

```bash
helixsh nf-list
```

#### `nf-launch`

Launch a pipeline using `nextflow launch` or Seqera Platform.

```bash
helixsh nf-launch nf-core/rnaseq \
    --revision 3.14.0 \
    --profile docker \
    --outdir results/ \
    --params '{"genome":"GRCh38","aligner":"star_salmon"}' \
    --execute
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--revision` | `main` | Pipeline revision / tag |
| `--profile` | `docker` | Nextflow profile |
| `--outdir` | `results/` | Output directory |
| `--params` | — | JSON string of pipeline params |
| `--work-dir` | — | Nextflow work directory |
| `--execute` | — | Actually launch (default: dry-run) |

#### `nf-auth`

Show Seqera Platform (`TOWER_ACCESS_TOKEN`) authentication status.

```bash
helixsh nf-auth
```

#### `pipeline-list`

List known nf-core pipelines with their latest version from the bundled registry.

```bash
helixsh pipeline-list
# Force refresh from nf-core API
helixsh pipeline-list --refresh
```

#### `pipeline-update`

Check if a pinned pipeline version matches the latest release.

```bash
helixsh pipeline-update nf-core/rnaseq --pinned 3.12.0
helixsh pipeline-update nf-core/sarek --pinned 3.4.0 --refresh
```

---

### Samplesheet Tools

#### `samplesheet-validate`

Validate an nf-core samplesheet CSV for required columns and data integrity.

```bash
helixsh samplesheet-validate --file samplesheet.csv --pipeline rnaseq
helixsh samplesheet-validate --file samplesheet.csv --pipeline sarek
```

Checks: required columns present, `fastq_1` files exist, paired-end consistency, strandedness values.

#### `samplesheet-generate`

Auto-generate an nf-core samplesheet by scanning a FASTQ directory for R1/R2 pairs.

```bash
helixsh samplesheet-generate \
    --fastq-dir /data/fastq/ \
    --pipeline rnaseq \
    --strandedness reverse \
    --out samplesheet.csv
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--fastq-dir` | — | Directory containing FASTQ files |
| `--pipeline` | `rnaseq` | Target pipeline (affects column names) |
| `--strandedness` | `auto` | `forward`, `reverse`, `unstranded`, `auto` |
| `--out` | `samplesheet.csv` | Output file path |

---

### Reference Genomes

#### `ref-list`

List all reference genomes in the built-in catalogue.

```bash
helixsh ref-list
```

Available genomes: `GRCh38`, `GRCh37`, `GRCm39`, `GRCm38`, `TAIR10`, `R64-1-1`, `WBcel235`.

#### `ref-download`

Download and cache a reference genome (FASTA + GTF) from Ensembl.

```bash
# Dry-run (show what would be downloaded)
helixsh ref-download --genome GRCh38 --cache-root /ref/cache

# Actually download
helixsh ref-download --genome GRCh38 --cache-root /ref/cache --execute
helixsh ref-download --genome GRCm39 --cache-root ~/helixsh_refs --execute
```

Files are stored at `<cache-root>/<genome>/` with SHA-256 checksums written alongside each file.

---

### Bioconda Integration

#### `conda-search`

Search the Bioconda channel for a tool.

```bash
helixsh conda-search samtools
helixsh conda-search star
helixsh conda-search gatk4
```

#### `conda-install`

Install one or more Bioconda packages (dry-run by default).

```bash
# Preview install command
helixsh conda-install samtools bwa-mem2

# Install into a specific environment
helixsh conda-install samtools --env-name myenv

# Actually execute the install
helixsh conda-install samtools bwa-mem2 --execute
```

#### `conda-env`

Create a complete conda environment with Bioconda tools (dry-run by default).

```bash
# Preview environment creation
helixsh conda-env myenv --tools samtools,bwa-mem2,gatk4

# Specify Python version
helixsh conda-env myenv --tools star,salmon --python-version 3.11

# Actually create it
helixsh conda-env myenv --tools samtools,bwa-mem2 --execute
```

All conda commands use the recommended channel stack:
`conda-forge → bioconda` with `--strict-channel-priority` and `defaults` channel removed.

---

### Trace & Cost Analysis

#### `trace-summary`

Parse a Nextflow `trace.txt` file and show per-process resource usage.

```bash
helixsh trace-summary --file results/pipeline_info/trace.txt
```

Output includes: total tasks, failed count, per-process CPU time, memory, wall time, and I/O.

#### `cost-estimate`

Estimate cloud cost for a pipeline run across AWS, GCP, and Azure.

```bash
# Basic estimate
helixsh cost-estimate --cpu 32 --memory-gb 128 --hours 6

# Provider-specific with instance family
helixsh cost-estimate --cpu 64 --memory-gb 256 --hours 12 \
    --provider aws --instance-family compute

# Compare all providers
helixsh cost-estimate --cpu 32 --memory-gb 128 --hours 6 --compare

# Override pricing
helixsh cost-estimate --cpu 32 --memory-gb 128 --hours 6 \
    --price-per-cpu-hour 0.04 --price-per-gb-hour 0.005
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--cpu` | — | Total vCPU count |
| `--memory-gb` | — | Total memory in GB |
| `--hours` | — | Estimated wall-clock hours |
| `--provider` | `aws` | `aws`, `gcp`, `azure` |
| `--instance-family` | `general` | `general`, `compute`, `memory`, `spot` |
| `--compare` | — | Show all three providers |

---

### Seqera Platform (Tower)

Set `TOWER_ACCESS_TOKEN` (and optionally `TOWER_WORKSPACE_ID`) before using these commands.

```bash
export TOWER_ACCESS_TOKEN=your_token_here
export TOWER_WORKSPACE_ID=12345   # optional
```

#### `tower-auth`

Verify your Seqera Platform token and connectivity.

```bash
helixsh tower-auth
```

#### `tower-submit`

Submit a pipeline run to Seqera Platform REST API.

```bash
# Dry-run (default)
helixsh tower-submit \
    --pipeline nf-core/rnaseq \
    --revision 3.14.0 \
    --profile docker \
    --work-dir s3://my-bucket/work

# Actually submit
helixsh tower-submit \
    --pipeline nf-core/rnaseq \
    --profile docker \
    --work-dir s3://my-bucket/work \
    --params '{"genome":"GRCh38","input":"s3://my-bucket/samplesheet.csv"}' \
    --execute
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--pipeline` | — | Pipeline name (e.g. `nf-core/rnaseq`) |
| `--revision` | `main` | Git revision / tag |
| `--profile` | `docker` | Nextflow profile |
| `--work-dir` | `s3://your-bucket/work` | Work directory |
| `--params` | — | JSON string of pipeline params |
| `--compute-env-id` | — | Seqera compute environment ID |
| `--workspace-id` | — | Override `TOWER_WORKSPACE_ID` |
| `--execute` | — | Actually submit |

#### `tower-status`

Get the status of a submitted workflow run.

```bash
helixsh tower-status --workflow-id 1abc23def456
```

#### `tower-envs`

List available compute environments in your workspace.

```bash
helixsh tower-envs
helixsh tower-envs --workspace-id 12345
```

---

### HPC Environment Modules

For clusters running Lmod or Environment Modules (no container runtime).

#### `envmodules-list`

List all tools with known HPC module names.

```bash
helixsh envmodules-list
```

Includes 25+ tools: STAR, HISAT2, BWA, samtools, GATK, Salmon, fastp, MultiQC, and more.

#### `envmodules-wrap`

Generate a Nextflow `modules.config` that loads HPC environment modules per process.

```bash
# Print to stdout
helixsh envmodules-wrap star samtools gatk4 salmon multiqc

# Write to file
helixsh envmodules-wrap star samtools gatk4 \
    --out modules.config \
    --process-prefix nf-core

# Include in a Nextflow run
nextflow run nf-core/rnaseq -profile hpc -c modules.config
```

---

### Snakemake Bridge

#### `snakemake-import`

Import resource declarations (threads, mem_mb, runtime) from a Snakefile into helixsh calibration format.

```bash
# Show extracted resources as JSON
helixsh snakemake-import --file Snakefile

# Export as helixsh calibration file
helixsh snakemake-import --file Snakefile \
    --export-calibration calibration.json
```

---

### Schema & Validation

#### `validate-schema`

Validate a parameters JSON file against an nf-core-style schema.

```bash
helixsh validate-schema \
    --schema nextflow_schema.json \
    --params params.json
```

#### `context-check`

Summarize a samplesheet and `nextflow.config` defaults.

```bash
helixsh context-check \
    --samplesheet samplesheet.csv \
    --config nextflow.config
```

#### `offline-check`

Check offline cache readiness (schemas, containers, assets).

```bash
helixsh offline-check --cache-root .helixsh_cache
```

#### `parse-workflow`

Parse Nextflow process blocks from a `.nf` file and check container policy.

```bash
helixsh parse-workflow --file main.nf
```

---

### Resource Estimation

#### `resource-estimate`

Estimate CPU and memory requirements for a tool, assay, and sample count.

```bash
helixsh resource-estimate --tool star --assay rnaseq --samples 8
helixsh resource-estimate --tool gatk4 --assay wgs --samples 4

# With empirical calibration multipliers
helixsh resource-estimate --tool salmon --assay rnaseq \
    --samples 12 --calibration calibration.json
```

#### `fit-calibration`

Fit calibration multipliers from an observations JSON file.

```bash
helixsh fit-calibration \
    --observations observations.json \
    --out calibration.json
```

The observations file is a JSON array of `{"tool": "star", "cpu_actual": 12, "mem_actual_gb": 38, ...}` records collected from real runs.

---

### AI Planning (MCP)

helixsh uses a proposal-review-execute pattern so AI suggestions never run without human approval.

#### `claude-plan`

Generate a Claude AI plan proposal and store it for review.

```bash
helixsh claude-plan --prompt "fix schema validation for tumor-normal sarek run"
```

#### `mcp-check`

Check whether an MCP gateway capability is permitted.

```bash
helixsh mcp-check execute_commands
helixsh mcp-check read_files
```

#### `mcp-propose`

Store a proposal for review.

```bash
helixsh mcp-propose \
    --kind file_patch \
    --summary "update nextflow.config memory settings" \
    --payload '{"file":"nextflow.config","patch":"..."}'
```

#### `mcp-proposals`

List all pending proposals.

```bash
helixsh mcp-proposals
```

#### `mcp-approve`

Approve a proposal by ID.

```bash
helixsh mcp-approve --id 1
```

#### `mcp-execute`

Execute an approved proposal.

```bash
helixsh mcp-execute --id 1
```

---

### Diagnostics

#### `diagnose`

Diagnose a failed Nextflow process by exit code.

```bash
helixsh diagnose --process QUANTIFY --exit-code 137
helixsh diagnose --process ALIGN_READS --exit-code 137 --memory-gb 4
helixsh diagnose --process TRIM_READS --exit-code 1
```

Common exit codes interpreted: `137` (OOM), `139` (segfault), `143` (SIGTERM), `127` (command not found), `1` (general failure).

#### `cache-report`

Summarize pipeline cache and resume efficiency.

```bash
helixsh cache-report --total 120 --cached 98 --invalidated ALIGN_READS,INDEX_GENOME
```

#### `explain`

Explain the latest command plan.

```bash
helixsh explain last
```

#### `roadmap-status`

Show current helixsh development roadmap completion status.

```bash
helixsh roadmap-status
```

---

### Audit & Provenance

#### `execution-start`

Record the start of a pipeline execution in the SQLite provenance database.

```bash
helixsh execution-start \
    --command "nextflow run nf-core/rnaseq" \
    --params '{"genome":"GRCh38","input":"samplesheet.csv"}' \
    --pipeline nf-core/rnaseq \
    --profile docker
```

Returns an execution ID used for subsequent `execution-finish` and `audit-show` calls.

#### `execution-finish`

Record the completion of a pipeline execution.

```bash
helixsh execution-finish \
    --id exec_20250101_abc123 \
    --status success \
    --exit-code 0
```

#### `audit-show`

Show the full execution bundle from the provenance DB.

```bash
helixsh audit-show --id exec_20250101_abc123
```

#### `audit-export`

Export the JSONL audit log with a reproducible SHA-256 digest.

```bash
helixsh audit-export --out audit_export.json
```

#### `audit-verify`

Verify the integrity and shape of the audit log.

```bash
helixsh audit-verify
```

#### `audit-sign`

Sign the audit log with an HMAC key.

```bash
helixsh audit-sign --key-file audit.key --out audit.sig
```

#### `audit-verify-signature`

Verify an HMAC-signed audit log.

```bash
helixsh audit-verify-signature \
    --key-file audit.key \
    --signature-file audit.sig
```

#### `provenance`

Generate a reproducible execution hash record.

```bash
helixsh provenance \
    --command "nextflow run nf-core/rnaseq" \
    --params '{"genome":"GRCh38","aligner":"star_salmon"}'
```

---

### Security & Compliance

#### `image-check`

Check whether a container image has a pinned digest (required for reproducibility).

```bash
helixsh image-check --image ghcr.io/nf-core/rnaseq@sha256:abc123...
helixsh image-check --image biocontainers/samtools:1.17
```

#### `rbac-check`

Check whether a role is permitted to perform an action.

```bash
helixsh rbac-check --role auditor --action run
helixsh rbac-check --role analyst --action conda-install
helixsh rbac-check --role admin --action conda-install
```

#### `compliance-check`

Evaluate clinical compliance policy for container images and model confidence.

```bash
helixsh compliance-check \
    --images ghcr.io/nf-core/rnaseq@sha256:abc123 \
    --agreement-score 0.9 \
    --confidences 0.85 0.92
```

#### `agent-run`

Run an agent task via the HAPS v1 (Helix Agent Protocol Spec).

```bash
helixsh agent-run \
    --agent variant_classification \
    --task "classify variants from sarek VCF" \
    --payload '{"vcf":"variants.vcf"}'
```

#### `arbitrate`

Arbitrate between multiple agent responses using a strategy.

```bash
helixsh arbitrate \
    --responses responses.json \
    --strategy majority_vote
```

---

## RBAC: Role-Based Access

Every command is gated by one of three built-in roles. Pass `--role <role>` globally or set the default via your organisation's deployment.

| Role | Description | Additional permissions vs. previous role |
|---|---|---|
| `auditor` | Read-only inspection | `doctor`, `explain`, `plan`, `validate-schema`, `parse-workflow`, `diagnose`, `cache-report`, `roadmap-status`, `rbac-check`, `report`, `context-check`, `offline-check`, `audit-export`, `audit-verify`, `audit-sign`, `audit-verify-signature`, `resource-estimate`, `fit-calibration`, `image-check`, `agent-run`, `arbitrate`, `compliance-check`, `mcp-check`, `mcp-proposals`, `nf-auth`, `ref-list`, `pipeline-list`, `envmodules-list`, `tower-auth`, `tower-status`, `tower-envs`, `trace-summary`, `cost-estimate` |
| `analyst` | + pipeline operations | All auditor commands + `run`, `intent`, `profile-suggest`, `provenance`, `posix-wrap`, `preflight`, `execution-start`, `execution-finish`, `audit-show`, `mcp-propose`, `mcp-approve`, `mcp-execute`, `claude-plan`, `nf-launch`, `samplesheet-validate`, `samplesheet-generate`, `ref-download`, `pipeline-update`, `envmodules-wrap`, `tower-submit`, `snakemake-import` |
| `admin` | + environment management | All analyst commands + `conda-install`, `conda-env`, `conda-search` |

Example:

```bash
# Auditor: read-only checks
helixsh --role auditor doctor
helixsh --role auditor trace-summary --file trace.txt

# Analyst: run pipelines
helixsh --role analyst run nf-core/rnaseq --runtime docker --input s.csv

# Admin: install tools
helixsh --role admin conda-install star salmon
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TOWER_ACCESS_TOKEN` | For Tower commands | Seqera Platform personal access token |
| `TOWER_API_ENDPOINT` | No | Default: `https://api.cloud.seqera.io` |
| `TOWER_WORKSPACE_ID` | No | Seqera workspace numeric ID |
| `HELIXSH_AUDIT_FILE` | No | Path to audit JSONL (default: `.helixsh_audit.jsonl`) |
| `HELIXSH_PROVENANCE_DB` | No | Path to SQLite provenance DB (default: `.helixsh_provenance.db`) |

---

## Configuration

### Strict mode

Strict mode prevents any side-effecting command from running without `--execute` and `--yes`:

```bash
helixsh --strict run nf-core/rnaseq --runtime docker --input s.csv
# → blocked: requires --execute --yes

helixsh --strict run nf-core/rnaseq --runtime docker --input s.csv --execute --yes
# → runs
```

Use strict mode in clinical genomics, regulated HPC, or production environments.

### Audit log

All commands append a structured JSONL entry to `.helixsh_audit.jsonl` including:

- Timestamp, role, command, parameters
- Reproducible execution hash (SHA-256)
- Container images used

### Provenance database

All pipeline executions are recorded in an SQLite database (`.helixsh_provenance.db`) with full parameter sets, execution IDs, status, and timing.

---

## Architecture

```
┌─────────────────────────────────────┐
│           helixsh CLI               │
│  (argparse, zero external deps)     │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
┌─────────────┐   ┌───────────────┐
│ Intent &    │   │ Validation &  │
│ Context     │   │ Schema Layer  │
│ intent.py   │   │ schema.py     │
│ profiles.py │   │ context.py    │
│ resources.py│   │ workflow.py   │
└──────┬──────┘   └───────┬───────┘
       │                  │
       └────────┬─────────┘
                ▼
    ┌───────────────────────┐
    │   Execution Layer     │
    │  nextflow.py          │
    │  nf_launch.py         │
    │  bioconda.py          │
    │  tower.py             │
    └───────────┬───────────┘
                │
    ┌───────────┴───────────┐
    │   Audit & Provenance  │
    │  provenance_db.py     │
    │  signing.py           │
    │  compliance.py        │
    └───────────────────────┘
```

### Key design decisions

- **Zero external dependencies** — everything uses Python stdlib only (`urllib`, `csv`, `json`, `re`, `subprocess`, `sqlite3`, `hashlib`).
- **Dry-run by default** — all destructive operations (downloads, conda installs, Tower submissions, Nextflow runs) require explicit `--execute`.
- **Nextflow is the authority** — helixsh plans, validates, and diagnoses; it never replaces Nextflow.
- **Brace-aware DSL2 parsing** — process block extraction uses a depth-tracking brace parser, not fragile regex.

---

## Local Development

```bash
# Clone and set up
git clone https://github.com/musicofthings/helixsh
cd helixsh
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run the full test suite
pytest

# Run a specific test file
pytest tests/test_features.py -v

# Run with coverage
pytest --tb=short -q
```

The test suite covers 188+ tests across all modules with no network calls (all external I/O is mocked or bypassed by dry-run defaults).

---

## Packaging

### CLI executable (.pyz)

Build a single-file Python zipapp for distribution:

```bash
./scripts/package_local.sh
ls -lh dist/helixsh.pyz
```

The `.pyz` runs on any machine with Python 3.10+ — no installation required.

```bash
chmod +x dist/helixsh.pyz
./dist/helixsh.pyz doctor
```

### Desktop app

Build a native installer for the current platform:

```bash
./scripts/package_ui.sh
```

This runs `npm ci` then `tauri build` and produces platform-specific installable packages:

| Platform | Output | Install |
|---|---|---|
| **Linux** | `bundle/deb/*.deb` | `sudo dpkg -i *.deb` |
| **Linux** | `bundle/appimage/*.AppImage` | `chmod +x *.AppImage && ./helixsh.AppImage` |
| **macOS** | `bundle/dmg/*.dmg` | Open dmg, drag to `/Applications` |
| **Windows** | `bundle/nsis/*-setup.exe` | Run the NSIS installer |

All output lands in `ui/src-tauri/target/release/bundle/`.

**Prerequisites for building:**

- Node.js 18+, Rust (stable), `cargo`
- Linux: `sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev libgtk-3-dev libgdk-pixbuf-2.0-dev`
- macOS: Xcode Command Line Tools (`xcode-select --install`)
- Windows: Visual Studio Build Tools with the "Desktop development with C++" workload

To build a debug binary (faster compile, larger binary, DevTools enabled):

```bash
./scripts/package_ui.sh --debug
```
