"""MCP tool: aws_list_network_acls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.nacls import list_network_acls
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_network_acls"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List network ACLs in a region, optionally filtered by VPC "
            "(ec2:DescribeNetworkAcls), with entries normalized by "
            "direction/rule number/action/protocol/ports/CIDR."
        ),
        meta=capability_meta(resource_types=["network_acl"]),
    )
    def aws_list_network_acls(
        region: str, vpc_id: str | None = None, network_acl_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List network ACLs.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            network_acl_ids: Optional list of network ACL IDs (ignored if
                ``vpc_id`` is also given).
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_acls(
                client_factory, region=region, vpc_id=vpc_id, network_acl_ids=network_acl_ids
            ),
        )
