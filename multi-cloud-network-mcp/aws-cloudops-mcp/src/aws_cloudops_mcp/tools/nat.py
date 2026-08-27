"""MCP tool: aws_list_nat_gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.nat import list_nat_gateways
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_nat_gateways"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List NAT gateways in a region, optionally filtered by VPC or "
            "subnet (ec2:DescribeNatGateways). Includes recently deleted "
            "gateways (state='deleted')."
        ),
        meta=capability_meta(resource_types=["nat_gateway"]),
    )
    def aws_list_nat_gateways(
        region: str,
        vpc_id: str | None = None,
        subnet_id: str | None = None,
        nat_gateway_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List NAT gateways.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to.
            subnet_id: Optional subnet ID to restrict results to.
            nat_gateway_ids: Optional list of NAT gateway IDs.
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_nat_gateways(
                client_factory,
                region=region,
                vpc_id=vpc_id,
                subnet_id=subnet_id,
                nat_gateway_ids=nat_gateway_ids,
            ),
        )
