# helixsh

**Bioinformatics-first AI shell for Nextflow / nf-core**

helixsh is a POSIX-respecting command-line tool that understands bioinformatics intent, validates Nextflow/nf-core workflows, enforces container policy, estimates resources, and delegates all real execution to deterministic tools. AI is a planner here — not an executor.

---

## Core Principles

1. **POSIX execution boundary** — final execution is always real `sh`/`bash` commands.
2. **Nextflow is the workflow authority** — helixsh plans, validates, explains, and diagnoses; it does not replace Nextflow.
3. **Container-first execution** — Docker / Podman / Singularity are mandatory.
4. **LLM as planner, not executor** — AI proposes plans and fixes; helixsh decides and executes.
5. **Offline-capable by design** — local reasoning, cached schemas, and optional internet access.
6. **Dry-run by default** — nothing runs without `--execute`.

---

## Installation

**Requirements:** Python ≥ 3.10

```bash
git clone https://github.com/musicofthings/helixsh
cd helixsh
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

**Self-contained executable (no venv needed):**

```bash
./scripts/package_local.sh
./dist/helixsh.pyz doctor
```

**Desktop integration (macOS/Linux):**

```bash
./scripts/install_desktop.sh    # install
./scripts/uninstall_desktop.sh  # remove
```

---

## Quick Start

```bash
# Check your environment
helixsh doctor

# Dry-run an RNA-seq pipeline
helixsh run nf-core rnaseq --runtime docker --input samplesheet.csv

# Execute it
helixsh run nf-core rnaseq --runtime docker --input samplesheet.csv --execute

# Natural language → Nextflow plan
helixsh intent "run nf-core rnaseq on tumor-normal samples use docker resume"

# Strict mode for clinical use (requires --execute --yes to run)
helixsh --strict run nf-core sarek --runtime singularity --input samples.csv --execute --yes
```

---

## Command Reference

### Core Execution

| Command | Description |
|---------|-------------|
| `helixsh run nf-core <pipeline>` | Plan or execute an nf-core pipeline via Nextflow |
| `helixsh doctor` | Check environment: Nextflow, Docker, Python, container runtimes |
| `helixsh explain last` | Show the last planned command with provenance hash |
| `helixsh plan` | Display roadmap and planning guidance |
| `helixsh intent "<text>"` | Parse natural language into a Nextflow parameter plan |

**`run` flags:**

```
--runtime docker|podman|singularity|apptainer
--input <samplesheet.csv>
--outdir <results/>
--resume
--offline
--execute          (required to actually run)
--yes              (required in --strict mode)
--nf-arg <flag>    (pass extra flags to nextflow, repeatable)
--org <org>        (default: nf-core)
```

**RBAC-aware execution:**

```bash
helixsh --role analyst  run nf-core rnaseq ...   # default role
helixsh --role auditor  doctor
helixsh --role viewer   explain last
```

---

### Pipeline Discovery

```bash
# List curated nf-core pipelines
helixsh nf-list

# List all known pipelines with latest versions
helixsh pipeline-list

# Check if your pinned version is current
helixsh pipeline-update --pipeline nf-core/rnaseq --pinned 3.14.0

# Refresh pipeline registry cache then check
helixsh pipeline-update --pipeline sarek --pinned 3.4.0 --cache registry.json --refresh

# Suggest profile and pipeline args for an assay
helixsh profile-suggest --assay wgs --reference GRCh38
helixsh profile-suggest --assay rnaseq --offline
```

---

### Samplesheet Tools

```bash
# Generate samplesheet from a directory of FASTQ files
helixsh samplesheet-generate --fastq-dir /data/fastq --pipeline rnaseq --out samplesheet.csv

# Validate an existing samplesheet
helixsh samplesheet-validate --file samplesheet.csv --pipeline rnaseq
```

Supported pipelines for validation: `rnaseq`, `sarek`, `chipseq`, `atacseq`

---

### Reference Genomes

```bash
# List available reference genomes
helixsh ref-list

# Dry-run: show what would be downloaded
helixsh ref-download --genome GRCh38 --cache-root .helixsh_cache/refs

# Actually download
helixsh ref-download --genome GRCh38 --cache-root .helixsh_cache/refs --execute
```

---

### Schema & Preflight Validation

```bash
# Validate params against nf-core JSON schema
helixsh validate-schema --schema schema.json --params params.json

# Parse Nextflow processes, detect container policy violations
helixsh parse-workflow --file main.nf

# Check samplesheet and nextflow.config defaults
helixsh context-check --samplesheet samplesheet.csv --config nextflow.config

# Check offline cache readiness
helixsh offline-check --cache-root .helixsh_cache

# Run all preflight checks in one command
helixsh preflight \
  --schema schema.json \
  --params params.json \
  --workflow main.nf \
  --samplesheet samplesheet.csv \
  --config nextflow.config \
  --cache-root .helixsh_cache \
  --image ghcr.io/nf-core/rnaseq@sha256:abc123...
```

---

### Container Policy

```bash
# Check if an image reference meets digest policy
helixsh image-check --image ghcr.io/nf-core/rnaseq@sha256:abc123...
helixsh image-check --image biocontainers/samtools:1.17
```

Policy rules:
- Image digests (`@sha256:...`) are preferred
- Host binaries are blocked
- Pinned tags are flagged as warnings

---

### Resource Planning & Cloud Cost

```bash
# Estimate CPU/memory for a tool and sample count
helixsh resource-estimate --tool star --assay rnaseq --samples 4
helixsh resource-estimate --tool salmon --assay rnaseq --samples 2 --calibration calibration.json

# Fit calibration multipliers from empirical observations
helixsh fit-calibration --observations observations.json --out calibration.json

# Summarise a Nextflow trace.txt for bottlenecks and failed tasks
helixsh trace-summary --file work/trace.txt

# Estimate cloud cost
helixsh cost-estimate --cpu 32 --memory-gb 128 --hours 4 --provider aws
helixsh cost-estimate --cpu 32 --memory-gb 128 --hours 4 --compare-all
```

---

### Bioconda Integration

```bash
# Search Bioconda for a package
helixsh conda-search --package star

# Dry-run install (shows the conda command)
helixsh conda-install --package star --package samtools

# Actually install into an existing env
helixsh conda-install --package star --env myenv --execute

# Create a new Bioconda environment (dry-run)
helixsh conda-env --name ngs --tool star --tool samtools --tool gatk

# Create it for real
helixsh conda-env --name ngs --tool star --tool samtools --execute
```

---

### HPC / Environment Modules

For HPC clusters that use Lmod/Environment Modules instead of Docker:

```bash
# List tools with known HPC module names
helixsh envmodules-list

# Generate a Nextflow modules.config for HPC
helixsh envmodules-wrap --tool star --tool samtools --out modules.config

# With a process selector prefix
helixsh envmodules-wrap --tool star --tool samtools \
  --process-prefix "NFCORE_RNASEQ:" --out modules.config
```

---

### Seqera Platform / Tower

```bash
# Check authentication status
helixsh nf-auth
helixsh tower-auth

# Launch pipeline via nextflow launch / Seqera Platform (dry-run)
helixsh nf-launch --pipeline nf-core/rnaseq --profile docker \
  --param genome=GRCh38 --param input=samplesheet.csv

# Execute it
helixsh nf-launch --pipeline nf-core/rnaseq --profile docker \
  --param genome=GRCh38 --param input=samplesheet.csv --execute

# Submit to Seqera Platform REST API
helixsh tower-submit --pipeline nf-core/rnaseq --revision 3.14.0 \
  --profile docker --work-dir s3://my-bucket/work \
  --workspace-id 12345 --param genome=GRCh38

# Check run status
helixsh tower-status --workflow-id abc123 --workspace-id 12345

# List compute environments
helixsh tower-envs
```

---

### Failure Diagnosis & Cache

```bash
# Diagnose a failed process
helixsh diagnose --process QUANTIFY --exit-code 137 --memory-gb 4
# → Identifies OOM, suggests increasing memory or switching to kallisto

# Summarise cache/resume efficiency
helixsh cache-report --total 100 --cached 83 --invalidated ALIGN_READS
```

Common exit code interpretations:

| Exit code | Likely cause | Action |
|-----------|--------------|--------|
| 137 | Out of memory (OOM kill) | Increase memory or reduce parallelism |
| 1 | General process failure | Check process log |
| 139 | Segfault | Check tool version / input data |

---

### Audit, Provenance & Compliance

Every `run` command writes to `.helixsh_audit.jsonl` automatically.

```bash
# Verify audit log integrity (hash check)
helixsh audit-verify

# Export audit log with SHA-256 digest
helixsh audit-export --out audit_export.json

# HMAC-sign the audit log
helixsh audit-sign --key-file audit.key --out audit.sig

# Verify the signature
helixsh audit-verify-signature --key-file audit.key --signature-file audit.sig

# Generate validation report for regulated environments
helixsh report \
  --schema-ok --container-policy-ok \
  --cache-percent 95 --diagnostics ok \
  --out validation_report.json

# RBAC: check if a role can take an action
helixsh rbac-check --role auditor --action run

# Clinical compliance check (for AI agent pipelines)
helixsh compliance-check \
  --image biocontainers/gatk:4.4 \
  --agreement-score 0.92 \
  --confidence 0.87
```

**RBAC roles:**

| Role | Permissions |
|------|-------------|
| `analyst` | run, plan, doctor, explain, validate |
| `auditor` | doctor, explain, audit commands (read-only) |
| `viewer` | explain, doctor |

---

### Provenance & Execution Lifecycle

```bash
# Generate a reproducible execution hash record
helixsh provenance \
  --command "nextflow run nf-core/rnaseq" \
  --params '{"genome":"GRCh38","input":"samplesheet.csv"}'

# POSIX wrapper (explicit execution boundary)
helixsh posix-wrap nextflow run nf-core/rnaseq -profile docker --input samplesheet.csv
helixsh posix-wrap nextflow run nf-core/rnaseq --execute   # actually runs it

# Execution lifecycle (SQLite provenance DB)
helixsh execution-start \
  --command "nextflow run nf-core/rnaseq" \
  --workflow main.nf \
  --input samplesheet.csv \
  --image ghcr.io/nf-core/rnaseq@sha256:... \
  --db provenance.db

helixsh execution-finish \
  --execution-id <id> --status success --db provenance.db

helixsh audit-show --execution-id <id> --db provenance.db
```

---

### MCP Gateway & AI Planning

helixsh integrates with Claude Code via a controlled MCP gateway. Claude proposes; helixsh approves and executes.

```bash
# Check if a capability is allowed through the MCP gateway
helixsh mcp-check execute_commands   # → denied
helixsh mcp-check read_logs          # → allowed

# Create a proposal for review
helixsh mcp-propose \
  --kind file_patch \
  --summary "update nextflow.config memory settings" \
  --payload '{"file":"nextflow.config","diff":"..."}'

# List pending proposals
helixsh mcp-proposals

# Approve a proposal
helixsh mcp-approve --id 1

# Execute an approved proposal
helixsh mcp-execute --id 1

# Generate a Claude-style plan and store it as a proposal
helixsh claude-plan --prompt "fix schema mismatch in rnaseq params"
```

**MCP permissions model:**

| Capability | Allowed |
|------------|---------|
| Read logs | Yes |
| Inspect DAG | Yes |
| Modify files | Proposal only |
| Execute commands | No |

---

### Agent Tasks & Arbitration

For multi-agent clinical genomics workflows:

```bash
# Run an agent task via HAPS v1
helixsh agent-run \
  --agent variant-classifier \
  --task classify_variant \
  --model claude-sonnet-4-6 \
  --payload '{"gene":"BRCA1","hgvs":"c.5266dupC"}'

# Arbitrate between multiple agent responses
helixsh arbitrate --responses responses.json --strategy majority
helixsh arbitrate --responses responses.json --strategy weighted_confidence
```

---

### Snakemake Import

Migrate resource declarations from an existing Snakefile:

```bash
# Import resource declarations
helixsh snakemake-import --file Snakefile

# Export as helixsh calibration observations
helixsh snakemake-import --file Snakefile --export-calibration observations.json
```

---

### Roadmap Status

```bash
helixsh roadmap-status   # JSON output of phase completion
```

---

## Architecture

```
┌────────────────────────────┐
│        helixsh CLI         │
│  (POSIX-compatible shell)  │
└──────────────┬─────────────┘
               ↓
┌────────────────────────────┐
│ Intent & Context Layer     │
│  - Bio terminology         │
│  - nf-core schemas         │
│  - Sample metadata         │
└──────────────┬─────────────┘
               ↓
┌────────────────────────────┐
│ Workflow Intelligence      │
│  - Nextflow AST            │
│  - Process graph (DAG)     │
│  - Resume/cache semantics  │
└──────────────┬─────────────┘
               ↓
┌────────────────────────────┐
│ Container Orchestrator     │
│  - Docker / Podman         │
│  - MCP Gateway             │
│  - Claude Code CLI         │
└──────────────┬─────────────┘
               ↓
┌────────────────────────────┐
│ Safe POSIX Executor        │
│  - sh / bash / dash        │
│  - Audited commands        │
└────────────────────────────┘
```

---

## Supported Assays & Tools

**Assay types:** WGS, WES, RNA-seq, cfDNA, ChIP-seq, ATAC-seq, scRNA-seq, metagenomics, amplicon, methylation, Hi-C, long-read (Nanopore), ancient DNA

**Reference genomes:** GRCh37, GRCh38, hg19, GRCm38, GRCm39, T2T-CHM13

**Container runtimes:** Docker (first-class), Podman (compatible), Singularity / Apptainer (HPC mode)

**nf-core pipelines (curated):**

| Pipeline | Description |
|----------|-------------|
| `nf-core/rnaseq` | RNA-seq quantification (STAR/Salmon/HISAT2) |
| `nf-core/sarek` | Germline and somatic variant calling (WGS/WES) |
| `nf-core/chipseq` | ChIP-seq peak calling |
| `nf-core/atacseq` | ATAC-seq peak calling |
| `nf-core/methylseq` | Bisulfite / DNA methylation |
| `nf-core/scrnaseq` | Single-cell RNA-seq |
| `nf-core/ampliseq` | Amplicon / 16S rRNA |
| `nf-core/mag` | Metagenome assembly |
| `nf-core/viralrecon` | Viral genome reconstruction |
| `nf-core/nanoseq` | Oxford Nanopore long-read |
| `nf-core/fetchngs` | Fetch public data (SRA/ENA) |
| `nf-core/taxprofiler` | Metagenomic taxonomic profiling |

---

## Strict Mode (Clinical Use)

```bash
helixsh --strict run nf-core sarek \
  --runtime singularity \
  --input samples.csv \
  --execute --yes
```

In strict mode:
- No execution without explicit `--execute`
- Execution also requires `--yes` confirmation
- Full audit trail is enforced
- All changes require confirmation

Suitable for clinical genomics, regulated HPC, and enterprise environments.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
```

Tests are in `tests/` and mirror the `src/helixsh/` module structure.

---

## What helixsh Is Not

| Thing | Reason |
|-------|--------|
| Workflow engine | Nextflow already exists |
| Scheduler | Slurm / PBS remain in place |
| Notebook | Reproducibility first |
| Cloud-only | HPC and on-prem are required |
| AI executor | AI proposes; helixsh decides |

---

## One-Line Summary

**helixsh** is an AI-native shell that thinks like a bioinformatician, respects POSIX, trusts Nextflow, and treats AI as a planner — not an executor.
