from __future__ import annotations

from types import SimpleNamespace

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, FakePager

from gcp_network_mcp.gcp.shared_vpc import (
    get_shared_vpc_host_relationship,
    get_shared_vpc_host_status,
)


def test_get_shared_vpc_host_status_reports_xpn_status(client_factory) -> None:
    client_factory.compute_projects().get_xpn_host.return_value = compute_v1.Project(
        xpn_project_status="HOST"
    )
    status = get_shared_vpc_host_status(client_factory, project_id=PROJECT_ID)
    assert status.project_id == PROJECT_ID
    assert status.xpn_project_status == "HOST"
    client_factory.compute_projects().get_xpn_host.assert_called_once_with(project=PROJECT_ID)


def test_get_shared_vpc_host_relationship_lists_service_projects(client_factory) -> None:
    resource = compute_v1.XpnResourceId(id="service-project-1", type_="PROJECT")
    client_factory.compute_projects().get_xpn_resources.return_value = FakePager(
        [SimpleNamespace(resources=[resource])]
    )
    relationship = get_shared_vpc_host_relationship(client_factory, host_project_id=PROJECT_ID)
    assert relationship.host_project_id == PROJECT_ID
    assert len(relationship.service_projects) == 1
    assert relationship.service_projects[0].resource_id == "service-project-1"
    assert relationship.service_projects[0].resource_type == "PROJECT"
