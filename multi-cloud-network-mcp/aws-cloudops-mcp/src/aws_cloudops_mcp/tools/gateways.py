"""MCP tools: aws_list_internet_gateways, aws_list_egress_only_internet_gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.gateways import (
    list_egress_only_internet_gateways,
    list_internet_gateways,
)
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

_LIST_INTERNET_GATEWAYS = "aws_list_internet_gateways"
_LIST_EGRESS_ONLY_INTERNET_GATEWAYS = "aws_list_egress_only_internet_gateways"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_LIST_INTERNET_GATEWAYS,
        description=(
            "List internet gateways in a region, optionally filtered by "
            "attached VPC (ec2:DescribeInternetGateways)."
        ),
        meta=capability_meta(resource_types=["internet_gateway"]),
    )
    def aws_list_internet_gateways(
        region: str,
        vpc_id: str | None = None,
        internet_gateway_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List internet gateways.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: Optional VPC ID to restrict results to gateways attached
                to that VPC.
            internet_gateway_ids: Optional list of internet gateway IDs
                (ignored if ``vpc_id`` is also given).
        """
        return execute_tool(
            tool_name=_LIST_INTERNET_GATEWAYS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_internet_gateways(
                client_factory,
                region=region,
                vpc_id=vpc_id,
                internet_gateway_ids=internet_gateway_ids,
            ),
        )

    @mcp.tool(
        name=_LIST_EGRESS_ONLY_INTERNET_GATEWAYS,
        description=(
            "List egress-only internet gateways in a region "
            "(ec2:DescribeEgressOnlyInternetGateways)."
        ),
        meta=capability_meta(resource_types=["egress_only_internet_gateway"]),
    )
    def aws_list_egress_only_internet_gateways(
        region: str, egress_only_internet_gateway_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """List egress-only internet gateways.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            egress_only_internet_gateway_ids: Optional list of egress-only
                internet gateway IDs to restrict results to.
        """
        return execute_tool(
            tool_name=_LIST_EGRESS_ONLY_INTERNET_GATEWAYS,
            client_factory=client_factory,
            region=region,
            func=lambda: list_egress_only_internet_gateways(
                client_factory,
                region=region,
                egress_only_internet_gateway_ids=egress_only_internet_gateway_ids,
            ),
        )
