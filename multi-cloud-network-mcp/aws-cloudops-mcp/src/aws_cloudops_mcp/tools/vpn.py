"""MCP tools: Site-to-Site VPN connections, customer gateways, and VPN gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.vpn import list_customer_gateways, list_vpn_connections, list_vpn_gateways
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_VPN_CONNECTIONS = "aws_list_vpn_connections"
_LIST_CUSTOMER_GATEWAYS = "aws_list_customer_gateways"
_LIST_VPN_GATEWAYS = "aws_list_vpn_gateways"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_VPN_CONNECTIONS,
        description=(
            "List Site-to-Site VPN connections, including tunnel status and "
            "static routes (ec2:DescribeVpnConnections). Pre-shared keys and "
            "the raw customer gateway configuration blob are never returned "
            "-- see docs/security.md."
        ),
        meta=capability_meta(resource_types=["vpn_connection"]),
    )
    def aws_list_vpn_connections(
        region: str,
        vpn_connection_ids: list[str] | None = None,
        transit_gateway_id: str | None = None,
    ) -> dict[str, Any]:
        """List Site-to-Site VPN connections.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpn_connection_ids: Optional list of VPN connection IDs.
            transit_gateway_id: Optional Transit Gateway ID to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_VPN_CONNECTIONS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_vpn_connections(
                client_factory,
                region=region,
                vpn_connection_ids=vpn_connection_ids,
                transit_gateway_id=transit_gateway_id,
            ),
        )

    @mcp.tool(
        name=_LIST_CUSTOMER_GATEWAYS,
        description=(
            "List customer gateways -- the on-premises side of a Site-to-"
            "Site VPN (ec2:DescribeCustomerGateways)."
        ),
        meta=capability_meta(resource_types=["customer_gateway"]),
    )
    def aws_list_customer_gateways(
        region: str, customer_gateway_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List customer gateways.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            customer_gateway_ids: Optional list of customer gateway IDs.
        """
        return execute_tool(
            tool_name=_LIST_CUSTOMER_GATEWAYS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_customer_gateways(
                client_factory, region=region, customer_gateway_ids=customer_gateway_ids
            ),
        )

    @mcp.tool(
        name=_LIST_VPN_GATEWAYS,
        description=(
            "List virtual private gateways -- the AWS side of a classic "
            "Site-to-Site VPN, distinct from a Transit Gateway "
            "(ec2:DescribeVpnGateways)."
        ),
        meta=capability_meta(resource_types=["vpn_gateway"]),
    )
    def aws_list_vpn_gateways(
        region: str, vpn_gateway_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List virtual private gateways.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpn_gateway_ids: Optional list of VPN gateway IDs.
        """
        return execute_tool(
            tool_name=_LIST_VPN_GATEWAYS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_vpn_gateways(
                client_factory, region=region, vpn_gateway_ids=vpn_gateway_ids
            ),
        )
