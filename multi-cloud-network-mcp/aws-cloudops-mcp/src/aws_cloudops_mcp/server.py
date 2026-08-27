"""MCP server entrypoint and wiring.

This module owns MCP transport concerns only. It builds the shared
``ClientFactory``/``SessionManager`` once and hands them to each tool
module's ``register`` function -- AWS business logic itself lives in
``aws_cloudops_mcp.aws`` and ``aws_cloudops_mcp.tools``, never here.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.config import Settings, get_settings
from aws_cloudops_mcp.logging.setup import configure_logging, get_logger
from aws_cloudops_mcp.tools import (
    diagnostics,
    directconnect,
    dns,
    endpoints,
    enis,
    flowlogs,
    gateways,
    hybrid_topology,
    identity,
    inventory,
    loadbalancers,
    nacls,
    nat,
    network_insights,
    networkmanager,
    peering,
    prefix_lists,
    regions,
    security,
    topology,
    transit_gateway,
    vpn,
)

_logger = get_logger(__name__)


def build_server(settings: Settings | None = None) -> MCPServer:
    """Construct a fully wired MCPServer instance."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    session_manager = SessionManager(settings)
    client_factory = ClientFactory(settings, session_manager)

    mcp = MCPServer(settings.app_name)

    identity.register(mcp, client_factory)
    regions.register(mcp, client_factory)
    inventory.register(mcp, client_factory)
    gateways.register(mcp, client_factory)
    nat.register(mcp, client_factory)
    security.register(mcp, client_factory)
    nacls.register(mcp, client_factory)
    enis.register(mcp, client_factory)
    peering.register(mcp, client_factory)
    prefix_lists.register(mcp, client_factory)
    endpoints.register(mcp, client_factory)
    loadbalancers.register(mcp, client_factory)
    topology.register(mcp, client_factory)
    transit_gateway.register(mcp, client_factory)
    vpn.register(mcp, client_factory)
    directconnect.register(mcp, client_factory)
    dns.register(mcp, client_factory)
    networkmanager.register(mcp, client_factory)
    flowlogs.register(mcp, client_factory)
    hybrid_topology.register(mcp, client_factory)
    network_insights.register(mcp, client_factory)
    diagnostics.register(mcp, client_factory)

    _logger.info(
        "server initialized",
        extra={"tool_name": "server", "status": "ready"},
    )
    return mcp


def main() -> None:
    """Run the MCP server over stdio (the standard transport for local clients)."""
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
