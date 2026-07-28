# Helixsh — Desktop orchestration for Nextflow and nf-core

**Helixsh** is a sandboxed desktop app and POSIX-respecting CLI for planning,
validating, and running nf-core pipelines with Docker, Kubernetes, Podman, or
Apptainer. Nextflow remains the workflow authority; Helixsh provides the
reviewed execution boundary around it.

[Website](https://musicofthings.github.io/helixsh/) ·
[Desktop quick start](#desktop-app) ·
[Implementation status](#current-implementation-status-v02-development-preview)

> **Development preview:** The desktop workflow, macOS application packaging,
> execution-time preflight, Docker readiness, and Kubernetes `nf-k8s`
> configuration are implemented. The app is not yet signed, notarized, or
> clinically validated.

## What works today

| Capability | Status |
| --- | --- |
| Sandboxed Electron desktop UI | Implemented |
| Reviewed plan and native run confirmation | Implemented |
| Docker / Podman / Apptainer / Singularity targets | Implemented |
| Kubernetes target with pinned `nf-k8s` configuration | Implemented |
| Live logs and full process-group cancellation | Implemented |
| Execution-time schema, workflow, context, cache, and image checks | Implemented |
| Signed universal macOS distribution with bundled runtimes | Planned |

## Core Principles

1. **POSIX execution boundary** — final execution is always real `sh`/`bash` commands.
2. **Nextflow is the workflow authority** — helixsh plans, validates, explains, and diagnoses; it does not replace Nextflow.
3. **Container-first execution** — workflow processes run through a supported
   container or cluster runtime rather than untracked host binaries.
4. **LLM as planner, not executor** — AI proposes plans and fixes; helixsh decides and executes.
5. **Offline-capable by design** — local reasoning, cached schemas, and optional internet access.

## High-Level Architecture

```text
┌────────────────────────────┐
│    Helixsh desktop + CLI   │
│  (sandboxed UI / POSIX)    │
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
│  - Docker / Kubernetes     │
│  - Podman / Singularity    │
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
| Kubernetes (`nf-k8s`)   | First-class |
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

These controls are foundations for regulated and enterprise deployments. The
current development preview is not clinically validated.

## Implementation roadmap

### Phase 1 — Foundation and desktop

- POSIX shell wrapper
- Nextflow command interception
- nf-core schema ingestion
- Container enforcement
- Sandboxed desktop planner and runner
- Docker and Kubernetes readiness checks

### Phase 2 — AI planning

- MCP Gateway
- Claude Code CLI integration
- Intent → parameter mapping

### Phase 3 — Bioinformatics intelligence

- RNA-seq / WGS / WES profiles
- Tool memory and CPU models
- Reference genome awareness

### Phase 4 — Enterprise and release hardening

- Offline mode
- RBAC
- Audit exports
- Validation reports
- Code signing, notarization, and universal macOS packaging
- Bundled Python and Nextflow runtimes

## What helixsh Is Not

| Thing           | Reason                  |
| --------------- | ----------------------- |
| Workflow engine | Nextflow already exists |
| Scheduler       | Slurm / PBS remain      |
| Notebook        | Reproducibility first   |
| Cloud-only      | HPC and on-prem required |

## One-line summary

**Helixsh** is a dedicated control room for reproducible nf-core execution.

## Current implementation status (v0.2 development preview)

This repository includes the desktop app and its Python execution backend:

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
- `helixsh k8s-config --storage-claim nextflow-pvc --out nextflow.k8s.config`
- `helixsh run nf-core rnaseq --runtime kubernetes --config nextflow.k8s.config`
- `helixsh run nf-core rnaseq --workflow main.nf --schema schema.json --params params.json --execute`
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
- Sandboxed Electron desktop planner/runner for nf-core pipelines
- Docker-daemon and Kubernetes-cluster capability checks
- Validated `nf-k8s` configuration generation with a shared persistent volume
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
- Execution-time preflight checks can block `run --execute` when requested validation fails
- `run --execute` crosses the explicit POSIX `exec sh -c` boundary
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

`roadmap-status` distinguishes implemented scaffolds from the remaining
end-to-end PRD work; phases remain `in_progress` until those production
requirements are complete.

## Desktop app

The desktop app provides a dedicated Helixsh window instead of running the
workflow interface in a terminal. It supports:

- nf-core pipeline and revision selection
- Docker or Kubernetes execution targets
- file pickers for samplesheets, parameter schemas, and output directories
- a reviewed execution plan before the run is enabled
- live logs and cancellation
- local Nextflow, Docker-daemon, and Kubernetes-cluster readiness status
- generated Kubernetes configuration using `nf-k8s` and a user-supplied
  persistent-volume claim

The renderer runs with Electron sandboxing and context isolation, without Node
integration. It can only call a narrow, validated IPC API; arbitrary shell
commands, navigation, popups, and renderer permission requests are blocked.
Nextflow still owns workflow execution, and Docker or Kubernetes provides the
process isolation.

For local development, install Node.js 22.12 or newer:

```bash
npm install
npm run desktop:test
npm run desktop:dev
```

Build the current machine's macOS application bundle:

```bash
npm run desktop:pack:mac
```

The app is written to `dist-desktop/Helixsh-darwin-*/Helixsh.app`.

The development build currently uses the system `python3`, Nextflow, and the
selected container runtime. The `.app` bundles the Helixsh Python source but is
not yet code-signed, notarized, or configured with an Apple App Sandbox
entitlement. A bundled Python/Nextflow runtime and signed universal macOS
distribution remain release-hardening tasks.

### Docker

Start Docker Desktop or another compatible Docker daemon, select **Docker**,
choose an nf-core pipeline, review the plan, and run. Helixsh invokes Nextflow
with `-profile docker`; nf-core's process definitions select their declared
container images.

### Kubernetes

Helixsh requires a reachable cluster, `kubectl`, a service account, and a
ReadWriteMany-compatible persistent-volume claim mounted at the selected work
path. The app generates a dedicated Nextflow config that pins `nf-k8s` 1.5.5,
selects the Kubernetes executor, and sets the namespace, service account,
storage claim, mount path, and work directory. The generated config is
validated again before execution.

Only run trusted pipelines, pin a revision for reproducible work, and review
the displayed Nextflow command before confirming execution.

### Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
```

### Package for local deployment

Build a self-contained local executable archive (`.pyz`) and run it directly:

```bash
./scripts/package_local.sh
./dist/helixsh.pyz doctor
```

This packaging flow is self-contained and does not require publishing to PyPI.
