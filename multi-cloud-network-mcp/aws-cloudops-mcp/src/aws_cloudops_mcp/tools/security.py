"""MCP tool: aws_list_security_groups."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.security import list_security_groups
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_security_groups"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List security groups in a region, optionally filtered by VPC "
            "(ec2:DescribeSecurityGroups), each with its rules normalized by "
            "direction/protocol/ports/peer/rule ID (ec2:DescribeSecurityGroupRules)."
        ),
        meta=capability_meta(resource_types=["security_group", "security_group_rule"]),
    )
    def aws_list_security_groups(
        region: str,
        vpc_id: str | None = None,
        security_group_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List security groups and their rules.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            security_group_ids: Optional list of security group IDs
                (ignored if ``vpc_id`` is also given).
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_security_groups(
                client_factory,
                region=region,
                vpc_id=vpc_id,
                security_group_ids=security_group_ids,
            ),
        )
