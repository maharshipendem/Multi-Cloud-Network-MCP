"""MCP tools: aws_list_vpcs, aws_list_subnets, aws_list_route_tables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.networking import list_route_tables, list_subnets, list_vpcs
from aws_cloudops_mcp.tools._shared import execute_tool

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_VPCS = "aws_list_vpcs"
_LIST_SUBNETS = "aws_list_subnets"
_LIST_ROUTE_TABLES = "aws_list_route_tables"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_VPCS,
        description="List VPCs in a region (ec2:DescribeVpcs).",
    )
    def aws_list_vpcs(region: str) -> dict[str, Any]:
        """List VPCs.

        Args:
            region: AWS region to query, e.g. "us-east-1".
        """
        return execute_tool(
            tool_name=_LIST_VPCS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_vpcs(client_factory, region=region),
        )

    @mcp.tool(
        name=_LIST_SUBNETS,
        description="List subnets in a region, optionally filtered by VPC (ec2:DescribeSubnets).",
    )
    def aws_list_subnets(region: str, vpc_id: str | None = None) -> dict[str, Any]:
        """List subnets.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_SUBNETS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_subnets(client_factory, region=region, vpc_id=vpc_id),
        )

    @mcp.tool(
        name=_LIST_ROUTE_TABLES,
        description=(
            "List route tables in a region, optionally filtered by VPC "
            "(ec2:DescribeRouteTables), with normalized routes and associations."
        ),
    )
    def aws_list_route_tables(region: str, vpc_id: str | None = None) -> dict[str, Any]:
        """List route tables.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_ROUTE_TABLES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_route_tables(client_factory, region=region, vpc_id=vpc_id),
        )
