# helixsh — Bioinformatics-First AI Shell for Nextflow / nf-core

**helixsh** is an AI-native, POSIX-respecting shell that understands bioinformatics intent, Nextflow / nf-core semantics, and containerized execution, while delegating real execution to deterministic tools.

## Core Principles

1. **POSIX execution boundary** — final execution is always real `sh`/`bash` commands.
2. **Nextflow is the workflow authority** — helixsh plans, validates, explains, and diagnoses; it does not replace Nextflow.
3. **Container-first execution** — Docker / Podman / Singularity are mandatory.
4. **LLM as planner, not executor** — AI proposes plans and fixes; helixsh decides and executes.
5. **Offline-capable by design** — local reasoning, cached schemas, and optional internet access.

## High-Level Architecture

```text
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

## CLI Specification

### Invocation modes

```bash
helixsh
helixsh run nf-core rnaseq
helixsh explain last
helixsh doctor
helixsh plan
```

### Intent-first commands

```text
run nf-core rnaseq on tumor-normal samples
use docker
optimize for low-memory node
resume if possible
```

### Strict mode (clinical use)

```bash
helixsh --strict
```

- No interactive guesses
- All changes require confirmation
- Full audit trail

## Domain Intelligence

### Bioinformatics vocabulary

helixsh natively understands:

- Assay types: WGS, WES, RNA-seq, cfDNA, ChIP-seq
- Sample models: tumor/normal, trio, cohort
- Reference genomes: GRCh37, GRCh38, hg19
- Common tool constraints (e.g., STAR, BWA, GATK, Salmon)

### Context sources

| Source              | Usage                |
| ------------------- | -------------------- |
| `samplesheet.csv`   | Sample topology      |
| nf-core schema JSON | Parameter validation |
| `nextflow.config`   | Resource defaults    |
| Container metadata  | Tool provenance      |

## Nextflow-Native Workflow Intelligence

### AST parsing

helixsh parses:

- `process` blocks
- `input` / `output`
- `cpus`, `memory`, `time`
- `container`
- `when` conditions

This enables:

- Resource mismatch detection
- Bottleneck prediction
- Semantic error explanations

### Process graph (DAG)

Each process becomes a typed node:

```text
ALIGN_READS
  inputs: FASTQ
  outputs: BAM
  resources: 8 CPU / 32 GB
  container: biocontainers/star
```

## nf-core Schema Intelligence

### Pre-flight validation

Before execution:

- Required parameters present
- Parameter types validated
- Mutually exclusive flags detected

### Semantic explanation example

```text
--aligner star
→ STAR: splice-aware RNA-seq aligner
→ High memory usage, fast runtime
```

## Container Orchestration

### Enforcement rules

- Every process must specify a container
- Image digests are preferred
- Host binaries are blocked

Example:

```text
Process ALIGN_READS uses host samtools → BLOCKED
Suggested fix: biocontainers/samtools
```

### Runtime support

| Runtime                 | Support     |
| ----------------------- | ----------- |
| Docker                  | First-class |
| Podman                  | Compatible  |
| Singularity / Apptainer | HPC mode    |

## MCP Gateway + Claude Code Integration

### Role separation

- **helixsh**: owns state and execution
- **Claude Code**: proposes plans and fixes
- **MCP Gateway**: controlled access boundary

### Permissions model

| Capability       | Allowed       |
| ---------------- | ------------- |
| Read logs        | Yes           |
| Inspect DAG      | Yes           |
| Modify files     | Proposal only |
| Execute commands | No            |

### Interaction flow

```text
helixsh → MCP Gateway → Claude Code
Claude Code → proposed diff → helixsh
helixsh → validate → execute
```

## Error Diagnosis Example

```text
Process QUANTIFY failed
Exit code: 137
```

helixsh analysis:

```text
Likely cause: Out-of-memory
Context: Salmon requires ~8–16 GB/sample
Node limit: 4 GB

Options:
1. Increase memory
2. Reduce parallelism
3. Switch to kallisto
```

## Resume & Cache Intelligence

```text
83% cached
ALIGN_READS invalidated (reference index changed)
Recommendation: pin genome FASTA
```

## POSIX Compatibility Guarantee

Final execution always reduces to real shell commands:

```sh
exec sh -c "nextflow run nf-core/rnaseq -profile docker --input samplesheet.csv -resume"
```

No proprietary runtime and no hidden execution behavior.

## Security, Compliance, and Audit

- Full command log
- Container digests recorded
- Parameter provenance stored
- Reproducible execution hash

Suitable for clinical genomics, regulated HPC, and enterprise environments.

## Implementation Roadmap

### Phase 1 — Foundation (4–6 weeks)

- POSIX shell wrapper
- Nextflow command interception
- nf-core schema ingestion
- Container enforcement

### Phase 2 — AI Planning (6–8 weeks)

- MCP Gateway
- Claude Code CLI integration
- Intent → parameter mapping

### Phase 3 — Bioinformatics Intelligence

- RNA-seq / WGS / WES profiles
- Tool memory and CPU models
- Reference genome awareness

### Phase 4 — Enterprise Hardening

- Offline mode
- RBAC
- Audit exports
- Validation reports

## What helixsh Is Not

| Thing           | Reason                  |
| --------------- | ----------------------- |
| Workflow engine | Nextflow already exists |
| Scheduler       | Slurm / PBS remain      |
| Notebook        | Reproducibility first   |
| Cloud-only      | HPC and on-prem required |

## One-Line Summary

**helixsh** is an AI-native shell that thinks like a bioinformatician, respects POSIX, trusts Nextflow, and treats AI as a planner—not an executor.

## Current Implementation Status (Phase 1 bootstrap)

This repository now includes an initial Python CLI implementation:

- `helixsh run nf-core rnaseq --runtime docker --input samplesheet.csv --resume`
- `helixsh doctor`
- `helixsh explain last`
- `helixsh plan`
- `helixsh intent "run nf-core rnaseq on tumor-normal samples use docker resume"`
- `helixsh validate-schema --schema schema.json --params params.json`
- `helixsh mcp-check execute_commands`
- `helixsh audit-export --out audit_export.json`
- `helixsh parse-workflow --file main.nf`
- `helixsh diagnose --process QUANTIFY --exit-code 137 --memory-gb 4`
- `helixsh cache-report --total 100 --cached 83 --invalidated ALIGN_READS`
- `helixsh rbac-check --role auditor --action run`
- `helixsh report --schema-ok --container-policy-ok --cache-percent 95 --diagnostics ok --out validation_report.json`
- `helixsh profile-suggest --assay wgs --reference GRCh38 --offline`
- `helixsh provenance --command "nextflow run nf-core/rnaseq" --params "{\"genome\":\"GRCh38\"}"`
- `helixsh image-check --image ghcr.io/nf-core/rnaseq@sha256:...`
- `helixsh --role auditor doctor`
- `helixsh context-check --samplesheet samplesheet.csv --config nextflow.config`
- `helixsh run nf-core rnaseq --offline`
- `helixsh offline-check --cache-root .helixsh_cache`
- `helixsh preflight --schema schema.json --params params.json --workflow main.nf --cache-root .helixsh_cache --image ghcr.io/tool@sha256:...`
- `helixsh audit-verify`
- `helixsh audit-sign --key-file audit.key --out audit.sig`
- `helixsh audit-verify-signature --key-file audit.key --signature-file audit.sig`
- `helixsh mcp-propose --kind file_patch --summary "update config" --payload "..."`
- `helixsh mcp-proposals`
- `helixsh mcp-approve --id 1`
- `helixsh resource-estimate --tool star --assay rnaseq --samples 4`
- `helixsh posix-wrap nextflow run nf-core/rnaseq`
- `helixsh roadmap-status`
- `helixsh claude-plan --prompt "fix schema mismatch"`
- `helixsh resource-estimate --tool salmon --assay rnaseq --samples 2 --calibration calibration.json`
- `helixsh fit-calibration --observations observations.json --out calibration.json`
- `helixsh mcp-execute --id 1`

Behavior highlights:

- Deterministic Nextflow command generation
- Runtime validation (Docker/Podman/Singularity/Apptainer)
- Audit trail written to `.helixsh_audit.jsonl`
- Dry-run by default; explicit `--execute` required for command execution
- `--strict` blocks execution unless `--execute` is passed
- In strict mode, execution also requires explicit `--yes` confirmation
- Intent parsing scaffold for RNA-seq/WGS/WES/ChIP-seq planning
- nf-core-style schema validation scaffold (required/type/mutually exclusive checks)
- MCP gateway capability policy check scaffold
- Audit export with reproducible SHA-256 digest
- Nextflow process parsing scaffold + container policy violation detection
- Failure diagnosis helper for common exit codes (e.g., OOM/137)
- Resume/cache summary reporting scaffold
- RBAC policy scaffold for role/action authorization
- Validation report artifact generation scaffold
- Assay/reference profile suggestion scaffold with offline mode hints
- Reproducible execution hash/provenance record scaffold
- Container image digest policy checker scaffold
- RBAC enforcement integrated into command execution via global `--role`
- Context ingestion scaffold for `samplesheet.csv` and `nextflow.config` defaults
- Offline-mode readiness checks for cached schemas/containers/assets
- Combined `preflight` command to run schema/workflow/offline/context/image checks in one report
- Audit entries now include role + reproducible execution hash + provenance params, with `audit-verify` hash integrity checks
- HMAC-based audit signature and verification workflow (`audit-sign` / `audit-verify-signature`)
- MCP proposal workflow scaffold (`mcp-propose`/`mcp-proposals`/`mcp-approve`)
- Tool-aware resource estimate scaffold for CPU/memory planning
- Calibration-aware resource estimation from empirical multipliers
- Claude-plan proposal shim that stores plan output in MCP proposal workflow
- MCP approved-proposal runtime execution shim (`mcp-execute`)
- Empirical calibration fitting command (`fit-calibration`)
- Explicit POSIX wrapper renderer/executor (`exec sh -c ...`)
- Machine-readable roadmap status report (`roadmap-status`)

### Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
```
