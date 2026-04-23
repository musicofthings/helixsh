"""Tests for all new feature modules and their CLI commands."""

import json
from pathlib import Path

import pytest

from helixsh import cli


# ─────────────────────────── nf_launch ───────────────────────────────────────

def test_nf_launch_dry_run(capsys):
    rc = cli.main([
        "nf-launch",
        "--pipeline", "nf-core/rnaseq",
        "--revision", "3.14.0",
        "--profile", "docker",
        "--param", "genome=GRCh38",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert "nf-core/rnaseq" in data["command"]
    assert "3.14.0" in data["command"]


def test_nf_launch_params_parsed(capsys):
    rc = cli.main([
        "nf-launch",
        "--pipeline", "nf-core/sarek",
        "--param", "genome=GRCh38",
        "--param", "tools=mutect2",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "GRCh38" in data["command"]
    assert "mutect2" in data["command"]


def test_nf_auth_returns_status(capsys):
    rc = cli.main(["nf-auth"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "token_set" in data
    assert "endpoint" in data


def test_nf_launch_command_structure():
    from helixsh.nf_launch import LaunchConfig, build_launch_command
    cfg = LaunchConfig(pipeline="nf-core/rnaseq", revision="3.14.0",
                       profile="singularity", outdir="results",
                       params={"genome": "GRCh38"})
    cmd = build_launch_command(cfg)
    assert "nextflow" in cmd
    assert "launch" in cmd
    assert "nf-core/rnaseq" in cmd
    assert "-r" in cmd
    assert "3.14.0" in cmd
    assert "--outdir" in cmd


# ─────────────────────────── samplesheet ─────────────────────────────────────

def test_samplesheet_validate_rnaseq_ok(tmp_path, capsys):
    ss = tmp_path / "ss.csv"
    ss.write_text(
        "sample,fastq_1,fastq_2,strandedness\n"
        "S1,s1_R1.fastq.gz,s1_R2.fastq.gz,auto\n",
        encoding="utf-8",
    )
    rc = cli.main(["samplesheet-validate", "--file", str(ss), "--pipeline", "rnaseq"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["row_count"] == 1


def test_samplesheet_validate_missing_column(tmp_path, capsys):
    ss = tmp_path / "ss.csv"
    ss.write_text("sample,fastq_1\nS1,s1.fastq.gz\n", encoding="utf-8")
    rc = cli.main(["samplesheet-validate", "--file", str(ss), "--pipeline", "rnaseq"])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    fields = [i["field"] for i in data["issues"]]
    assert "strandedness" in fields


def test_samplesheet_validate_bad_strandedness(tmp_path, capsys):
    ss = tmp_path / "ss.csv"
    ss.write_text(
        "sample,fastq_1,fastq_2,strandedness\n"
        "S1,r1.fastq.gz,r2.fastq.gz,yes\n",
        encoding="utf-8",
    )
    rc = cli.main(["samplesheet-validate", "--file", str(ss), "--pipeline", "rnaseq"])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert any(i["field"] == "strandedness" for i in data["issues"])


def test_samplesheet_validate_sarek_status(tmp_path, capsys):
    ss = tmp_path / "ss.csv"
    ss.write_text(
        "patient,sample,lane,fastq_1,fastq_2,status\n"
        "P1,S1,L001,r1.fastq.gz,r2.fastq.gz,2\n",
        encoding="utf-8",
    )
    rc = cli.main(["samplesheet-validate", "--file", str(ss), "--pipeline", "sarek"])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert any(i["field"] == "status" for i in data["issues"])


def test_samplesheet_generate_from_dir(tmp_path, capsys):
    (tmp_path / "S1_R1.fastq.gz").write_bytes(b"")
    (tmp_path / "S1_R2.fastq.gz").write_bytes(b"")
    (tmp_path / "S2_R1.fastq.gz").write_bytes(b"")
    (tmp_path / "S2_R2.fastq.gz").write_bytes(b"")
    rc = cli.main(["samplesheet-generate", "--fastq-dir", str(tmp_path), "--pipeline", "rnaseq"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["rows"] == 2


def test_samplesheet_generate_writes_file(tmp_path, capsys):
    (tmp_path / "S1_R1.fastq.gz").write_bytes(b"")
    out = tmp_path / "out.csv"
    rc = cli.main([
        "samplesheet-generate", "--fastq-dir", str(tmp_path),
        "--pipeline", "rnaseq", "--out", str(out),
    ])
    assert rc == 0
    assert out.exists()
    capsys.readouterr()


def test_samplesheet_generate_sarek_format(tmp_path, capsys):
    (tmp_path / "T1_R1.fastq.gz").write_bytes(b"")
    rc = cli.main(["samplesheet-generate", "--fastq-dir", str(tmp_path), "--pipeline", "sarek"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    # sarek rows have patient column
    assert "patient" in data["csv"]


def test_samplesheet_validate_not_found(tmp_path, capsys):
    rc = cli.main(["samplesheet-validate", "--file", str(tmp_path / "missing.csv")])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False


# ─────────────────────────── ref_genome ──────────────────────────────────────

def test_ref_list(capsys):
    rc = cli.main(["ref-list"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    genomes = [g["genome"] for g in data]
    assert "GRCh38" in genomes
    assert "GRCm39" in genomes


def test_ref_download_dry_run(tmp_path, capsys):
    rc = cli.main([
        "ref-download", "--genome", "GRCh38",
        "--cache-root", str(tmp_path / "cache"),
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["genome"] == "GRCh38"
    assert len(data["to_download"]) == 2   # fasta + gtf


def test_ref_download_dry_run_unknown_genome(tmp_path, capsys):
    rc = cli.main([
        "ref-download", "--genome", "UNKNOWNXYZ",
        "--cache-root", str(tmp_path / "cache"),
    ])
    assert rc == 0   # dry-run reports plan, plan is empty — no error from plan_download
    capsys.readouterr()


def test_ref_genome_plan_already_cached(tmp_path):
    from helixsh.ref_genome import plan_download, GENOME_CATALOGUE
    genome = "GRCh38"
    cache_root = str(tmp_path)
    root = tmp_path / genome
    root.mkdir()
    # Fake cached files
    info = GENOME_CATALOGUE[genome]
    for url_key in ("fasta_url", "gtf_url"):
        fname = info[url_key].split("/")[-1]
        (root / fname).write_bytes(b"fake")
    plan = plan_download(genome, cache_root)
    assert len(plan.already_cached) == 2
    assert len(plan.files) == 0


# ─────────────────────────── trace ────────────────────────────────────────────

TRACE_CONTENT = """\
task_id\thash\tnative_id\tname\tstatus\texit\tsubmit\tduration\trealtime\t%cpu\tpeak_rss\tpeak_vmem\trchar\twchar
1\tab/123\t101\tSTAR_ALIGN (S1)\tCOMPLETED\t0\t2026-01-01\t2m 30s\t2m 15s\t780\t12 GB\t14 GB\t10 GB\t2 GB
2\tcd/456\t102\tSTAR_ALIGN (S2)\tCOMPLETED\t0\t2026-01-01\t3m\t2m 45s\t820\t14 GB\t16 GB\t11 GB\t2.5 GB
3\tef/789\t103\tSALMON_QUANT (S1)\tCOMPLETED\t0\t2026-01-01\t30s\t28s\t180\t2 GB\t3 GB\t1 GB\t500 MB
4\tgh/000\t104\tMULTIQC\tFAILED\t1\t2026-01-01\t10s\t9s\t100\t500 MB\t600 MB\t200 MB\t50 MB
"""


def test_trace_summary_parses_tasks(tmp_path, capsys):
    trace = tmp_path / "trace.txt"
    trace.write_text(TRACE_CONTENT, encoding="utf-8")
    rc = cli.main(["trace-summary", "--file", str(trace)])
    assert rc == 2   # 1 failed task → non-zero exit
    data = json.loads(capsys.readouterr().out)
    assert data["total_tasks"] == 4
    assert data["failed_tasks"] == 1
    process_names = [p["process"] for p in data["processes"]]
    assert "STAR_ALIGN" in process_names


def test_trace_summary_aggregates_processes(tmp_path, capsys):
    trace = tmp_path / "trace.txt"
    trace.write_text(TRACE_CONTENT, encoding="utf-8")
    cli.main(["trace-summary", "--file", str(trace)])
    data = json.loads(capsys.readouterr().out)
    star = next(p for p in data["processes"] if p["process"] == "STAR_ALIGN")
    assert star["task_count"] == 2
    assert star["max_peak_rss_mb"] > 0


def test_trace_summary_missing_file(tmp_path, capsys):
    rc = cli.main(["trace-summary", "--file", str(tmp_path / "missing.txt")])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert data["total_tasks"] == 0
    assert data["warnings"]


def test_trace_duration_parsing():
    from helixsh.trace import _parse_duration
    assert _parse_duration("2m 30s") == 150_000
    assert _parse_duration("1h 30m") == 5_400_000
    assert _parse_duration("500 ms") == 500
    assert _parse_duration("-") == 0


def test_trace_memory_parsing():
    from helixsh.trace import _parse_memory
    assert _parse_memory("1 GB") == 1024.0
    assert _parse_memory("512 MB") == 512.0
    assert _parse_memory("2 KB") == pytest.approx(2 / 1024, rel=1e-3)
    assert _parse_memory("-") == 0.0


# ─────────────────────────── cloud_cost ──────────────────────────────────────

def test_cost_estimate_aws(capsys):
    rc = cli.main([
        "cost-estimate", "--cpu", "16", "--memory-gb", "64",
        "--hours", "4", "--provider", "aws",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["cost_usd"] > 0
    assert data["provider"] == "aws"
    assert "cpu_cost_usd" in data["breakdown"]


def test_cost_estimate_compare_all(capsys):
    rc = cli.main([
        "cost-estimate", "--cpu", "8", "--memory-gb", "32",
        "--hours", "2", "--compare-all",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 3
    providers = {e["provider"] for e in data}
    assert {"aws", "gcp", "azure"} == providers
    # sorted by cost ascending
    costs = [e["cost_usd"] for e in data]
    assert costs == sorted(costs)


def test_cost_estimate_spot_cheaper(capsys):
    rc_spot = cli.main(["cost-estimate", "--cpu", "16", "--memory-gb", "64", "--hours", "4",
                         "--provider", "aws", "--instance-family", "spot"])
    rc_od   = cli.main(["cost-estimate", "--cpu", "16", "--memory-gb", "64", "--hours", "4",
                         "--provider", "aws", "--instance-family", "general"])
    capsys.readouterr()
    from helixsh.cloud_cost import estimate_cost
    spot = estimate_cost(total_cpu=16, total_memory_gb=64, wall_hours=4,
                         provider="aws", instance_family="spot")
    od   = estimate_cost(total_cpu=16, total_memory_gb=64, wall_hours=4,
                         provider="aws", instance_family="general")
    assert spot.cost_usd < od.cost_usd


def test_cost_estimate_invalid_provider():
    from helixsh.cloud_cost import estimate_cost
    with pytest.raises(ValueError, match="Unknown provider"):
        estimate_cost(total_cpu=4, total_memory_gb=16, wall_hours=1, provider="oracle")


def test_cost_estimate_notes_for_large_job():
    from helixsh.cloud_cost import estimate_cost
    result = estimate_cost(total_cpu=128, total_memory_gb=256, wall_hours=1,
                           provider="aws", instance_family="general")
    assert any("spot" in n.lower() for n in result.notes)


# ─────────────────────────── pipeline_registry ───────────────────────────────

def test_pipeline_list(capsys):
    rc = cli.main(["pipeline-list"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    names = [p["name"] for p in data]
    assert "rnaseq" in names
    assert "sarek" in names


def test_pipeline_update_up_to_date(capsys):
    rc = cli.main(["pipeline-update", "--pipeline", "rnaseq", "--pinned", "3.14.0"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["up_to_date"] is True


def test_pipeline_update_outdated(capsys):
    rc = cli.main(["pipeline-update", "--pipeline", "sarek", "--pinned", "3.0.0"])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert data["up_to_date"] is False
    assert "Update available" in data["message"]


def test_pipeline_update_unknown(capsys):
    rc = cli.main(["pipeline-update", "--pipeline", "unknownpipeline", "--pinned", "1.0.0"])
    assert rc == 0   # unknown → up_to_date=None → no assertion of outdated
    data = json.loads(capsys.readouterr().out)
    assert data["latest"] == "unknown"
    assert data["up_to_date"] is None


def test_pipeline_update_with_cache(tmp_path, capsys):
    cache = tmp_path / "registry.json"
    cache.write_text(json.dumps([{"name": "rnaseq", "latest": "99.0.0", "description": "test"}]),
                     encoding="utf-8")
    rc = cli.main(["pipeline-update", "--pipeline", "rnaseq", "--pinned", "3.14.0",
                    "--cache", str(cache)])
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert data["latest"] == "99.0.0"


# ─────────────────────────── envmodules ──────────────────────────────────────

def test_envmodules_list(capsys):
    rc = cli.main(["envmodules-list"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    tools = {e["tool"] for e in data}
    assert "star" in tools
    assert "samtools" in tools


def test_envmodules_wrap_generates_config(capsys):
    rc = cli.main(["envmodules-wrap", "--tool", "star", "--tool", "samtools"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["entries"] == 2
    assert "withName" in data["config"]
    assert "STAR" in data["config"]
    assert "SAMtools" in data["config"]


def test_envmodules_wrap_writes_file(tmp_path, capsys):
    out = tmp_path / "modules.config"
    rc = cli.main(["envmodules-wrap", "--tool", "bwa", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    content = out.read_text()
    assert "BWA" in content
    capsys.readouterr()


def test_envmodules_wrap_unknown_tool_warns(capsys):
    rc = cli.main(["envmodules-wrap", "--tool", "reallyunknowntool123"])
    assert rc == 0   # warnings are non-fatal
    data = json.loads(capsys.readouterr().out)
    assert data["warnings"]


def test_envmodules_config_format():
    from helixsh.envmodules import generate_modules_config
    config = generate_modules_config(["star", "samtools"])
    rendered = config.to_nextflow_config()
    assert "process {" in rendered
    assert "withName:" in rendered
    assert "module = '" in rendered


# ─────────────────────────── tower ───────────────────────────────────────────

def test_tower_auth_no_token(capsys):
    import os
    old = os.environ.pop("TOWER_ACCESS_TOKEN", None)
    try:
        rc = cli.main(["tower-auth"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["ok"] is False or "token_set" in data
    finally:
        if old:
            os.environ["TOWER_ACCESS_TOKEN"] = old


def test_tower_submit_dry_run(capsys):
    rc = cli.main([
        "tower-submit",
        "--pipeline", "nf-core/rnaseq",
        "--revision", "3.14.0",
        "--profile", "docker",
        "--param", "genome=GRCh38",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["workflow_id"] == "(dry-run)"


def test_tower_submit_config_structure():
    from helixsh.tower import TowerRunConfig, submit_run
    cfg = TowerRunConfig(pipeline="nf-core/sarek", revision="3.4.4",
                         params={"genome": "GRCh38", "tools": "mutect2"})
    result = submit_run(cfg, dry_run=True)
    assert result.ok is True
    assert result.dry_run is True


# ─────────────────────────── snakemake_bridge ────────────────────────────────

SNAKEFILE_CONTENT = """\
rule all:
    input: "results/final.txt"

rule align:
    input: "data/{sample}.fastq.gz"
    output: "aligned/{sample}.bam"
    threads: 8
    resources:
        mem_mb=16000,
        runtime=120,
        disk_mb=50000
    shell:
        "bwa mem -t {threads} ref.fa {input} > {output}"

rule call_variants:
    input: "aligned/{sample}.bam"
    output: "vcf/{sample}.vcf"
    threads: 4
    resources:
        mem_mb=8000,
        runtime=60
    shell:
        "gatk HaplotypeCaller -I {input} -O {output}"

rule multiqc:
    input: expand("qc/{sample}.html", sample=samples)
    output: "multiqc_report.html"
    shell:
        "multiqc qc/"
"""


def test_snakemake_import_parses_rules(tmp_path, capsys):
    sf = tmp_path / "Snakefile"
    sf.write_text(SNAKEFILE_CONTENT, encoding="utf-8")
    rc = cli.main(["snakemake-import", "--file", str(sf)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_rules"] == 4
    assert data["rules_with_resources"] == 2   # align and call_variants


def test_snakemake_import_extracts_resources(tmp_path):
    from helixsh.snakemake_bridge import parse_snakefile
    sf = tmp_path / "Snakefile"
    sf.write_text(SNAKEFILE_CONTENT, encoding="utf-8")
    result = parse_snakefile(str(sf))
    align = next(r for r in result.rules if r.name == "align")
    assert align.threads == 8
    assert align.mem_mb == 16000
    assert align.runtime_min == 120


def test_snakemake_import_to_calibration(tmp_path):
    from helixsh.snakemake_bridge import parse_snakefile, to_helixsh_calibration
    sf = tmp_path / "Snakefile"
    sf.write_text(SNAKEFILE_CONTENT, encoding="utf-8")
    result = parse_snakefile(str(sf))
    cal = to_helixsh_calibration(result.rules)
    assert any(c["rule"] == "align" for c in cal)
    align_cal = next(c for c in cal if c["rule"] == "align")
    assert align_cal["expected_cpu"] == 8
    assert align_cal["expected_memory_gb"] == pytest.approx(16000 / 1024, rel=1e-3)


def test_snakemake_import_exports_calibration_json(tmp_path, capsys):
    sf = tmp_path / "Snakefile"
    sf.write_text(SNAKEFILE_CONTENT, encoding="utf-8")
    cal_out = tmp_path / "calibration.json"
    rc = cli.main([
        "snakemake-import", "--file", str(sf),
        "--export-calibration", str(cal_out),
    ])
    assert rc == 0
    assert cal_out.exists()
    data = json.loads(cal_out.read_text())
    assert isinstance(data, list)
    assert len(data) > 0
    capsys.readouterr()


def test_snakemake_import_missing_file(tmp_path, capsys):
    rc = cli.main(["snakemake-import", "--file", str(tmp_path / "missing")])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["warnings"]


# ─────────────────────────── RBAC new commands ───────────────────────────────

def test_rbac_auditor_cannot_nf_launch():
    from helixsh.rbac import check_access
    assert check_access("auditor", "nf-launch").allowed is False


def test_rbac_auditor_can_ref_list():
    from helixsh.rbac import check_access
    assert check_access("auditor", "ref-list").allowed is True


def test_rbac_auditor_can_cost_estimate():
    from helixsh.rbac import check_access
    assert check_access("auditor", "cost-estimate").allowed is True


def test_rbac_analyst_can_samplesheet_validate():
    from helixsh.rbac import check_access
    assert check_access("analyst", "samplesheet-validate").allowed is True


def test_rbac_analyst_can_tower_submit():
    from helixsh.rbac import check_access
    assert check_access("analyst", "tower-submit").allowed is True


def test_rbac_auditor_cannot_snakemake_import():
    from helixsh.rbac import check_access
    assert check_access("auditor", "snakemake-import").allowed is False
