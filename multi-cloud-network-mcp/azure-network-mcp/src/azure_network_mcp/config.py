"""Environment-variable-driven configuration.

Never accepts raw credentials (a client secret, a certificate's private
key, an access token) as a configuration value -- ``AZURE_TENANT_ID`` and
``AZURE_CLIENT_ID`` below are non-secret *identifiers* used to scope which
identity/tenant ``DefaultAzureCredential`` resolves against; the actual
secret material (a service principal's client secret, a certificate file)
is read by the Azure Identity SDK itself from its own standard environment
variables (``AZURE_CLIENT_SECRET``, ``AZURE_CLIENT_CERTIFICATE_PATH``) or
from a non-secret credential source (managed identity, Azure CLI login) --
this module never reads, stores, or logs any of them. See
docs/security.md#credential-handling.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "azure-network-mcp"
    log_level: str = "INFO"

    # Non-secret identity scoping for DefaultAzureCredential. Both optional --
    # DefaultAzureCredential works with zero configuration against Azure CLI
    # login, a managed identity, or workload identity federation.
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None

    # Subscription/tenant allowlists (comma-separated IDs). When set, any
    # tool call naming a subscription/tenant outside the list is rejected
    # before any Azure API call is made -- see auth/session.py. Unset means
    # "whatever the configured identity can see," matching Milestone 1's
    # "no restriction beyond IAM/RBAC" default.
    azure_subscription_allowlist: str | None = None
    azure_tenant_allowlist: str | None = None

    # Default subscription used when a tool call doesn't specify one.
    azure_default_subscription_id: str | None = None

    azure_max_retries: int = 3
    azure_connection_timeout: float = 5.0
    azure_read_timeout: float = 20.0
    max_page_results: int = 1000
    max_fanout_calls: int = 50
    max_concurrency: int = 10

    @property
    def subscription_allowlist(self) -> list[str] | None:
        if not self.azure_subscription_allowlist:
            return None
        return [s.strip() for s in self.azure_subscription_allowlist.split(",") if s.strip()]

    @property
    def tenant_allowlist(self) -> list[str] | None:
        if not self.azure_tenant_allowlist:
            return None
        return [t.strip() for t in self.azure_tenant_allowlist.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
