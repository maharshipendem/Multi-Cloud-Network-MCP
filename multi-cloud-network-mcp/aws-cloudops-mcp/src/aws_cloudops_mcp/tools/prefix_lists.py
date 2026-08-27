"""MCP tool: aws_list_managed_prefix_lists."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.prefix_lists import list_managed_prefix_lists
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_list_managed_prefix_lists"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "List customer-managed prefix lists in a region "
            "(ec2:DescribeManagedPrefixLists), optionally including each "
            "list's CIDR entries (ec2:GetManagedPrefixListEntries)."
        ),
        meta=capability_meta(resource_types=["managed_prefix_list"]),
    )
    def aws_list_managed_prefix_lists(
        region: str,
        include_entries: bool = False,
        prefix_list_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List managed prefix lists.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            include_entries: If true, also fetch each prefix list's CIDR
                entries (1 extra API call per prefix list, bounded and
                best-effort -- see warnings in the response metadata if any
                fetch fails or the fan-out cap is reached).
            prefix_list_ids: Optional list of prefix list IDs to restrict
                results to.
        """
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: list_managed_prefix_lists(
                client_factory,
                region=region,
                include_entries=include_entries,
                prefix_list_ids=prefix_list_ids,
            ),
        )
