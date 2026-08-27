"""MCP tools: Transit Gateways, attachments, route tables, and route search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.transit_gateway import (
    DEFAULT_ROUTE_SEARCH_MAX_RESULTS,
    list_transit_gateway_attachments,
    list_transit_gateway_route_tables,
    list_transit_gateways,
    search_transit_gateway_routes,
)
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_TRANSIT_GATEWAYS = "aws_list_transit_gateways"
_LIST_TGW_ATTACHMENTS = "aws_list_transit_gateway_attachments"
_LIST_TGW_ROUTE_TABLES = "aws_list_transit_gateway_route_tables"
_SEARCH_TGW_ROUTES = "aws_search_transit_gateway_routes"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_TRANSIT_GATEWAYS,
        description="List Transit Gateways in a region (ec2:DescribeTransitGateways).",
        meta=capability_meta(resource_types=["transit_gateway"]),
    )
    def aws_list_transit_gateways(
        region: str, transit_gateway_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List Transit Gateways.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            transit_gateway_ids: Optional list of Transit Gateway IDs.
        """
        return execute_tool(
            tool_name=_LIST_TRANSIT_GATEWAYS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_transit_gateways(
                client_factory, region=region, transit_gateway_ids=transit_gateway_ids
            ),
        )

    @mcp.tool(
        name=_LIST_TGW_ATTACHMENTS,
        description=(
            "List Transit Gateway attachments (VPC/VPN/Direct Connect gateway/"
            "peering/Connect), optionally filtered by Transit Gateway or "
            "resource type (ec2:DescribeTransitGatewayAttachments)."
        ),
        meta=capability_meta(resource_types=["transit_gateway_attachment"]),
    )
    def aws_list_transit_gateway_attachments(
        region: str,
        transit_gateway_id: str | None = None,
        resource_type: str | None = None,
    ) -> dict[str, Any]:
        """List Transit Gateway attachments.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            transit_gateway_id: Optional Transit Gateway ID to restrict results to.
            resource_type: Optional attachment resource type filter, e.g.
                "vpc", "vpn", "direct-connect-gateway", "peering", "connect".
        """
        return execute_tool(
            tool_name=_LIST_TGW_ATTACHMENTS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_transit_gateway_attachments(
                client_factory,
                region=region,
                transit_gateway_id=transit_gateway_id,
                resource_type=resource_type,
            ),
        )

    @mcp.tool(
        name=_LIST_TGW_ROUTE_TABLES,
        description=(
            "List Transit Gateway route tables, optionally with associations/"
            "propagations included (ec2:DescribeTransitGatewayRouteTables, "
            "+GetTransitGatewayRouteTableAssociations/Propagations)."
        ),
        meta=capability_meta(resource_types=["transit_gateway_route_table"]),
    )
    def aws_list_transit_gateway_route_tables(
        region: str,
        transit_gateway_id: str | None = None,
        transit_gateway_route_table_ids: list[str] | None = None,
        include_associations: bool = False,
        include_propagations: bool = False,
    ) -> dict[str, Any]:
        """List Transit Gateway route tables.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            transit_gateway_id: Optional Transit Gateway ID to restrict results to.
            transit_gateway_route_table_ids: Optional list of route table IDs
                (ignored if ``transit_gateway_id`` is also given).
            include_associations: If true, also fetch each route table's
                attachment associations (1 extra API call per route table,
                bounded and best-effort).
            include_propagations: If true, also fetch each route table's
                propagations (1 extra API call per route table, bounded and
                best-effort).
        """
        return execute_tool(
            tool_name=_LIST_TGW_ROUTE_TABLES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_transit_gateway_route_tables(
                client_factory,
                region=region,
                transit_gateway_id=transit_gateway_id,
                transit_gateway_route_table_ids=transit_gateway_route_table_ids,
                include_associations=include_associations,
                include_propagations=include_propagations,
            ),
        )

    @mcp.tool(
        name=_SEARCH_TGW_ROUTES,
        description=(
            "Search a Transit Gateway route table's routes, optionally by "
            "exact-match destination CIDR or route type (static/propagated) "
            "(ec2:SearchTransitGatewayRoutes). Bounded by max_results (default "
            f"{DEFAULT_ROUTE_SEARCH_MAX_RESULTS}, capped at 1000)."
        ),
        meta=capability_meta(resource_types=["transit_gateway_route"]),
    )
    def aws_search_transit_gateway_routes(
        region: str,
        transit_gateway_route_table_id: str,
        destination_cidr_block: str | None = None,
        route_search_type: str | None = None,
        max_results: int = DEFAULT_ROUTE_SEARCH_MAX_RESULTS,
    ) -> dict[str, Any]:
        """Search Transit Gateway routes.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            transit_gateway_route_table_id: The route table to search.
            destination_cidr_block: Optional exact-match destination CIDR.
            route_search_type: Optional route type filter: "static" or
                "propagated".
            max_results: Maximum routes to return (bounded fan-out cap).
        """
        return execute_tool(
            tool_name=_SEARCH_TGW_ROUTES,
            client_factory=client_factory,
            region=region,
            func=lambda: search_transit_gateway_routes(
                client_factory,
                region=region,
                transit_gateway_route_table_id=transit_gateway_route_table_id,
                destination_cidr_block=destination_cidr_block,
                route_search_type=route_search_type,
                max_results=max_results,
            ),
        )
