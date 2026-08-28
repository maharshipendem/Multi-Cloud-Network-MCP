"""Credential resolution via Application Default Credentials (ADC), with
optional service account impersonation.

This module never accepts, constructs from, or stores a raw credential
(a service account key file's private key, an access token) -- it calls
``google.auth.default()`` exactly once and lets the ADC resolution chain
find real credential material itself, from (in order): the
``GOOGLE_APPLICATION_CREDENTIALS`` environment variable (pointing at a
key file, if a deployment chooses that path -- discouraged, see
docs/security.md#credential-handling for safer alternatives), a user's
``gcloud auth application-default login`` session (the standard path for
local development), or the metadata server's attached service account
when running on Compute Engine/GKE/Cloud Run with workload identity.
``Settings.gcp_impersonate_service_account`` is a non-secret target
principal identifier that, when set, wraps the resolved base credentials
in ``google.auth.impersonated_credentials.Credentials`` scoped to
``cloud-platform.read-only`` -- the recommended safer alternative to a
downloaded JSON key file for a deployment that needs to act as a specific
service account. See docs/security.md#credential-handling for the full
model and why key files are discouraged.
"""

from __future__ import annotations

from functools import lru_cache

import google.auth
from google.auth import impersonated_credentials
from google.auth.credentials import Credentials

from gcp_network_mcp.config import Settings

READ_ONLY_SCOPES = ("https://www.googleapis.com/auth/cloud-platform.read-only",)


@lru_cache
def _cached_credentials(
    quota_project_id: str | None, impersonate_service_account: str | None
) -> tuple[Credentials, str | None]:
    base_credentials, adc_project_id = google.auth.default(
        scopes=list(READ_ONLY_SCOPES), quota_project_id=quota_project_id
    )
    if impersonate_service_account:
        credentials: Credentials = impersonated_credentials.Credentials(
            source_credentials=base_credentials,
            target_principal=impersonate_service_account,
            target_scopes=list(READ_ONLY_SCOPES),
        )
    else:
        credentials = base_credentials
    return credentials, adc_project_id


def get_shared_credentials(settings: Settings) -> tuple[Credentials, str | None]:
    """Return a process-wide cached (credentials, ADC-resolved project ID)
    pair for this configuration.

    Caching avoids re-resolving (and, for some ADC sources, re-reading a
    file or re-contacting the metadata server on) every tool call.
    Nothing in this codebase calls ``credentials.token`` directly or
    otherwise touches resolved token material -- callers of these
    credentials (the GCP client libraries) attach them to outgoing
    requests internally.
    """
    return _cached_credentials(
        settings.gcp_quota_project_id, settings.gcp_impersonate_service_account
    )


__all__ = ["READ_ONLY_SCOPES", "get_shared_credentials"]
