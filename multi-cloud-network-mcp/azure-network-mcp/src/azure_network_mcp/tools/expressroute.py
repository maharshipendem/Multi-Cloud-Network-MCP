"""MCP tools: ExpressRoute circuits, peerings, connections, gateways,
ports, and links."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.expressroute import (
    list_express_route_circuit_connections,
    list_express_route_circuit_peerings,
    list_express_route_circuits,
    list_express_route_connections,
    list_express_route_gateways,
    list_express_route_links,
    list_express_route_ports,
)
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_LIST_CIRCUITS = "azure_list_express_route_circuits"
_LIST_PEERINGS = "azure_list_express_route_circuit_peerings"
_LIST_CIRCUIT_CONNECTIONS = "azure_list_express_route_circuit_connections"
_LIST_GATEWAYS = "azure_list_express_route_gateways"
_LIST_CONNECTIONS = "azure_list_express_route_connections"
_LIST_PORTS = "azure_list_express_route_ports"
_LIST_LINKS = "azure_list_express_route_links"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_CIRCUITS,
        description=(
            "List ExpressRoute circuits (whole subscription, or one resource "
            "group), including provisioning/provider status and peerings. Never "
            "includes the circuit's authorization key or service key."
        ),
        meta=capability_meta(resource_types=["express_route_circuit"]),
    )
    def azure_list_express_route_circuits(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List ExpressRoute circuits.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_CIRCUITS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_express_route_circuits(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_PEERINGS,
        description=(
            "List one ExpressRoute circuit's peerings. Never includes the peering's shared key."
        ),
        meta=capability_meta(resource_types=["express_route_circuit"]),
    )
    def azure_list_express_route_circuit_peerings(
        resource_group: str, circuit_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List ExpressRoute circuit peerings.

        Args:
            resource_group: Resource group containing the circuit.
            circuit_name: Name of the ExpressRoute circuit.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_PEERINGS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_express_route_circuit_peerings(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                circuit_name=circuit_name,
            ),
        )

    @mcp.tool(
        name=_LIST_CIRCUIT_CONNECTIONS,
        description=(
            "List one ExpressRoute peering's circuit-to-circuit (Global Reach) "
            "connections. Never includes the connection's authorization key."
        ),
        meta=capability_meta(resource_types=["express_route_circuit"]),
    )
    def azure_list_express_route_circuit_connections(
        resource_group: str,
        circuit_name: str,
        peering_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """List ExpressRoute circuit connections.

        Args:
            resource_group: Resource group containing the circuit.
            circuit_name: Name of the ExpressRoute circuit.
            peering_name: Name of the peering (e.g. "AzurePrivatePeering").
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_CIRCUIT_CONNECTIONS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_express_route_circuit_connections(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                circuit_name=circuit_name,
                peering_name=peering_name,
            ),
        )

    @mcp.tool(
        name=_LIST_GATEWAYS,
        description=(
            "List vWAN ExpressRoute gateways (whole subscription, or one resource group)."
        ),
        meta=capability_meta(resource_types=["express_route_gateway"]),
    )
    def azure_list_express_route_gateways(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List ExpressRoute gateways.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_GATEWAYS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_express_route_gateways(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_CONNECTIONS,
        description=(
            "List a vWAN ExpressRoute gateway's connections to circuit "
            "peerings. Never includes the connection's authorization key."
        ),
        meta=capability_meta(resource_types=["express_route_gateway"]),
    )
    def azure_list_express_route_connections(
        resource_group: str, express_route_gateway_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List ExpressRoute connections.

        Args:
            resource_group: Resource group containing the ExpressRoute gateway.
            express_route_gateway_name: Name of the ExpressRoute gateway.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_CONNECTIONS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_express_route_connections(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                express_route_gateway_name=express_route_gateway_name,
            ),
        )

    @mcp.tool(
        name=_LIST_PORTS,
        description=("List ExpressRoute Direct ports (whole subscription, or one resource group)."),
        meta=capability_meta(resource_types=["express_route_port"]),
    )
    def azure_list_express_route_ports(
        subscription_id: str | None = None, resource_group: str | None = None
    ) -> dict[str, Any]:
        """List ExpressRoute ports.

        Args:
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
            resource_group: Optional resource group to restrict results to.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_PORTS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_express_route_ports(
                client_factory, subscription_id=resolved, resource_group=resource_group
            ),
        )

    @mcp.tool(
        name=_LIST_LINKS,
        description="List the physical fiber links within one ExpressRoute Direct port.",
        meta=capability_meta(resource_types=["express_route_port"]),
    )
    def azure_list_express_route_links(
        resource_group: str, port_name: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """List ExpressRoute links.

        Args:
            resource_group: Resource group containing the port.
            port_name: Name of the ExpressRoute Direct port.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """
        return execute_tool_with_resolved_subscription(
            tool_name=_LIST_LINKS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=lambda resolved: list_express_route_links(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                port_name=port_name,
            ),
        )
