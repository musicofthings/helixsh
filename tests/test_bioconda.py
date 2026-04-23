"""Tests for bioconda integration helpers."""

from helixsh.bioconda import (
    BIOCONDA_CHANNELS,
    build_create_env_command,
    build_install_command,
    create_env,
    install_packages,
    list_known_tools,
)


def test_bioconda_channels_include_conda_forge_and_bioconda():
    assert "conda-forge" in BIOCONDA_CHANNELS
    assert "bioconda" in BIOCONDA_CHANNELS


def test_build_install_command_structure():
    cmd = build_install_command(["samtools", "bwa"])
    assert cmd[0] in {"conda", "mamba", "micromamba"}
    assert "install" in cmd
    assert "-c" in cmd
    assert "samtools" in cmd
    assert "bwa" in cmd


def test_build_install_command_with_env():
    cmd = build_install_command(["fastqc"], env_name="qc_env")
    assert "-n" in cmd
    assert "qc_env" in cmd


def test_build_create_env_command():
    cmd = build_create_env_command("bio_env", ["star", "samtools"], python_version="3.11")
    assert "create" in cmd
    assert "-n" in cmd
    assert "bio_env" in cmd
    assert "python=3.11" in cmd
    assert "star" in cmd


def test_install_packages_dry_run():
    result = install_packages(["samtools"], dry_run=True)
    assert result.ok is True
    assert result.returncode == 0
    assert "samtools" in result.command


def test_create_env_dry_run():
    result = create_env("test_env", ["bwa", "gatk4"], dry_run=True)
    assert result.ok is True
    assert "test_env" in result.command
    assert "bwa" in result.command


def test_list_known_tools_returns_entries():
    tools = list_known_tools()
    assert len(tools) > 10
    names = {t["tool"] for t in tools}
    assert "samtools" in names
    assert "bwa" in names
    assert "fastqc" in names
    assert "star" in names
    assert "gatk" in names
