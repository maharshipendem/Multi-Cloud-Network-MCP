"""MCP server entrypoint and wiring.

This module owns MCP transport concerns only. It builds the shared
``ClientFactory``/``ResourceContext`` once and hands them to each tool
module's ``register`` function -- GCP business logic itself lives in
``gcp_network_mcp.gcp`` and ``gcp_network_mcp.tools``, never here.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from gcp_network_mcp.auth.session import ResourceContext
from gcp_network_mcp.config import Settings, get_settings
from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.logging.setup import configure_logging, get_logger
from gcp_network_mcp.tools import (
    addresses,
    bgp,
    connectivity_center,
    connectivity_tests,
    contracts,
    diagnostics,
    dns,
    firewall,
    flow_logs,
    identity,
    instances,
    interconnect,
    load_balancing,
    nat,
    networking,
    observability,
    packet_mirroring,
    peering,
    private_service_access,
    private_service_connect,
    projects,
    routes,
    shared_vpc,
    topology,
    vpn,
)

_logger = get_logger(__name__)


def build_server(settings: Settings | None = None) -> MCPServer:
    """Construct a fully wired MCPServer instance."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    resource_context = ResourceContext(settings)
    client_factory = ClientFactory(settings, resource_context)

    mcp = MCPServer(settings.app_name)

    identity.register(mcp, settings)
    projects.register(mcp, client_factory)
    networking.register(mcp, client_factory, resource_context)
    routes.register(mcp, client_factory, resource_context)
    firewall.register(mcp, client_factory, resource_context)
    instances.register(mcp, client_factory, resource_context)
    addresses.register(mcp, client_factory, resource_context)
    load_balancing.register(mcp, client_factory, resource_context)
    nat.register(mcp, client_factory, resource_context)
    peering.register(mcp, client_factory, resource_context)
    shared_vpc.register(mcp, client_factory, resource_context)
    topology.register(mcp, client_factory, resource_context)

    # Milestone 8: advanced transit/hybrid networking, DNS, observability, diagnostics.
    bgp.register(mcp, client_factory, resource_context)
    connectivity_center.register(mcp, client_factory, resource_context)
    vpn.register(mcp, client_factory, resource_context)
    interconnect.register(mcp, client_factory, resource_context)
    private_service_connect.register(mcp, client_factory, resource_context)
    private_service_access.register(mcp, client_factory, resource_context)
    dns.register(mcp, client_factory, resource_context)
    packet_mirroring.register(mcp, client_factory, resource_context)
    flow_logs.register(mcp, client_factory, resource_context)
    connectivity_tests.register(mcp, client_factory, resource_context)
    observability.register(mcp, client_factory, resource_context, settings)
    diagnostics.register(mcp, client_factory, resource_context, settings)

    # Milestone 9: multicloud-network-mcp contract adapter surface (no
    # runtime dependency on that package -- see tools/contracts.py).
    contracts.register(mcp, client_factory, resource_context)

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
