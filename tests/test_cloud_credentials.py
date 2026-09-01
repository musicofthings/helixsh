"""Where a cloud run will get its credentials -- established without using them."""

import pytest

from helixsh import cloud_credentials
from helixsh.cloud_credentials import (
    check_aws_credentials,
    check_google_credentials,
    collect_cloud_credentials,
)

_CLOUD_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_ROLE_ARN",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "GOOGLE_APPLICATION_CREDENTIALS",
)


@pytest.fixture
def clean_cloud_env(tmp_path, monkeypatch):
    """A host with nothing configured, and a home directory of its own.

    Without this the result depends on whoever is running the tests: a
    developer with real credentials and CI without them would disagree.
    """
    for name in _CLOUD_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cloud_credentials.Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(cloud_credentials.os, "name", "posix")
    return tmp_path


# ─────────────────────────── AWS ──────────────────────────────────────────────

def test_an_access_key_in_the_environment_is_usable(clean_cloud_env, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s3cret")

    assert check_aws_credentials().state == "ok"


def test_half_a_key_pair_is_reported_as_broken_not_absent(clean_cloud_env, monkeypatch):
    # Falling back silently here would send the user to look for a missing
    # profile when the real problem is the variable next to the one they set.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE")

    result = check_aws_credentials()

    assert result.state == "missing"
    assert "AWS_SECRET_ACCESS_KEY" in result.details


def test_a_shared_credentials_file_is_found(clean_cloud_env):
    (clean_cloud_env / ".aws").mkdir()
    (clean_cloud_env / ".aws" / "credentials").write_text("[default]\n")

    result = check_aws_credentials()

    assert result.state == "ok"
    assert "default profile" in result.details


def test_a_selected_profile_with_no_credentials_file_is_a_mistake(clean_cloud_env, monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "lab")

    result = check_aws_credentials()

    assert result.state == "missing"
    assert "lab" in result.details


def test_a_selected_profile_names_itself_when_the_file_exists(clean_cloud_env, monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "lab")
    (clean_cloud_env / ".aws").mkdir()
    (clean_cloud_env / ".aws" / "credentials").write_text("[lab]\n")

    result = check_aws_credentials()

    assert result.state == "ok"
    assert "lab" in result.details


def test_an_overridden_credentials_file_location_is_honoured(clean_cloud_env, monkeypatch):
    elsewhere = clean_cloud_env / "creds"
    elsewhere.write_text("[default]\n")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(elsewhere))

    assert check_aws_credentials().state == "ok"


def test_a_web_identity_token_that_is_missing_is_reported(clean_cloud_env, monkeypatch):
    monkeypatch.setenv("AWS_ROLE_ARN", "arn:aws:iam::123456789012:role/nextflow")
    monkeypatch.setenv("AWS_WEB_IDENTITY_TOKEN_FILE", str(clean_cloud_env / "absent"))

    result = check_aws_credentials()

    assert result.state == "missing"
    assert "AWS_WEB_IDENTITY_TOKEN_FILE" in result.details


def test_a_web_identity_token_that_exists_is_usable(clean_cloud_env, monkeypatch):
    token = clean_cloud_env / "token"
    token.write_text("header.payload.signature")
    monkeypatch.setenv("AWS_ROLE_ARN", "arn:aws:iam::123456789012:role/nextflow")
    monkeypatch.setenv("AWS_WEB_IDENTITY_TOKEN_FILE", str(token))

    assert check_aws_credentials().state == "ok"


def test_nothing_configured_is_unknown_rather_than_missing(clean_cloud_env):
    """An EC2 instance profile leaves no local trace and works perfectly.

    Reporting "missing" would be wrong on exactly the hosts most likely to be
    submitting to Batch, so the honest answer is that we cannot tell.
    """
    result = check_aws_credentials()

    assert result.state == "unknown"
    assert "instance profile" in result.details


# ─────────────────────────── Google ───────────────────────────────────────────

def test_an_explicit_service_account_key_is_usable(clean_cloud_env, monkeypatch):
    key = clean_cloud_env / "sa.json"
    key.write_text("{}")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))

    assert check_google_credentials().state == "ok"


def test_a_key_path_pointing_nowhere_is_a_mistake_not_a_fallback(clean_cloud_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(clean_cloud_env / "absent.json"))

    result = check_google_credentials()

    assert result.state == "missing"
    assert "does not exist" in result.details


def test_application_default_credentials_are_found(clean_cloud_env):
    adc = clean_cloud_env / ".config" / "gcloud"
    adc.mkdir(parents=True)
    (adc / "application_default_credentials.json").write_text("{}")

    assert check_google_credentials().state == "ok"


def test_no_google_credentials_is_unknown_because_of_the_metadata_server(clean_cloud_env):
    result = check_google_credentials()

    assert result.state == "unknown"
    assert "metadata server" in result.details


# ─────────────────────────── the whole answer ─────────────────────────────────

def test_no_credential_value_is_ever_reported(clean_cloud_env, monkeypatch):
    """The details reach the UI and the audit log, so they name sources only."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI-EXAMPLE-KEY")
    key = clean_cloud_env / "sa.json"
    key.write_text('{"private_key": "-----BEGIN PRIVATE KEY-----"}')
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))

    details = " ".join(result.details for result in collect_cloud_credentials())

    assert "AKIAIOSFODNN7EXAMPLE" not in details
    assert "wJalrXUtnFEMI-EXAMPLE-KEY" not in details
    assert "BEGIN PRIVATE KEY" not in details


def test_both_providers_are_always_reported(clean_cloud_env):
    assert [result.name for result in collect_cloud_credentials()] == [
        "aws-credentials",
        "google-credentials",
    ]
