import json
import re

import pytest

from helixsh import cli
from helixsh.cloud_batch import (
    AwsBatchConfig,
    GoogleBatchConfig,
    render_aws_batch_config,
    render_google_batch_config,
    validate_aws_batch_settings,
    validate_google_batch_settings,
)

AWS = AwsBatchConfig(region="eu-west-1", job_queue="genomics-spot", bucket="my-lab-nf")
GCP = GoogleBatchConfig(project="my-lab-project", location="us-central1", bucket="my-lab-nf")


# ─────────────────────────── rendering ────────────────────────────────────────

def test_aws_config_selects_the_batch_executor_and_queue():
    rendered = render_aws_batch_config(AWS)
    assert "process.executor = 'awsbatch'" in rendered
    assert "process.queue = 'genomics-spot'" in rendered
    assert "region = 'eu-west-1'" in rendered


def test_aws_work_directory_is_on_s3():
    # The compute nodes share no filesystem with the launching host, so a
    # local work directory fails at task startup rather than at submission.
    assert "workDir = 's3://my-lab-nf/work'" in render_aws_batch_config(AWS)


def test_a_prefix_is_placed_inside_the_bucket():
    rendered = render_aws_batch_config(
        AwsBatchConfig(region="eu-west-1", job_queue="q", bucket="my-lab-nf", prefix="runs/2026")
    )
    assert "workDir = 's3://my-lab-nf/runs/2026/work'" in rendered


def test_google_config_selects_batch_with_project_and_location():
    rendered = render_google_batch_config(GCP)
    assert "process.executor = 'google-batch'" in rendered
    assert "project = 'my-lab-project'" in rendered
    assert "location = 'us-central1'" in rendered
    assert "workDir = 'gs://my-lab-nf/work'" in rendered


def test_neither_config_can_carry_a_credential():
    """A generated config is written to disk and shown in the UI.

    Nextflow reads credentials from the environment, an instance profile or
    application default credentials, so there is no field here to hold one and
    nothing secret should appear in the output.
    """
    secretish = re.compile(
        r"(accesskey|secretkey|secret_?access|password|token|api_?key|credentials_?file)",
        re.IGNORECASE,
    )
    for rendered in (render_aws_batch_config(AWS), render_google_batch_config(GCP)):
        for line in rendered.splitlines():
            # Comments explain where credentials come from; only assignments
            # could actually carry one.
            if line.strip().startswith("//") or "=" not in line:
                continue
            assert not secretish.search(line), f"a credential-shaped setting was rendered: {line}"
    # There is nowhere to put one in the first place.
    assert not hasattr(AWS, "access_key")
    assert not hasattr(GCP, "service_account_key")


# ─────────────────────────── validation ───────────────────────────────────────

@pytest.mark.parametrize(
    "region",
    ["", "eu_west_1", "EU-WEST-1", "eu-west", "eu-west-1a", "'; rm -rf /", "eu-west-1\nx"],
)
def test_a_region_that_is_not_an_aws_region_is_refused(region):
    with pytest.raises(ValueError, match="region"):
        validate_aws_batch_settings(AwsBatchConfig(region=region, job_queue="q", bucket="a-bucket"))


@pytest.mark.parametrize("region", ["us-east-1", "eu-west-2", "ap-southeast-1", "us-gov-west-1"])
def test_real_aws_regions_are_accepted(region):
    assert validate_aws_batch_settings(
        AwsBatchConfig(region=region, job_queue="q", bucket="a-bucket")
    ).region == region


@pytest.mark.parametrize("queue", ["", "my queue", "queue'; x", "-leading", "q" * 200])
def test_a_job_queue_name_aws_would_reject_is_refused(queue):
    with pytest.raises(ValueError, match="job queue"):
        validate_aws_batch_settings(
            AwsBatchConfig(region="eu-west-1", job_queue=queue, bucket="a-bucket")
        )


@pytest.mark.parametrize(
    "bucket",
    ["", "ab", "My-Bucket", "bucket_underscore", "has..dots", "192.168.1.1", "b" * 70, "b'; x"],
)
def test_a_bucket_name_the_provider_would_reject_is_refused(bucket):
    # Catching this here saves a round trip to the cloud to learn something
    # that is checkable locally.
    with pytest.raises(ValueError, match="bucket"):
        validate_aws_batch_settings(
            AwsBatchConfig(region="eu-west-1", job_queue="q", bucket=bucket)
        )


@pytest.mark.parametrize("prefix", ["../escape", "runs/../..", "with space", "quote'x", "a\nb"])
def test_a_prefix_that_could_escape_the_bucket_is_refused(prefix):
    with pytest.raises(ValueError, match="prefix"):
        validate_aws_batch_settings(
            AwsBatchConfig(region="eu-west-1", job_queue="q", bucket="a-bucket", prefix=prefix)
        )


@pytest.mark.parametrize("project", ["", "Sh", "UPPER-CASE", "1starts-with-digit", "p'; x"])
def test_a_project_id_google_would_reject_is_refused(project):
    with pytest.raises(ValueError, match="project"):
        validate_google_batch_settings(
            GoogleBatchConfig(project=project, location="us-central1", bucket="a-bucket")
        )


@pytest.mark.parametrize("location", ["", "us_central1", "US-CENTRAL1", "us-central", "x'; y"])
def test_a_location_google_would_reject_is_refused(location):
    with pytest.raises(ValueError, match="location"):
        validate_google_batch_settings(
            GoogleBatchConfig(project="my-lab-project", location=location, bucket="a-bucket")
        )


def test_no_rejected_value_can_reach_the_rendered_config():
    """The point of the allow-list: injection is refused, never escaped."""
    for payload in ("q'; System.exit(1); //", "q'\nprocess.executor = 'local'\n//"):
        with pytest.raises(ValueError):
            render_aws_batch_config(
                AwsBatchConfig(region="eu-west-1", job_queue=payload, bucket="a-bucket")
            )


# ─────────────────────────── CLI ──────────────────────────────────────────────

def test_aws_batch_config_command_writes_a_file(tmp_path, capsys):
    out = tmp_path / "aws.config"
    rc = cli.main([
        "aws-batch-config", "--region", "eu-west-1", "--job-queue", "genomics-spot",
        "--bucket", "my-lab-nf", "--out", str(out),
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["path"] == str(out)
    assert "process.executor = 'awsbatch'" in out.read_text(encoding="utf-8")


def test_google_batch_config_command_writes_a_file(tmp_path, capsys):
    out = tmp_path / "gcp.config"
    rc = cli.main([
        "google-batch-config", "--project", "my-lab-project", "--location", "us-central1",
        "--bucket", "my-lab-nf", "--out", str(out),
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["path"] == str(out)
    assert "process.executor = 'google-batch'" in out.read_text(encoding="utf-8")


def test_a_bad_value_fails_the_command_without_writing_anything(tmp_path, capsys):
    out = tmp_path / "aws.config"
    rc = cli.main([
        "aws-batch-config", "--region", "nowhere", "--job-queue", "q",
        "--bucket", "my-lab-nf", "--out", str(out),
    ])
    assert rc != 0
    assert not out.exists()


def test_an_auditor_cannot_generate_an_executor_config(tmp_path, capsys):
    rc = cli.main([
        "--role", "auditor", "aws-batch-config", "--region", "eu-west-1",
        "--job-queue", "q", "--bucket", "my-lab-nf", "--out", str(tmp_path / "x.config"),
    ])
    assert rc != 0
    assert "not allowed" in capsys.readouterr().err


# ─────────────────────────── run integration ──────────────────────────────────

def test_a_cloud_run_requires_a_generated_config(capsys):
    for runtime in ("awsbatch", "googlebatch"):
        assert cli.main(["run", "nf-core", "rnaseq", "--runtime", runtime]) == 2
        assert "requires --config" in capsys.readouterr().err


def test_a_cloud_run_threads_the_config_through(tmp_path, capsys):
    config = tmp_path / "aws.config"
    cli.main([
        "aws-batch-config", "--region", "eu-west-1", "--job-queue", "q",
        "--bucket", "my-lab-nf", "--out", str(config),
    ])
    capsys.readouterr()

    assert cli.main([
        "run", "nf-core", "rnaseq", "--runtime", "awsbatch", "--config", str(config),
    ]) == 0
    planned = [
        line for line in capsys.readouterr().out.splitlines()
        if line.startswith("[helixsh] planned:")
    ]
    assert planned, "no plan was produced"
    # An executor is not a container profile, so it contributes no -profile.
    assert str(config) in planned[0]
    assert "-profile" not in planned[0]
