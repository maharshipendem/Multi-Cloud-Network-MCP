"""MCP tool: aws_list_vpc_peering_connections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.peering import list_vpc_peering_connections
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_vpc_peering_connections"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List VPC peering connections in a region, optionally filtered "
            "by VPC on either the requester or accepter side "
            "(ec2:DescribeVpcPeeringConnections)."
        ),
        meta=capability_meta(resource_types=["vpc_peering_connection"]),
    )
    def aws_list_vpc_peering_connections(
        region: str,
        vpc_id: str | None = None,
        vpc_peering_connection_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List VPC peering connections.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to (matches either
                the requester or accepter side).
            vpc_peering_connection_ids: Optional list of peering connection
                IDs (ignored if ``vpc_id`` is also given).
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_vpc_peering_connections(
                client_factory,
                region=region,
                vpc_id=vpc_id,
                vpc_peering_connection_ids=vpc_peering_connection_ids,
            ),
        )
