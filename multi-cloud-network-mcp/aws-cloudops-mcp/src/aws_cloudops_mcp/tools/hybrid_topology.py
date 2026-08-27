"""MCP tool: aws_get_hybrid_topology."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.hybrid_topology import get_hybrid_topology
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_get_hybrid_topology"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Join VPC, VPN, Direct Connect, and DNS resources attached to "
            "one Transit Gateway into a typed node/edge topology graph. "
            "Genuinely external (non-AWS) endpoints -- e.g. a customer "
            "gateway's on-premises IP -- are labeled with an "
            "'external_endpoint' node rather than left implicit. Does not "
            "claim or imply traffic reachability -- this is a connectivity "
            "map, not a reachability analysis."
        ),
        meta=capability_meta(resource_types=["hybrid_topology"]),
    )
    def aws_get_hybrid_topology(region: str, transit_gateway_id: str) -> dict[str, Any]:
        """Assemble a Transit Gateway's hybrid connectivity topology graph.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            transit_gateway_id: The Transit Gateway to build the topology
                graph for.
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: get_hybrid_topology(
                client_factory, region=region, transit_gateway_id=transit_gateway_id
            ),
        )
