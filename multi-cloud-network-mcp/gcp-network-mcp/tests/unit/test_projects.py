from __future__ import annotations

from types import SimpleNamespace

from google.api_core import exceptions as gax
from google.cloud import resourcemanager_v3
from tests.conftest import FakePager

from gcp_network_mcp.auth.session import ResourceContext
from gcp_network_mcp.config import Settings
from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.projects import list_permitted_projects


def _factory(settings: Settings) -> ClientFactory:
    factory = ClientFactory(settings, ResourceContext(settings))
    from unittest.mock import MagicMock

    factory.resource_manager_projects = lambda m=MagicMock(): m  # type: ignore[method-assign]
    return factory


def test_list_permitted_projects_uses_search_when_no_allowlist() -> None:
    settings = Settings(_env_file=None)
    factory = _factory(settings)
    project = resourcemanager_v3.Project(
        project_id="proj-a", display_name="Project A", state=resourcemanager_v3.Project.State.ACTIVE
    )
    # search_projects response items are on `.projects`, not the default `.items`.
    factory.resource_manager_projects().search_projects.return_value = FakePager(
        [SimpleNamespace(projects=[project])]
    )

    result = list_permitted_projects(factory)
    assert len(result.data) == 1
    assert result.data[0].source == "search"
    assert result.data[0].project_id == "proj-a"
    assert result.data[0].state == "ACTIVE"
    assert result.warnings == []


def test_list_permitted_projects_uses_allowlist_when_configured() -> None:
    settings = Settings(_env_file=None, gcp_project_allowlist="proj-a,proj-b")
    factory = _factory(settings)
    factory.resource_manager_projects().get_project.side_effect = [
        resourcemanager_v3.Project(project_id="proj-a", display_name="A"),
        resourcemanager_v3.Project(project_id="proj-b", display_name="B"),
    ]
    result = list_permitted_projects(factory)
    assert len(result.data) == 2
    assert {p.source for p in result.data} == {"allowlist"}
    assert result.warnings == []


def test_list_permitted_projects_reports_warning_for_unreadable_allowlisted_project() -> None:
    settings = Settings(_env_file=None, gcp_project_allowlist="proj-a,proj-forbidden")
    factory = _factory(settings)
    factory.resource_manager_projects().get_project.side_effect = [
        resourcemanager_v3.Project(project_id="proj-a", display_name="A"),
        gax.Forbidden("no access"),
    ]
    result = list_permitted_projects(factory)
    assert len(result.data) == 1
    assert result.data[0].project_id == "proj-a"
    assert len(result.warnings) == 1
    assert result.warnings[0].project_id == "proj-forbidden"
