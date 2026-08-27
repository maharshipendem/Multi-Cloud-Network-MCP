"""MCP tools: azure_list_load_balancers, azure_list_application_gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.load_balancers import list_application_gateways, list_load_balancers
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_LOAD_BALANCERS = "azure_list_load_balancers"
_LIST_APPLICATION_GATEWAYS = "azure_list_application_gateways"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_LOAD_BALANCERS,
        description=(
            "List load balancers (whole subscription, or one resource group), "
            "including SKU, frontend/backend configuration, rules, and probes."
        ),
        meta=capability_meta(resource_types=["load_balancer"]),
    )
    def azure_list_load_balancers(
        subscription_id: str | None = None,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """List load balancers.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_LOAD_BALANCERS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_load_balancers(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_APPLICATION_GATEWAYS,
        description=(
            "List application gateways (whole subscription, or one resource group), "
            "including SKU, listeners, and both provisioning and operational state."
        ),
        meta=capability_meta(resource_types=["application_gateway"]),
    )
    def azure_list_application_gateways(
        subscription_id: str | None = None,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """List application gateways.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_APPLICATION_GATEWAYS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_application_gateways(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )
