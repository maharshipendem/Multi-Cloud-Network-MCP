"""MCP tool: aws_list_regions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.regions import list_regions
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_regions"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description="Return AWS regions accessible through EC2 DescribeRegions.",
        meta=capability_meta(resource_types=["region"]),
    )
    def aws_list_regions(region: str | None = None) -> dict[str, Any]:
        """List AWS regions.

        Args:
            region: Region whose EC2 endpoint issues the call. Defaults to
                the server's configured default region. DescribeRegions
                results are the same regardless of which region is queried.
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_regions(client_factory, region=region),
        )
