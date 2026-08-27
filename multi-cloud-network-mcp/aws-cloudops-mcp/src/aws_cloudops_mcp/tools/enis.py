"""MCP tool: aws_list_network_interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.enis import list_network_interfaces
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_network_interfaces"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List elastic network interfaces in a region, optionally "
            "filtered by VPC or subnet (ec2:DescribeNetworkInterfaces)."
        ),
        meta=capability_meta(resource_types=["network_interface"]),
    )
    def aws_list_network_interfaces(
        region: str,
        vpc_id: str | None = None,
        subnet_id: str | None = None,
        network_interface_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List elastic network interfaces (ENIs).

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            subnet_id: Optional subnet ID to restrict results to (ignored
                if ``vpc_id`` is also given).
            network_interface_ids: Optional list of ENI IDs (ignored if
                ``vpc_id`` or ``subnet_id`` is also given).
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_network_interfaces(
                client_factory,
                region=region,
                vpc_id=vpc_id,
                subnet_id=subnet_id,
                network_interface_ids=network_interface_ids,
            ),
        )
