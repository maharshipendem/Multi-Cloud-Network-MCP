"""MCP tool: gcp_get_caller_identity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.gcp.identity import get_caller_identity
from gcp_network_mcp.tools._shared import execute_tool
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.config import Settings

TOOL_NAME = "gcp_get_caller_identity"


def register(mcp: MCPServer, settings: Settings) -> None:
    @mcp.tool(
        name=TOOL_NAME,
        description=(
            "Return the current identity/context this server is authenticating "
            "with (credential type, resolved principal, ADC project, "
            "impersonation target) -- never a token, secret, or other "
            "credential material."
        ),
        meta=capability_meta(resource_types=["identity"]),
    )
    def gcp_get_caller_identity() -> dict[str, Any]:
        return execute_tool(
            tool_name=TOOL_NAME,
            project_id=None,
            func=lambda: get_caller_identity(settings),
        )
