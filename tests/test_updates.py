"""Tests for all updated and new functionality in helixsh."""

import json

import pytest

from helixsh import cli
from helixsh.context import summarize_samplesheet
from helixsh.diagnostics import diagnose_failure
from helixsh.intent import parse_intent, intent_to_nf_args
from helixsh.nextflow import RunConfig, build_nextflow_run_command, validate_runtime
from helixsh.profiles import recommend_profile
from helixsh.resources import estimate_resources
from helixsh.schema import validate_params
from helixsh.workflow import parse_process_nodes, container_violations


# ── intent.py ─────────────────────────────────────────────────────────────────

def test_intent_apptainer_maps_to_apptainer():
    r = parse_intent("run wgs with apptainer")
    assert r.runtime == "apptainer"


def test_intent_singularity_distinct_from_apptainer():
    r = parse_intent("run rnaseq with singularity")
    assert r.runtime == "singularity"


def test_intent_atacseq():
    r = parse_intent("run atac-seq analysis")
    assert r.pipeline == "nf-core/atacseq"


def test_intent_methylseq():
    r = parse_intent("run methylseq bisulfite pipeline")
    assert r.pipeline == "nf-core/methylseq"


def test_intent_scrnaseq():
    r = parse_intent("run single cell rna analysis")
    assert r.pipeline == "nf-core/scrnaseq"


def test_intent_ampliseq():
    r = parse_intent("run 16s ampliseq metagenomics")
    assert r.pipeline == "nf-core/ampliseq"


def test_intent_conda_adds_with_conda_arg():
    r = parse_intent("run rnaseq using conda")
    assert r.runtime == "conda"
    args = intent_to_nf_args(r)
    assert "-with-conda" in args


# ── profiles.py ───────────────────────────────────────────────────────────────

def test_profile_offline_no_with_trace():
    r = recommend_profile("wgs", offline=True)
    assert "-with-trace" not in r.suggested_args


def test_profile_atacseq():
    r = recommend_profile("atac-seq")
    assert r.pipeline == "nf-core/atacseq"


def test_profile_methylseq():
    r = recommend_profile("methylseq")
    assert r.pipeline == "nf-core/methylseq"


def test_profile_scrnaseq():
    r = recommend_profile("scrnaseq")
    assert r.pipeline == "nf-core/scrnaseq"


def test_profile_ampliseq():
    r = recommend_profile("amplicon")
    assert r.pipeline == "nf-core/ampliseq"


# ── context.py ────────────────────────────────────────────────────────────────

def test_context_sarek_status_column_detects_tumor_normal(tmp_path):
    ss = tmp_path / "samplesheet.csv"
    ss.write_text("sample,fastq_1,fastq_2,status\nS1,r1.fastq.gz,r2.fastq.gz,0\nS2,r1.fastq.gz,r2.fastq.gz,1\n", encoding="utf-8")
    result = summarize_samplesheet(str(ss))
    assert result.has_tumor_normal is True


def test_context_sarek_status_normal_only_not_tumor_normal(tmp_path):
    ss = tmp_path / "samplesheet.csv"
    ss.write_text("sample,fastq_1,fastq_2,status\nS1,a.fastq.gz,b.fastq.gz,0\n", encoding="utf-8")
    result = summarize_samplesheet(str(ss))
    assert result.has_tumor_normal is False


# ── schema.py ─────────────────────────────────────────────────────────────────

def test_schema_number_type_valid():
    schema = {"properties": {"threshold": {"type": "number"}}, "required": []}
    result = validate_params(schema, {"threshold": 0.75})
    assert result.ok is True


def test_schema_number_type_invalid():
    schema = {"properties": {"threshold": {"type": "number"}}, "required": []}
    result = validate_params(schema, {"threshold": "0.75"})
    assert result.ok is False
    assert any(i.field == "threshold" for i in result.issues)


# ── diagnostics.py ────────────────────────────────────────────────────────────

def test_diagnose_sigsegv_139():
    d = diagnose_failure("BWA_MEM", 139)
    assert d.likely_cause == "Segmentation fault (SIGSEGV)"
    assert "139" in d.context


def test_diagnose_sigterm_143():
    d = diagnose_failure("GATK_HAPLOTYPE", 143)
    assert d.likely_cause == "Process killed (SIGTERM/cluster timeout)"
    assert "wall-time" in d.context


def test_diagnose_command_not_found_127():
    d = diagnose_failure("STAR_ALIGN", 127)
    assert d.likely_cause == "Command not found (exit 127)"


def test_diagnose_generic_exit1():
    d = diagnose_failure("MULTIQC", 1)
    assert d.likely_cause == "Generic process failure (exit 1)"


# ── nextflow.py ───────────────────────────────────────────────────────────────

def test_build_command_with_outdir():
    cfg = RunConfig("nf-core/rnaseq", "docker", "samplesheet.csv", outdir="results")
    cmd = build_nextflow_run_command(cfg)
    assert "--outdir" in cmd
    assert "results" in cmd


def test_build_command_conda_uses_with_conda():
    cfg = RunConfig("nf-core/rnaseq", "conda")
    cmd = build_nextflow_run_command(cfg)
    assert "-with-conda" in cmd
    assert "-profile" not in cmd


def test_validate_runtime_conda_accepted():
    assert validate_runtime("conda") == "conda"


def test_validate_runtime_apptainer_accepted():
    assert validate_runtime("apptainer") == "apptainer"


# ── workflow.py ───────────────────────────────────────────────────────────────

NF_WITH_NESTED_BRACES = """
process ALIGN {
    container 'quay.io/biocontainers/bwa:0.7.17'
    cpus 8
    memory '16 GB'
    script:
    def opts = params.save_bam ? "--save-bam" : ""
    \"\"\"
    bwa mem ${opts} \\
        -t ${task.cpus} \\
        ${ref} ${reads} \\
        | samtools view -b { echo "nested" }
    \"\"\"
}

process FASTQC {
    container 'quay.io/biocontainers/fastqc:0.12.1'
    cpus 2
}
"""


def test_workflow_nested_braces_parsed_correctly():
    nodes = parse_process_nodes(NF_WITH_NESTED_BRACES)
    names = [n.name for n in nodes]
    assert "ALIGN" in names
    assert "FASTQC" in names


def test_workflow_nested_braces_extracts_container():
    nodes = parse_process_nodes(NF_WITH_NESTED_BRACES)
    align = next(n for n in nodes if n.name == "ALIGN")
    assert align.container == "quay.io/biocontainers/bwa:0.7.17"


# ── resources.py ─────────────────────────────────────────────────────────────

def test_resources_hisat2_rnaseq():
    r = estimate_resources("hisat2", "rnaseq", 1)
    # hisat2 base: (8, 16) + rnaseq adjustment +8 = 24 GB
    assert r.memory_gb_per_sample == 24


def test_resources_bwa_mem2():
    r = estimate_resources("bwa-mem2", "wgs", 1)
    # bwa-mem2 base: (8, 24) + wgs +8 = 32 GB
    assert r.memory_gb_per_sample == 32


def test_resources_fastp():
    r = estimate_resources("fastp", "rnaseq", 2)
    assert r.total_cpu == 8
    assert r.tool == "fastp"


def test_resources_cellranger():
    r = estimate_resources("cellranger", "scrnaseq", 1)
    assert r.cpu_per_sample == 16
    assert r.memory_gb_per_sample == 64


# ── rbac.py ──────────────────────────────────────────────────────────────────

def test_rbac_auditor_cannot_run():
    from helixsh.rbac import check_access
    assert check_access("auditor", "run").allowed is False


def test_rbac_auditor_cannot_mcp_approve():
    from helixsh.rbac import check_access
    assert check_access("auditor", "mcp-approve").allowed is False


def test_rbac_auditor_cannot_conda_install():
    from helixsh.rbac import check_access
    assert check_access("auditor", "conda-install").allowed is False


def test_rbac_analyst_can_run():
    from helixsh.rbac import check_access
    assert check_access("analyst", "run").allowed is True


def test_rbac_analyst_cannot_conda_install():
    from helixsh.rbac import check_access
    assert check_access("analyst", "conda-install").allowed is False


def test_rbac_admin_can_conda_install():
    from helixsh.rbac import check_access
    assert check_access("admin", "conda-install").allowed is True


# ── CLI new commands ──────────────────────────────────────────────────────────

def test_cli_nf_list(capsys):
    rc = cli.main(["nf-list"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    names = [p["name"] for p in data]
    assert "nf-core/rnaseq" in names
    assert "nf-core/sarek" in names


def test_cli_conda_search_dry(capsys):
    rc = cli.main(["conda-search", "--package", "samtools"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "samtools"


def test_cli_conda_install_dry(capsys):
    # conda-install is admin-only
    rc = cli.main(["--role", "admin", "conda-install", "--package", "samtools", "--package", "bwa"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert "samtools" in data["command"]


def test_cli_conda_env_dry(capsys):
    rc = cli.main(["conda-env", "--name", "myenv", "--tool", "star", "--tool", "samtools"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert "myenv" in data["command"]


def test_cli_execution_lifecycle(tmp_path, capsys):
    db = tmp_path / "prov.sqlite"
    inp = tmp_path / "input.csv"
    inp.write_text("sample,fastq_1\nS1,r1.fastq.gz\n", encoding="utf-8")

    rc = cli.main([
        "execution-start",
        "--command", "nextflow run nf-core/rnaseq",
        "--db", str(db),
        "--input", str(inp),
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    eid = payload["execution_context"]["execution_id"]

    rc = cli.main(["execution-finish", "--execution-id", eid, "--status", "completed", "--db", str(db)])
    assert rc == 0
    capsys.readouterr()

    rc = cli.main(["audit-show", "--execution-id", eid, "--db", str(db)])
    assert rc == 0
    bundle = json.loads(capsys.readouterr().out)
    assert bundle["execution"]["status"] == "completed"
    assert len(bundle["inputs"]) == 1


def test_cli_agent_run(capsys):
    rc = cli.main([
        "agent-run",
        "--agent", "claude",
        "--task", "variant_classification",
        "--model", "claude-sonnet-4-6",
        "--payload", "BRCA1:c.68_69delAG",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["result"]["classification"] == "Pathogenic"
    assert data["confidence"] > 0.5


def test_cli_compliance_check_flags_unpinned(capsys):
    rc = cli.main([
        "compliance-check",
        "--image", "ghcr.io/tool:latest",
        "--agreement-score", "0.9",
        "--confidence", "0.85",
    ])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert "UNPINNED_CONTAINER_DIGEST" in data["flags"]


def test_cli_run_with_outdir(tmp_path, capsys):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    try:
        rc = cli.main(["run", "nf-core", "rnaseq", "--runtime", "docker", "--outdir", "results"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "--outdir results" in out
    finally:
        cli.AUDIT_FILE = old


def test_cli_run_conda_uses_with_conda(tmp_path, capsys):
    old = cli.AUDIT_FILE
    cli.AUDIT_FILE = tmp_path / "audit.jsonl"
    try:
        rc = cli.main(["run", "nf-core", "rnaseq", "--runtime", "conda"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "-with-conda" in out
    finally:
        cli.AUDIT_FILE = old
