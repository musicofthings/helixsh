"""Where a cloud run will find its credentials, checked without using them.

The generated AWS Batch and Google Batch configs deliberately hold no secret:
Nextflow resolves credentials at submission time from the environment, a
shared credentials file or application default credentials. That is the right
design, but it moves the first sign of trouble to several minutes after the
user pressed Run, when a job has already been submitted and rejected.

So this module answers the question locally, by looking only at what is
configured -- environment variable names and file locations. It never reads a
credential, never prints one, and never makes a network call, because the
answer is shown in the UI and recorded in an audit log.

The fallback that cannot be checked here is an instance profile or the GCE
metadata server: a machine inside the provider is issued credentials without
any local configuration at all. Reporting that as "missing" would be wrong on
exactly the hosts most likely to be running these pipelines, so it is reported
as unknown -- Helixsh cannot tell from here, and Nextflow may still succeed.
"""

from __future__ import annotations

import os
from pathlib import Path

from helixsh.doctor import CheckResult

AWS_CREDENTIALS = "aws-credentials"
GOOGLE_CREDENTIALS = "google-credentials"

# Set together; either alone is a half-configured environment rather than a
# usable one.
_AWS_KEY_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
_AWS_PROFILE_VARS = ("AWS_PROFILE", "AWS_DEFAULT_PROFILE")
_AWS_WEB_IDENTITY_VARS = ("AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE")

_UNKNOWN_AWS = (
    "no local credentials configured; an instance profile may still supply "
    "them, which cannot be checked from here"
)
_UNKNOWN_GOOGLE = (
    "no application default credentials found; the GCE metadata server may "
    "still supply them, which cannot be checked from here"
)


def _shared_credentials_file() -> Path:
    override = os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    return Path(override) if override else Path.home() / ".aws" / "credentials"


def _adc_file() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def check_aws_credentials() -> CheckResult:
    """How Nextflow will authenticate to AWS Batch and S3, if we can tell."""
    present = [name for name in _AWS_KEY_VARS if os.environ.get(name, "").strip()]
    if len(present) == len(_AWS_KEY_VARS):
        return CheckResult(AWS_CREDENTIALS, "ok", "access key in the environment")
    if present:
        missing = [name for name in _AWS_KEY_VARS if name not in present]
        return CheckResult(
            AWS_CREDENTIALS, "missing", f"{present[0]} is set but {missing[0]} is not"
        )

    token_file = os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE", "").strip()
    if os.environ.get("AWS_ROLE_ARN", "").strip() and token_file:
        # The token is short-lived and rotated by whatever issued it, so the
        # file being absent is a real failure rather than a fallback.
        if Path(token_file).is_file():
            return CheckResult(AWS_CREDENTIALS, "ok", "web identity token for AWS_ROLE_ARN")
        return CheckResult(
            AWS_CREDENTIALS, "missing", "AWS_WEB_IDENTITY_TOKEN_FILE does not exist"
        )

    profile = next(
        (os.environ[name] for name in _AWS_PROFILE_VARS if os.environ.get(name, "").strip()),
        "",
    )
    credentials_file = _shared_credentials_file()
    if profile:
        if credentials_file.is_file():
            return CheckResult(AWS_CREDENTIALS, "ok", f"profile '{profile}' in {credentials_file}")
        return CheckResult(
            AWS_CREDENTIALS,
            "missing",
            f"profile '{profile}' is selected but {credentials_file} does not exist",
        )
    if credentials_file.is_file():
        return CheckResult(AWS_CREDENTIALS, "ok", f"default profile in {credentials_file}")
    return CheckResult(AWS_CREDENTIALS, "unknown", _UNKNOWN_AWS)


def check_google_credentials() -> CheckResult:
    """How Nextflow will authenticate to Google Batch and Cloud Storage."""
    explicit = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if explicit:
        # Pointing the variable at a file that is not there is a mistake worth
        # reporting, not a reason to fall back silently.
        if Path(explicit).is_file():
            return CheckResult(
                GOOGLE_CREDENTIALS, "ok", f"service account key at {explicit}"
            )
        return CheckResult(
            GOOGLE_CREDENTIALS,
            "missing",
            f"GOOGLE_APPLICATION_CREDENTIALS points at {explicit}, which does not exist",
        )

    adc = _adc_file()
    if adc.is_file():
        return CheckResult(GOOGLE_CREDENTIALS, "ok", f"application default credentials at {adc}")
    return CheckResult(GOOGLE_CREDENTIALS, "unknown", _UNKNOWN_GOOGLE)


def collect_cloud_credentials() -> list[CheckResult]:
    return [check_aws_credentials(), check_google_credentials()]
