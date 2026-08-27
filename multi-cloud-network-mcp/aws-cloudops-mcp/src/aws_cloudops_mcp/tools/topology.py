"""MCP tool: aws_get_vpc_topology."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.topology import get_vpc_topology
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_get_vpc_topology"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Join VPC networking resources (subnets, route tables, "
            "gateways, NAT gateways, security groups, NACLs, ENIs, peering, "
            "VPC endpoints, load balancers) into one node/edge topology "
            "graph for a single VPC. Every edge states its relationship "
            "type and the specific API evidence it was derived from. "
            "Deterministically sorted; partial-collection warnings and the "
            "AWS API call count are included."
        ),
        meta=capability_meta(resource_types=["vpc_topology"]),
    )
    def aws_get_vpc_topology(region: str, vpc_id: str) -> dict[str, Any]:
        """Assemble a VPC's networking topology graph.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: The VPC to build the topology graph for.
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: get_vpc_topology(client_factory, region=region, vpc_id=vpc_id),
        )
