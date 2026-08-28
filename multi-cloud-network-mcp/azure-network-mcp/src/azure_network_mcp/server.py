"""MCP server entrypoint and wiring.

This module owns MCP transport concerns only. It builds the shared
``ClientFactory``/``SubscriptionContext`` once and hands them to each tool
module's ``register`` function -- Azure business logic itself lives in
``azure_network_mcp.arm`` and ``azure_network_mcp.tools``, never here.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.auth.session import SubscriptionContext
from azure_network_mcp.config import Settings, get_settings
from azure_network_mcp.logging.setup import configure_logging, get_logger
from azure_network_mcp.tools import (
    diagnostics,
    expressroute,
    firewall,
    identity,
    load_balancers,
    monitor,
    nat_gateways,
    network_interfaces,
    network_security_groups,
    network_watcher,
    networking,
    peerings,
    private_dns,
    private_link,
    public_ips,
    resource_groups,
    route_server,
    route_tables,
    subscriptions,
    topology,
    virtual_wan,
    vpn,
)

_logger = get_logger(__name__)


def build_server(settings: Settings | None = None) -> MCPServer:
    """Construct a fully wired MCPServer instance."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    subscription_context = SubscriptionContext(settings)
    client_factory = ClientFactory(settings, subscription_context)

    mcp = MCPServer(settings.app_name)

    identity.register(mcp, client_factory)
    subscriptions.register(mcp, client_factory)
    resource_groups.register(mcp, client_factory)
    networking.register(mcp, client_factory)
    route_tables.register(mcp, client_factory)
    network_security_groups.register(mcp, client_factory)
    network_interfaces.register(mcp, client_factory)
    public_ips.register(mcp, client_factory)
    peerings.register(mcp, client_factory)
    nat_gateways.register(mcp, client_factory)
    load_balancers.register(mcp, client_factory)
    topology.register(mcp, client_factory)
    virtual_wan.register(mcp, client_factory)
    route_server.register(mcp, client_factory)
    vpn.register(mcp, client_factory)
    expressroute.register(mcp, client_factory)
    private_link.register(mcp, client_factory)
    private_dns.register(mcp, client_factory)
    firewall.register(mcp, client_factory)
    network_watcher.register(mcp, client_factory)
    monitor.register(mcp, client_factory)
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
