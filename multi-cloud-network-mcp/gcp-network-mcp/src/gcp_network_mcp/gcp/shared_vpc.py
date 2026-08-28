"""Service-layer functions for Shared VPC host/service-project
relationships -- entirely via ``compute_v1.ProjectsClient`` (distinct
from ``resourcemanager_v3.ProjectsClient``, which handles general
project metadata, not Shared VPC).

Only the read-only discovery calls (``get_xpn_host``, ``get_xpn_resources``,
``list_xpn_hosts``) are used here. Their mutating counterparts
(``enable_xpn_host``/``enable_xpn_resource``/``disable_xpn_host``/
``disable_xpn_resource``) are never called anywhere in this codebase.
"""

from __future__ import annotations

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import record_call
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.models.shared_vpc import (
    SharedVpcHostRelationship,
    SharedVpcHostStatus,
    SharedVpcServiceProject,
)


def get_shared_vpc_host_status(
    client_factory: ClientFactory, *, project_id: str
) -> SharedVpcHostStatus:
    """Whether ``project_id`` is a Shared VPC host (or standalone/service
    project), via ``ProjectsClient.get_xpn_host``."""
    project = call_readonly(client_factory.compute_projects(), "get_xpn_host", project=project_id)
    record_call()
    return SharedVpcHostStatus(project_id=project_id, xpn_project_status=project.xpn_project_status)


def get_shared_vpc_host_relationship(
    client_factory: ClientFactory, *, host_project_id: str
) -> SharedVpcHostRelationship:
    """Every service project attached to ``host_project_id``, via
    ``ProjectsClient.get_xpn_resources``. Only meaningful when
    ``host_project_id`` is actually a Shared VPC host -- callers should
    check ``get_shared_vpc_host_status`` first."""
    raw = paginate(
        client_factory.compute_projects(),
        "get_xpn_resources",
        resource_type="shared_vpc_service_project",
        project_id=host_project_id,
        items_field="resources",
        project=host_project_id,
    )
    return SharedVpcHostRelationship(
        host_project_id=host_project_id,
        service_projects=[
            SharedVpcServiceProject(resource_id=r.id, resource_type=r.type_) for r in raw
        ],
    )


__all__ = ["get_shared_vpc_host_relationship", "get_shared_vpc_host_status"]
