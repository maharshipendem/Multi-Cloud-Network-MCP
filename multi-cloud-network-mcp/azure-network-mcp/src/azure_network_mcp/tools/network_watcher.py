"""MCP tools: Network Watcher topology, existing connection monitors, and
flow log configuration. Never creates, starts, or stops a Network
Watcher, connection monitor, troubleshooter, or packet capture."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.network_watcher import (
    get_network_topology,
    list_connection_monitors,
    list_flow_logs,
    list_network_watchers,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_NETWORK_WATCHERS = "azure_list_network_watchers"
_GET_NETWORK_TOPOLOGY = "azure_get_network_topology"
_LIST_CONNECTION_MONITORS = "azure_list_connection_monitors"
_LIST_FLOW_LOGS = "azure_list_flow_logs"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_NETWORK_WATCHERS,
        description=("List Network Watcher instances (whole subscription, or one resource group)."),
        meta=capability_meta(resource_types=["network_watcher"]),
    )
    def azure_list_network_watchers(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List Network Watchers.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_NETWORK_WATCHERS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_network_watchers(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_GET_NETWORK_TOPOLOGY,
        description=(
            "Get Azure's own resource-association topology for one resource "
            "group, via Network Watcher. This is Azure's native topology, "
            "distinct from this server's self-computed azure_get_vnet_topology."
        ),
        meta=capability_meta(resource_types=["network_watcher"]),
    )
    def azure_get_network_topology(
        resource_group: str,
        network_watcher_name: str,
        target_resource_group: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get Azure's native topology for one resource group.

        Args:
            resource_group: Resource group containing the Network Watcher.
            network_watcher_name: Name of the Network Watcher.
            target_resource_group: Resource group to compute the topology for.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_GET_NETWORK_TOPOLOGY,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: get_network_topology(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                network_watcher_name=network_watcher_name,
                target_resource_group=target_resource_group,
            ),
        )

    @mcp.tool(
        name=_LIST_CONNECTION_MONITORS,
        description=(
            "List one Network Watcher's existing connection monitors, including "
            "last-known monitoring status. Never creates, starts, or stops one."
        ),
        meta=capability_meta(resource_types=["network_watcher"]),
    )
    def azure_list_connection_monitors(
        resource_group: str, network_watcher_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List connection monitors.

        Args:
            resource_group: Resource group containing the Network Watcher.
            network_watcher_name: Name of the Network Watcher.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_CONNECTION_MONITORS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_connection_monitors(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                network_watcher_name=network_watcher_name,
            ),
        )

    @mcp.tool(
        name=_LIST_FLOW_LOGS,
        description=(
            "List one Network Watcher's flow log configurations (VNet and NSG "
            "flow logs share one unified API). Configuration and delivery "
            "metadata only, never log record contents."
        ),
        meta=capability_meta(resource_types=["network_watcher"]),
    )
    def azure_list_flow_logs(
        resource_group: str, network_watcher_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List flow log configurations.

        Args:
            resource_group: Resource group containing the Network Watcher.
            network_watcher_name: Name of the Network Watcher.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_FLOW_LOGS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_flow_logs(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                network_watcher_name=network_watcher_name,
            ),
        )
