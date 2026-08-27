"""MCP tools: aws_list_vpcs, aws_list_subnets, aws_list_route_tables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.networking import list_route_tables, list_subnets, list_vpcs
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_VPCS = "aws_list_vpcs"
_LIST_SUBNETS = "aws_list_subnets"
_LIST_ROUTE_TABLES = "aws_list_route_tables"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_VPCS,
        description=(
            "List VPCs in a region (ec2:DescribeVpcs), including CIDR "
            "associations, tenancy, and (opt-in) DNS attributes."
        ),
        meta=capability_meta(resource_types=["vpc"]),
    )
    def aws_list_vpcs(
        region: str,
        vpc_ids: list[str] | None = None,
        include_dns_attributes: bool = False,
    ) -> dict[str, Any]:
        """List VPCs.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_ids: Optional list of VPC IDs to restrict results to.
            include_dns_attributes: If true, also fetch each VPC's
                enableDnsSupport/enableDnsHostnames attributes (2 extra API
                calls per VPC, bounded and best-effort -- see warnings in
                the response metadata if any VPC's enrichment fails).
        """
        return execute_tool(
            tool_name=_LIST_VPCS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_vpcs(
                client_factory,
                region=region,
                vpc_ids=vpc_ids,
                include_dns_attributes=include_dns_attributes,
            ),
        )

    @mcp.tool(
        name=_LIST_SUBNETS,
        description="List subnets in a region, optionally filtered by VPC (ec2:DescribeSubnets).",
        meta=capability_meta(resource_types=["subnet"]),
    )
    def aws_list_subnets(
        region: str, vpc_id: str | None = None, subnet_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List subnets.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            subnet_ids: Optional list of subnet IDs to restrict results to
                (ignored if ``vpc_id`` is also given).
        """
        return execute_tool(
            tool_name=_LIST_SUBNETS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_subnets(
                client_factory, region=region, vpc_id=vpc_id, subnet_ids=subnet_ids
            ),
        )

    @mcp.tool(
        name=_LIST_ROUTE_TABLES,
        description=(
            "List route tables in a region, optionally filtered by VPC "
            "(ec2:DescribeRouteTables), with normalized routes and associations."
        ),
        meta=capability_meta(resource_types=["route_table"]),
    )
    def aws_list_route_tables(
        region: str, vpc_id: str | None = None, route_table_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List route tables.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            route_table_ids: Optional list of route table IDs to restrict
                results to (ignored if ``vpc_id`` is also given).
        """
        return execute_tool(
            tool_name=_LIST_ROUTE_TABLES,
            client_factory=client_factory,
            region=region,
            func=lambda: list_route_tables(
                client_factory, region=region, vpc_id=vpc_id, route_table_ids=route_table_ids
            ),
        )
