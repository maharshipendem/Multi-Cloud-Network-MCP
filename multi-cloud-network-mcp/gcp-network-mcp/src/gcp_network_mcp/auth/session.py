"""Project/folder/organization allowlist enforcement.

Every tool that resolves a project ID (explicitly given, or falling back
to ``Settings.gcp_default_project_id``) passes through
``ResourceContext.resolve_project_id`` before any GCP client call is
made for it -- this is the choke point that makes an allowlist actually
enforced rather than merely documented. Unset allowlists mean "whatever
the configured identity's IAM bindings permit," matching how this
project's AWS/Azure siblings default to IAM/RBAC-only scoping; a
*configured* allowlist is an additional, optional restriction this
server enforces itself, independent of IAM.
"""

from __future__ import annotations

from gcp_network_mcp.config import Settings
from gcp_network_mcp.exceptions import InvalidConfigurationError, ProjectNotAllowedError


class ResourceContext:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve_project_id(self, requested: str | None) -> str:
        """Resolve the project ID a tool call should operate against,
        falling back to the configured default, then validate it against
        the allowlist (if one is configured)."""
        project_id = requested or self._settings.gcp_default_project_id
        if not project_id:
            raise InvalidConfigurationError(
                "No project_id was given and GCP_DEFAULT_PROJECT_ID is not "
                "configured. Pass project_id explicitly, or set a default."
            )
        self.assert_project_allowed(project_id)
        return project_id

    def assert_project_allowed(self, project_id: str) -> None:
        allowlist = self._settings.project_allowlist
        if allowlist is not None and project_id not in allowlist:
            raise ProjectNotAllowedError(
                f"Project '{project_id}' is not in the configured GCP_PROJECT_ALLOWLIST."
            )

    def assert_folder_allowed(self, folder_id: str) -> None:
        allowlist = self._settings.folder_allowlist
        if allowlist is not None and folder_id not in allowlist:
            raise ProjectNotAllowedError(
                f"Folder '{folder_id}' is not in the configured GCP_FOLDER_ALLOWLIST."
            )

    def assert_organization_allowed(self, organization_id: str) -> None:
        allowlist = self._settings.organization_allowlist
        if allowlist is not None and organization_id not in allowlist:
            raise ProjectNotAllowedError(
                f"Organization '{organization_id}' is not in the configured "
                "GCP_ORGANIZATION_ALLOWLIST."
            )


__all__ = ["ResourceContext"]
