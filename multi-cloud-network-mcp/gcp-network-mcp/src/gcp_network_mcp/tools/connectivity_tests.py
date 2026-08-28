"""MCP tools: gcp_list_connectivity_tests, gcp_get_connectivity_test."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.connectivity_tests import get_connectivity_test, list_connectivity_tests
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_LIST_TESTS = "gcp_list_connectivity_tests"
_GET_TEST = "gcp_get_connectivity_test"


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=_LIST_TESTS,
        description=(
            "List existing Network Management Connectivity Tests and their last-computed "
            "reachability result. Never creates, reruns, updates, or deletes a test."
        ),
        meta=capability_meta(resource_types=["connectivity_test"]),
    )
    def gcp_list_connectivity_tests(project_id: str | None = None) -> dict[str, Any]:
        """List Connectivity Tests.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_LIST_TESTS,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: list_connectivity_tests(client_factory, project_id=resolved),
        )

    @mcp.tool(
        name=_GET_TEST,
        description=(
            "Get one existing Connectivity Test by name, including its last-computed "
            "reachability result."
        ),
        meta=capability_meta(resource_types=["connectivity_test"]),
    )
    def gcp_get_connectivity_test(test_name: str, project_id: str | None = None) -> dict[str, Any]:
        """Get a Connectivity Test.

        Args:
            test_name: Name of the Connectivity Test.
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=_GET_TEST,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: get_connectivity_test(
                client_factory, project_id=resolved, test_name=test_name
            ),
        )
