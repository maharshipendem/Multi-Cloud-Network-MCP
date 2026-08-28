"""Environment-variable-driven configuration.

Never accepts a service account key file's contents, a raw access token,
or any other secret material as a configuration value. All of
``GCP_QUOTA_PROJECT_ID``, ``GCP_IMPERSONATE_SERVICE_ACCOUNT``, and every
allowlist below are non-secret *identifiers* used to scope which
credential/project/folder/organization this server resolves against and
operates on -- the actual credential material is resolved by
``google.auth.default()`` (Application Default Credentials) from its own
standard sources (a user ADC file from `gcloud auth application-default
login`, a service account attached to the compute environment, or
workload identity federation), never read, stored, or logged by this
module. See docs/security.md#credential-handling.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "gcp-network-mcp"
    log_level: str = "INFO"

    # Non-secret quota/billing project and impersonation target. Both
    # optional -- ADC works with zero configuration against a user login,
    # an attached service account, or workload identity federation.
    gcp_quota_project_id: str | None = None
    gcp_impersonate_service_account: str | None = None

    # Project/folder/organization allowlists (comma-separated IDs or
    # numbers). When set, any tool call naming a project/folder/
    # organization outside the list is rejected before any GCP API call
    # is made -- see auth/session.py. Unset means "whatever the
    # configured identity's IAM bindings permit," matching how the
    # AWS/Azure siblings in this family default to IAM/RBAC-only scoping.
    gcp_project_allowlist: str | None = None
    gcp_folder_allowlist: str | None = None
    gcp_organization_allowlist: str | None = None

    # Project used when a tool call doesn't specify one.
    gcp_default_project_id: str | None = None

    gcp_max_retries: int = 3
    gcp_timeout_seconds: float = 20.0
    max_page_results: int = 1000
    max_fanout_calls: int = 50
    max_concurrency: int = 10

    @property
    def project_allowlist(self) -> list[str] | None:
        if not self.gcp_project_allowlist:
            return None
        return [p.strip() for p in self.gcp_project_allowlist.split(",") if p.strip()]

    @property
    def folder_allowlist(self) -> list[str] | None:
        if not self.gcp_folder_allowlist:
            return None
        return [f.strip() for f in self.gcp_folder_allowlist.split(",") if f.strip()]

    @property
    def organization_allowlist(self) -> list[str] | None:
        if not self.gcp_organization_allowlist:
            return None
        return [o.strip() for o in self.gcp_organization_allowlist.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
