"""Discovers which projects this server is permitted to operate against."""

from __future__ import annotations

from google.api_core import exceptions as gax
from google.cloud import resourcemanager_v3

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult
from gcp_network_mcp.gcp.errors import translate_gcp_error
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.models.common import CollectionWarning
from gcp_network_mcp.models.projects import PermittedProject


def _normalize(project: resourcemanager_v3.Project, *, source: str) -> PermittedProject:
    return PermittedProject(
        project_id=project.project_id,
        display_name=project.display_name or None,
        state=project.state.name,
        parent=project.parent or None,
        source=source,
    )


def list_permitted_projects(client_factory: ClientFactory) -> CollectionResult:
    """List the projects this server is permitted to operate against.

    When ``GCP_PROJECT_ALLOWLIST`` is configured, this fetches exactly
    those projects (``source="allowlist"``); a project in the allowlist
    the configured identity cannot read is reported as a warning, not a
    failure of the whole call. Otherwise, this discovers whatever
    Resource Manager's ``search_projects`` returns for the configured
    identity (``source="search"``) -- i.e. every project its IAM bindings
    expose.
    """
    client = client_factory.resource_manager_projects()
    allowlist = client_factory.settings.project_allowlist

    if allowlist is not None:
        projects: list[PermittedProject] = []
        warnings: list[CollectionWarning] = []
        for project_id in allowlist:
            try:
                raw = call_readonly(client, "get_project", name=f"projects/{project_id}")
            except gax.GoogleAPICallError as exc:
                error = translate_gcp_error(exc, resource_type="project", project_id=project_id)
                warnings.append(
                    CollectionWarning(
                        resource_type="project",
                        code=error.error_type,
                        message=error.message,
                        project_id=project_id,
                    )
                )
                continue
            projects.append(_normalize(raw, source="allowlist"))
        return CollectionResult(data=projects, warnings=warnings)

    raw_projects = paginate(
        client,
        "search_projects",
        resource_type="project",
        items_field="projects",
    )
    return CollectionResult(data=[_normalize(p, source="search") for p in raw_projects])


__all__ = ["list_permitted_projects"]
