"""MCP tool: azure_get_caller_identity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.identity import get_caller_identity
from azure_network_mcp.tools._shared import execute_tool
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

TOOL_NAME = "azure_get_caller_identity"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Return the current identity/context this server is "
            "authenticating with (credential type, configured tenant, "
            "default subscription) -- never a token, secret, or other "
            "credential material."
        ),
        meta=capability_meta(resource_types=["identity"]),
    )
    def azure_get_caller_identity() -> dict[str, Any]:
        return execute_tool(
            tool_name=TOOL_NAME,
            subscription_id=None,
            func=lambda: get_caller_identity(client_factory),
        )
