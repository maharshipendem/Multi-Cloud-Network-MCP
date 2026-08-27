"""MCP tools: Direct Connect connections, LAGs, virtual interfaces, and gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.directconnect import (
    list_direct_connect_connections,
    list_direct_connect_gateways,
    list_direct_connect_lags,
    list_direct_connect_virtual_interfaces,
)
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_CONNECTIONS = "aws_list_direct_connect_connections"
_LIST_LAGS = "aws_list_direct_connect_lags"
_LIST_VIFS = "aws_list_direct_connect_virtual_interfaces"
_LIST_GATEWAYS = "aws_list_direct_connect_gateways"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_CONNECTIONS,
        description=(
            "List Direct Connect connections, including hosted connections "
            "visible to this identity (directconnect:DescribeConnections)."
        ),
        meta=capability_meta(resource_types=["direct_connect_connection"]),
    )
    def aws_list_direct_connect_connections(
        region: str, connection_id: str | None = None
    ) -> dict[str, Any]:
        """List Direct Connect connections.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            connection_id: Optional connection ID to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_CONNECTIONS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_direct_connect_connections(
                client_factory, region=region, connection_id=connection_id
            ),
        )

    @mcp.tool(
        name=_LIST_LAGS,
        description="List Direct Connect Link Aggregation Groups (directconnect:DescribeLags).",
        meta=capability_meta(resource_types=["direct_connect_lag"]),
    )
    def aws_list_direct_connect_lags(region: str, lag_id: str | None = None) -> dict[str, Any]:
        """List Direct Connect LAGs.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            lag_id: Optional LAG ID to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_LAGS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_direct_connect_lags(client_factory, region=region, lag_id=lag_id),
        )

    @mcp.tool(
        name=_LIST_VIFS,
        description=(
            "List Direct Connect virtual interfaces (private/public), "
            "including BGP peer operational status "
            "(directconnect:DescribeVirtualInterfaces). BGP authentication "
            "keys are never returned -- see docs/security.md."
        ),
        meta=capability_meta(resource_types=["direct_connect_virtual_interface"]),
    )
    def aws_list_direct_connect_virtual_interfaces(
        region: str,
        connection_id: str | None = None,
        virtual_interface_id: str | None = None,
    ) -> dict[str, Any]:
        """List Direct Connect virtual interfaces.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            connection_id: Optional connection ID to restrict results to.
            virtual_interface_id: Optional virtual interface ID.
        """
        return execute_tool(
            tool_name=_LIST_VIFS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_direct_connect_virtual_interfaces(
                client_factory,
                region=region,
                connection_id=connection_id,
                virtual_interface_id=virtual_interface_id,
            ),
        )

    @mcp.tool(
        name=_LIST_GATEWAYS,
        description=(
            "List Direct Connect Gateways (global-scope), optionally with "
            "their VGW/TGW associations (directconnect:DescribeDirectConnectGateways"
            "+DescribeDirectConnectGatewayAssociations)."
        ),
        meta=capability_meta(resource_types=["direct_connect_gateway"]),
    )
    def aws_list_direct_connect_gateways(
        region: str,
        direct_connect_gateway_id: str | None = None,
        include_associations: bool = False,
    ) -> dict[str, Any]:
        """List Direct Connect Gateways.

        Args:
            region: AWS region whose Direct Connect endpoint issues the call
                (the gateway itself is global-scope), e.g. "us-east-1".
            direct_connect_gateway_id: Optional gateway ID to restrict results to.
            include_associations: If true, also fetch each gateway's VGW/TGW
                associations (1 extra API call per gateway, bounded and
                best-effort).
        """
        return execute_tool(
            tool_name=_LIST_GATEWAYS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_direct_connect_gateways(
                client_factory,
                region=region,
                direct_connect_gateway_id=direct_connect_gateway_id,
                include_associations=include_associations,
            ),
        )
