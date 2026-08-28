"""MCP tool: bounded Azure Monitor metric queries for network health."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.monitor import get_metrics
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

TOOL_NAME = "azure_get_network_metrics"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Query a fixed catalog of network-relevant Azure Monitor metrics for "
            "one resource (VPN/ExpressRoute gateway, firewall, load balancer, or "
            "application gateway), bounded to the last 24 hours at 5-minute "
            "granularity. Never open-ended metric discovery."
        ),
        meta=capability_meta(resource_types=["metric"]),
    )
    def azure_get_network_metrics(
        resource_id: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """Get bounded network metrics for one resource.

        Args:
            resource_id: Full ARM resource ID to query metrics for.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            subscription_id=subscription_id,
            func=lambda resolved: get_metrics(
                client_factory, subscription_id=resolved, resource_id=resource_id
            ),
        )
