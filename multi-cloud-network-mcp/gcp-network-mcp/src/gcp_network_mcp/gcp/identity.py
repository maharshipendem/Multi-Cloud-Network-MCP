"""Caller-identity resolution: who this server is currently authenticated
as, without ever touching resolved token material."""

from __future__ import annotations

from google.auth import impersonated_credentials
from google.auth.credentials import Credentials as GoogleCredentials

from gcp_network_mcp.auth.credentials import READ_ONLY_SCOPES, get_shared_credentials
from gcp_network_mcp.config import Settings
from gcp_network_mcp.models.identity import CallerIdentity


def _resolve_principal(credentials: GoogleCredentials) -> str | None:
    """Best-effort human-readable principal for common ADC credential
    types. Returns ``None`` (never guesses) for credential types that
    don't expose one, e.g. some workload identity federation flows."""
    service_account_email = getattr(credentials, "service_account_email", None)
    if service_account_email and service_account_email != "default":
        return str(service_account_email)
    signer_email = getattr(credentials, "signer_email", None)
    if signer_email:
        return str(signer_email)
    return None


def get_caller_identity(settings: Settings) -> CallerIdentity:
    credentials, adc_project_id = get_shared_credentials(settings)

    if isinstance(credentials, impersonated_credentials.Credentials):
        credential_type = "impersonated_service_account"
        principal = settings.gcp_impersonate_service_account
    else:
        credential_type = type(credentials).__name__
        principal = _resolve_principal(credentials)

    return CallerIdentity(
        principal=principal,
        credential_type=credential_type,
        impersonated_service_account=settings.gcp_impersonate_service_account,
        adc_project_id=adc_project_id,
        scopes=list(READ_ONLY_SCOPES),
        quota_project_id=settings.gcp_quota_project_id,
    )


__all__ = ["get_caller_identity"]
