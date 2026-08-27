"""MCP tool: aws_get_caller_identity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.accounts import get_caller_identity
from aws_cloudops_mcp.tools._shared import execute_tool

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

TOOL_NAME = "aws_get_caller_identity"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Return the AWS identity currently used by the MCP server "
            "(sts:GetCallerIdentity): account_id, arn, and user_id."
        ),
    )
    def aws_get_caller_identity() -> dict[str, Any]:
        return execute_tool(
            tool_name=TOOL_NAME,
            client_factory=client_factory,
            region=None,
            func=lambda: get_caller_identity(client_factory),
        )
