"""Low-level AWS credential resolution primitives.

Credential material never touches disk or logs here beyond what boto3
itself does internally. Nothing in this module accepts or stores raw
access keys directly -- everything flows through boto3's standard
credential resolution chain (env vars, shared config/credentials files,
SSO, container/instance metadata) or STS AssumeRole.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

from aws_cloudops_mcp.config import Settings
from aws_cloudops_mcp.exceptions import AuthenticationError, InvalidConfigurationError


@dataclass(frozen=True)
class AssumedRoleCredentials:
    """Temporary credentials obtained from sts:AssumeRole."""

    access_key: str
    secret_key: str
    session_token: str
    expiration: datetime


def build_base_session(settings: Settings) -> boto3.Session:
    """Build the base boto3 Session using standard credential resolution.

    Honors ``AWS_PROFILE``/``settings.aws_profile`` when set; otherwise
    defers entirely to boto3's default chain (environment variables, shared
    credentials/config files, SSO, or an IAM role when running in AWS).
    """
    try:
        return boto3.Session(
            profile_name=settings.aws_profile or None,
            region_name=settings.aws_default_region or None,
        )
    except ProfileNotFound as exc:
        raise InvalidConfigurationError(
            f"AWS profile '{settings.aws_profile}' was not found in the shared "
            "AWS config/credentials files."
        ) from exc


def assume_role(
    base_session: boto3.Session,
    *,
    role_arn: str,
    session_name: str,
    external_id: str | None = None,
    duration_seconds: int = 3600,
) -> AssumedRoleCredentials:
    """Call sts:AssumeRole and return normalized temporary credentials.

    This is an authentication operation, not a resource-mutating AWS API
    call, so it is intentionally not routed through the read-only
    guardrails in ``security.guardrails`` -- those guardrails govern which
    *resource* APIs (EC2, etc.) a tool may call once a session is
    established, not how that session is obtained.
    """
    sts_client = base_session.client("sts")
    request: dict[str, str | int] = {
        "RoleArn": role_arn,
        "RoleSessionName": session_name,
        "DurationSeconds": duration_seconds,
    }
    if external_id:
        request["ExternalId"] = external_id

    try:
        response = sts_client.assume_role(**request)  # type: ignore[arg-type]
    except NoCredentialsError as exc:
        raise AuthenticationError(
            "No base AWS credentials were found to assume the configured role."
        ) from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        raise AuthenticationError(f"Failed to assume role '{role_arn}': {code}.") from exc

    creds = response["Credentials"]
    return AssumedRoleCredentials(
        access_key=creds["AccessKeyId"],
        secret_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
        expiration=creds["Expiration"],
    )
