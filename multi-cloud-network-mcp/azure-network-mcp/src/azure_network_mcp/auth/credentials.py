"""Credential resolution via ``azure.identity.DefaultAzureCredential``.

This module never accepts, constructs from, or stores a raw secret
(client secret, certificate private key, access token) -- it builds
exactly one ``DefaultAzureCredential`` and lets the Azure Identity SDK
resolve actual credential material itself, from (in order) environment
variables (``AZURE_CLIENT_ID``/``AZURE_CLIENT_SECRET``/``AZURE_TENANT_ID``
for a service principal, or ``AZURE_CLIENT_CERTIFICATE_PATH`` for
certificate auth), workload identity federation, a managed identity, or
an interactively-authenticated Azure CLI/PowerShell/Developer CLI
session. ``Settings.azure_tenant_id``/``azure_client_id`` are non-secret
identifiers that only narrow *which* identity/tenant this resolves
against -- see docs/security.md#credential-handling for the full model
and how to configure each credential source safely.
"""

from __future__ import annotations

from functools import lru_cache

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential

from azure_network_mcp.config import Settings


@lru_cache
def _cached_credential(tenant_id: str | None, client_id: str | None) -> TokenCredential:
    # DefaultAzureCredential has no single unified `tenant_id` kwarg (it
    # raises TypeError if one is passed) -- each sub-credential that
    # supports tenant scoping takes its own tenant kwarg, defaulting to the
    # AZURE_TENANT_ID environment variable if unset. Passing the same value
    # to all four explicitly (rather than relying on that env var, which may
    # not be set) scopes every sub-credential that could activate.
    kwargs: dict[str, str] = {}
    if tenant_id:
        kwargs["interactive_browser_tenant_id"] = tenant_id
        kwargs["workload_identity_tenant_id"] = tenant_id
        kwargs["broker_tenant_id"] = tenant_id
        kwargs["shared_cache_tenant_id"] = tenant_id
    if client_id:
        kwargs["managed_identity_client_id"] = client_id
    return DefaultAzureCredential(**kwargs)


def get_shared_credential(settings: Settings) -> TokenCredential:
    """Return a process-wide cached credential for this configuration.

    Caching avoids re-resolving (and, for interactive credentials like
    Azure CLI, re-shelling-out for) a credential on every tool call --
    ``DefaultAzureCredential`` itself already caches *tokens* internally,
    but constructing a fresh credential instance per call would defeat
    that. ``DefaultAzureCredential`` never logs or exposes the resolved
    token; callers of this credential (the ARM SDK clients) attach it to
    outgoing requests internally, and nothing in this codebase calls
    ``get_token()`` directly or otherwise touches the token value.
    """
    return _cached_credential(settings.azure_tenant_id, settings.azure_client_id)


__all__ = ["get_shared_credential"]
