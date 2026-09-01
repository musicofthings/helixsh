"""Safe generation of Nextflow AWS Batch and Google Batch executor config.

Follows the nf-k8s generator: every value is checked against an allow-list
before it reaches a single-quoted Groovy string, rather than a deny-list of
characters known to be dangerous, so nothing that could break out of the
quoting is rendered at all.

Credentials are deliberately absent. Nextflow reads AWS credentials from the
environment, an instance profile or a named profile, and Google credentials
from application default credentials, so there is no reason to put a secret
in a file that is written to disk, shown in the UI and recorded in an audit
log. This module has no field to hold one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# us-east-1, eu-west-2, ap-southeast-1, us-gov-west-1.
AWS_REGION_RE = re.compile(r"^[a-z]{2}(?:-[a-z]+)+-\d$")
# AWS Batch job queue names: letters, digits, hyphen and underscore.
AWS_QUEUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
# Google project IDs are 6-30 characters, starting with a letter.
GCP_PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
# us-central1, europe-west4, asia-northeast1.
GCP_LOCATION_RE = re.compile(r"^[a-z]+-[a-z]+\d$")
# Bucket naming is shared closely enough between S3 and GCS for one rule:
# lowercase letters, digits, hyphen and dot, 3-63 characters.
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
# A key prefix inside the bucket. Empty is fine; the work directory is
# appended to it.
OBJECT_PREFIX_RE = re.compile(r"^(?:[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)?$")


@dataclass(frozen=True)
class AwsBatchConfig:
    region: str
    job_queue: str
    bucket: str
    prefix: str = ""


@dataclass(frozen=True)
class GoogleBatchConfig:
    project: str
    location: str
    bucket: str
    prefix: str = ""


def _validate(field: str, value: str, pattern: re.Pattern[str], expectation: str) -> str:
    normalized = str(value or "").strip()
    if not pattern.fullmatch(normalized):
        raise ValueError(f"{field} {expectation}")
    return normalized


def _validate_bucket(value: str) -> str:
    bucket = _validate(
        "bucket",
        value,
        BUCKET_RE,
        "must be 3-63 characters of lowercase letters, digits, dots or hyphens",
    )
    # Both providers reject these, and finding out at submission time costs a
    # round trip to the cloud to learn something checkable here.
    if ".." in bucket:
        raise ValueError("bucket must not contain consecutive dots")
    if re.fullmatch(r"\d+(?:\.\d+){3}", bucket):
        raise ValueError("bucket must not look like an IP address")
    return bucket


def _validate_prefix(value: str) -> str:
    prefix = str(value or "").strip().strip("/")
    if not OBJECT_PREFIX_RE.fullmatch(prefix):
        raise ValueError(
            "prefix must be a plain object path of letters, digits, dots, "
            "hyphens and underscores"
        )
    # Dots are legal inside a segment but a segment that is only dots is a
    # relative path element. Object keys are flat, so these do not traverse
    # anywhere, but they produce a key nobody meant and that some tools
    # normalise differently.
    if any(segment in {".", ".."} for segment in prefix.split("/") if segment):
        raise ValueError("prefix must not contain '.' or '..' segments")
    return prefix


def _work_dir(scheme: str, bucket: str, prefix: str) -> str:
    """The work directory these executors require to be object storage.

    A local work directory is the most common way an AWS Batch run fails: the
    head node and the compute nodes do not share a filesystem, so tasks cannot
    find their inputs. Generating it removes the choice.
    """
    return f"{scheme}://{bucket}/{prefix}/work" if prefix else f"{scheme}://{bucket}/work"


def validate_aws_batch_settings(config: AwsBatchConfig) -> AwsBatchConfig:
    return AwsBatchConfig(
        region=_validate("region", config.region, AWS_REGION_RE, "must be an AWS region such as eu-west-1"),
        job_queue=_validate(
            "job queue",
            config.job_queue,
            AWS_QUEUE_RE,
            "must be an AWS Batch job queue name",
        ),
        bucket=_validate_bucket(config.bucket),
        prefix=_validate_prefix(config.prefix),
    )


def validate_google_batch_settings(config: GoogleBatchConfig) -> GoogleBatchConfig:
    return GoogleBatchConfig(
        project=_validate(
            "project",
            config.project,
            GCP_PROJECT_RE,
            "must be a Google Cloud project id of 6-30 characters",
        ),
        location=_validate(
            "location",
            config.location,
            GCP_LOCATION_RE,
            "must be a Google Cloud location such as us-central1",
        ),
        bucket=_validate_bucket(config.bucket),
        prefix=_validate_prefix(config.prefix),
    )


def render_aws_batch_config(config: AwsBatchConfig) -> str:
    settings = validate_aws_batch_settings(config)
    work_dir = _work_dir("s3", settings.bucket, settings.prefix)
    return (
        "process.executor = 'awsbatch'\n"
        f"process.queue = '{settings.job_queue}'\n"
        "\n"
        "aws {\n"
        f"    region = '{settings.region}'\n"
        "}\n"
        "\n"
        "// AWS Batch runs tasks on machines that share no filesystem with the\n"
        "// launching host, so the work directory has to be on S3.\n"
        f"workDir = '{work_dir}'\n"
        "\n"
        "// Credentials are read from the environment, an instance profile or a\n"
        "// named profile. Nothing secret is written here.\n"
    )


def render_google_batch_config(config: GoogleBatchConfig) -> str:
    settings = validate_google_batch_settings(config)
    work_dir = _work_dir("gs", settings.bucket, settings.prefix)
    return (
        "process.executor = 'google-batch'\n"
        "\n"
        "google {\n"
        f"    project = '{settings.project}'\n"
        f"    location = '{settings.location}'\n"
        "}\n"
        "\n"
        "// Google Batch runs tasks on machines that share no filesystem with\n"
        "// the launching host, so the work directory has to be on Cloud Storage.\n"
        f"workDir = '{work_dir}'\n"
        "\n"
        "// Credentials come from application default credentials. Nothing\n"
        "// secret is written here.\n"
    )


def write_aws_batch_config(path: str, config: AwsBatchConfig) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_aws_batch_config(config), encoding="utf-8")
    return destination


def write_google_batch_config(path: str, config: GoogleBatchConfig) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_google_batch_config(config), encoding="utf-8")
    return destination
