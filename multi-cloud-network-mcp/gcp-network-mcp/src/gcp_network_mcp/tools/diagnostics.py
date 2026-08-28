"""MCP tools: gcp_get_hybrid_topology, gcp_explain_network_path,
gcp_find_network_risks, gcp_get_network_health -- the deterministic
diagnostics engine's tool surface. Every tool collects a fresh
``HybridNetworkSnapshot`` for the resolved project (optionally scoped by
``hierarchical_firewall_parent_id`` for org/folder Firewall Policy
visibility) and runs the relevant pure-function analysis over it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gcp_network_mcp.diagnostics.explain import explain_network_path
from gcp_network_mcp.diagnostics.health import get_network_health
from gcp_network_mcp.diagnostics.hybrid_topology import build_hybrid_topology
from gcp_network_mcp.diagnostics.risks import find_network_risks
from gcp_network_mcp.diagnostics.snapshot import collect_hybrid_snapshot
from gcp_network_mcp.tools._shared import execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.config import Settings
    from gcp_network_mcp.gcp.client_factory import ClientFactory

_GET_HYBRID_TOPOLOGY = "gcp_get_hybrid_topology"
_EXPLAIN_NETWORK_PATH = "gcp_explain_network_path"
_FIND_NETWORK_RISKS = "gcp_find_network_risks"
_GET_NETWORK_HEALTH = "gcp_get_network_health"


def register(
    mcp: MCPServer,
    client_factory: ClientFactory,
    resource_context: ResourceContext,
    settings: Settings,
) -> None:
    @mcp.tool(
        name=_GET_HYBRID_TOPOLOGY,
        description=(
            "Return a deterministic, typed node/edge graph of one project's hybrid "
            "networking -- networks, subnetworks, Cloud Routers, VPN gateways/tunnels, "
            "Interconnect attachments, and NCC hubs/spokes. A reference this server "
            "couldn't resolve still produces an edge plus a warning, never a silent drop; "
            "completeness is 'partial' whenever any warning was recorded."
        ),
        meta=capability_meta(resource_types=["topology"]),
    )
    def gcp_get_hybrid_topology(
        project_id: str | None = None, hierarchical_firewall_parent_id: str | None = None
    ) -> dict[str, Any]:
        """Get the hybrid topology graph for one project.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
            hierarchical_firewall_parent_id: Optional organization/folder ID to also
                collect hierarchical Firewall Policies for.
        """

        def _run(resolved: str) -> Any:
            snapshot = collect_hybrid_snapshot(
                client_factory,
                project_id=resolved,
                hierarchical_firewall_parent_id=hierarchical_firewall_parent_id,
                max_fanout=settings.max_diagnostics_fanout,
            )
            return build_hybrid_topology(snapshot)

        return execute_tool_with_resolved_project(
            tool_name=_GET_HYBRID_TOPOLOGY,
            resource_context=resource_context,
            project_id=project_id,
            func=_run,
        )

    @mcp.tool(
        name=_EXPLAIN_NETWORK_PATH,
        description=(
            "Deterministically evaluate route resolution and firewall rules (network-level "
            "plus hierarchical policy interaction) for one network toward one destination "
            "IP/port/protocol. overall_verdict is 'allowed' only when every layer "
            "independently concluded so; 'blocked' if any did; 'partially_evaluated' if any "
            "layer's evidence was incomplete."
        ),
        meta=capability_meta(resource_types=["route", "firewall_rule"]),
    )
    def gcp_explain_network_path(
        network_self_link: str,
        destination_ip: str,
        protocol: str = "tcp",
        destination_port: int | None = None,
        project_id: str | None = None,
        hierarchical_firewall_parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Explain a network path.

        Args:
            network_self_link: Full self-link of the source network.
            destination_ip: Destination IP address.
            protocol: IP protocol (default "tcp").
            destination_port: Optional destination port.
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
            hierarchical_firewall_parent_id: Optional organization/folder ID to also
                collect hierarchical Firewall Policies for.
        """

        def _run(resolved: str) -> Any:
            snapshot = collect_hybrid_snapshot(
                client_factory,
                project_id=resolved,
                hierarchical_firewall_parent_id=hierarchical_firewall_parent_id,
                max_fanout=settings.max_diagnostics_fanout,
            )
            return explain_network_path(
                snapshot,
                network_self_link=network_self_link,
                destination_ip=destination_ip,
                destination_port=destination_port,
                protocol=protocol,
            )

        return execute_tool_with_resolved_project(
            tool_name=_EXPLAIN_NETWORK_PATH,
            resource_context=resource_context,
            project_id=project_id,
            func=_run,
        )

    @mcp.tool(
        name=_FIND_NETWORK_RISKS,
        description=(
            "Run every deterministic diagnostic rule (routing, peering, NCC propagation, "
            "firewall, Cloud NAT, public exposure, VPN/BGP/Interconnect health, DNS) against "
            "one project and return every finding, including confidence='indeterminate' "
            "findings -- never silently filtered out."
        ),
        meta=capability_meta(resource_types=["finding"]),
    )
    def gcp_find_network_risks(
        project_id: str | None = None, hierarchical_firewall_parent_id: str | None = None
    ) -> dict[str, Any]:
        """Find network risks across one project.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
            hierarchical_firewall_parent_id: Optional organization/folder ID to also
                collect hierarchical Firewall Policies for.
        """

        def _run(resolved: str) -> Any:
            snapshot = collect_hybrid_snapshot(
                client_factory,
                project_id=resolved,
                hierarchical_firewall_parent_id=hierarchical_firewall_parent_id,
                max_fanout=settings.max_diagnostics_fanout,
            )
            return find_network_risks(snapshot)

        return execute_tool_with_resolved_project(
            tool_name=_FIND_NETWORK_RISKS,
            resource_context=resource_context,
            project_id=project_id,
            func=_run,
        )

    @mcp.tool(
        name=_GET_NETWORK_HEALTH,
        description=(
            "Summarize one project's network health: finding counts by severity, a resource "
            "inventory count, and every underlying finding."
        ),
        meta=capability_meta(resource_types=["health"]),
    )
    def gcp_get_network_health(
        project_id: str | None = None, hierarchical_firewall_parent_id: str | None = None
    ) -> dict[str, Any]:
        """Get a project's network health report.

        Args:
            project_id: Project to query. Falls back to GCP_DEFAULT_PROJECT_ID if omitted.
            hierarchical_firewall_parent_id: Optional organization/folder ID to also
                collect hierarchical Firewall Policies for.
        """

        def _run(resolved: str) -> Any:
            snapshot = collect_hybrid_snapshot(
                client_factory,
                project_id=resolved,
                hierarchical_firewall_parent_id=hierarchical_firewall_parent_id,
                max_fanout=settings.max_diagnostics_fanout,
            )
            return get_network_health(snapshot)

        return execute_tool_with_resolved_project(
            tool_name=_GET_NETWORK_HEALTH,
            resource_context=resource_context,
            project_id=project_id,
            func=_run,
        )
