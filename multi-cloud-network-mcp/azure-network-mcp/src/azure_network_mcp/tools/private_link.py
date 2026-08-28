"""MCP tools: Private Endpoints, Private Link Services, and service
endpoint policies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.private_link import (
    list_private_endpoints,
    list_private_link_services,
    list_service_endpoint_policies,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_PRIVATE_ENDPOINTS = "azure_list_private_endpoints"
_LIST_PRIVATE_LINK_SERVICES = "azure_list_private_link_services"
_LIST_SERVICE_ENDPOINT_POLICIES = "azure_list_service_endpoint_policies"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_PRIVATE_ENDPOINTS,
        description=(
            "List Private Endpoints (whole subscription, or one resource "
            "group), including subnet, NIC, and Private Link Service connections."
        ),
        meta=capability_meta(resource_types=["private_endpoint"]),
    )
    def azure_list_private_endpoints(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Private Endpoints.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_PRIVATE_ENDPOINTS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_private_endpoints(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_PRIVATE_LINK_SERVICES,
        description=(
            "List Private Link Services (whole subscription, or one resource "
            "group), including visibility/auto-approval subscription lists and "
            "connected private endpoint count."
        ),
        meta=capability_meta(resource_types=["private_link_service"]),
    )
    def azure_list_private_link_services(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Private Link Services.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_PRIVATE_LINK_SERVICES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_private_link_services(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_SERVICE_ENDPOINT_POLICIES,
        description=(
            "List service endpoint policies (whole subscription, or one "
            "resource group), including associated subnets and a definition count."
        ),
        meta=capability_meta(resource_types=["service_endpoint_policy"]),
    )
    def azure_list_service_endpoint_policies(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List service endpoint policies.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_SERVICE_ENDPOINT_POLICIES,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_service_endpoint_policies(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )
