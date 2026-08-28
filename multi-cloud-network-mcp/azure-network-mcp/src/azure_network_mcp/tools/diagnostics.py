"""MCP tools: azure_get_hybrid_topology, azure_explain_network_path,
azure_find_network_risks, azure_get_network_health -- the deterministic
diagnostics engine's four tools.

Every finding is deterministic Python logic evaluated against an
already-collected snapshot, never an LLM judgment call. ``remediation``
text on a ``Finding`` is always advisory -- nothing in this module (or
anywhere in this repository) executes it. See
docs/security.md#deterministic-evidence-bound-diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.diagnostics.explain import explain_network_path
from azure_network_mcp.diagnostics.health import get_network_health
from azure_network_mcp.diagnostics.hybrid_topology import build_hybrid_topology
from azure_network_mcp.diagnostics.risks import find_network_risks
from azure_network_mcp.diagnostics.snapshot import collect_hybrid_snapshot
from azure_network_mcp.tools._shared import execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

_GET_HYBRID_TOPOLOGY = "azure_get_hybrid_topology"
_EXPLAIN_NETWORK_PATH = "azure_explain_network_path"
_FIND_NETWORK_RISKS = "azure_find_network_risks"
_GET_NETWORK_HEALTH = "azure_get_network_health"


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=_GET_HYBRID_TOPOLOGY,
        description=(
            "Build a deterministic hybrid-connectivity topology graph for one "
            "resource group: VNets, Virtual Hubs (including standalone Route "
            "Servers), VPN gateways/connections, and ExpressRoute circuits/"
            "gateways/connections, with evidence on every edge and a "
            "completeness warning for anything outside the resource group."
        ),
        meta=capability_meta(resource_types=["hybrid_topology"]),
    )
    def azure_get_hybrid_topology(
        resource_group: str, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """Get a resource group's hybrid topology graph.

        Args:
            resource_group: Resource group to build the topology for.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """

        def _run(resolved: str) -> Any:
            snapshot = collect_hybrid_snapshot(
                client_factory, subscription_id=resolved, resource_group=resource_group
            )
            return build_hybrid_topology(snapshot)

        return execute_tool_with_resolved_subscription(
            tool_name=_GET_HYBRID_TOPOLOGY,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=_run,
        )

    @mcp.tool(
        name=_EXPLAIN_NETWORK_PATH,
        description=(
            "Explain whether a source network interface can reach a destination "
            "IP/port/protocol, by evaluating Azure's own effective route table "
            "and effective NSG rules for that NIC. Returns route_verdict, "
            "security_verdict, and overall_verdict (allowed/blocked/"
            "partially_evaluated -- never silently upgraded to allowed when "
            "evidence is incomplete), each backed by a deterministic Finding "
            "with evidence and reasoning."
        ),
        meta=capability_meta(resource_types=["network_interface"]),
    )
    def azure_explain_network_path(
        resource_group: str,
        network_interface_name: str,
        destination_ip: str,
        destination_port: int,
        protocol: str = "Tcp",
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Explain a network path from one NIC to a destination.

        Args:
            resource_group: Resource group containing the source NIC.
            network_interface_name: Name of the source network interface.
            destination_ip: Destination IP address to evaluate reachability to.
            destination_port: Destination port.
            protocol: "Tcp" or "Udp" (default "Tcp").
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """

        def _run(resolved: str) -> Any:
            return explain_network_path(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                network_interface_name=network_interface_name,
                destination_ip=destination_ip,
                destination_port=destination_port,
                protocol=protocol,
            )

        return execute_tool_with_resolved_subscription(
            tool_name=_EXPLAIN_NETWORK_PATH,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=_run,
        )

    @mcp.tool(
        name=_FIND_NETWORK_RISKS,
        description=(
            "Scan one resource group for network risks: internet-exposed "
            "network interfaces, degraded/failed resource or connection "
            "state, and blackhole/orphaned user-defined routes. Each risk is "
            "a deterministic Finding with severity, confidence, evidence, "
            "and advisory (never executed) remediation."
        ),
        meta=capability_meta(resource_types=["hybrid_topology"]),
    )
    def azure_find_network_risks(
        resource_group: str,
        min_severity: str = "info",
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Scan a resource group for network risks.

        Args:
            resource_group: Resource group to scan.
            min_severity: Minimum severity to include: one of "info", "low",
                "medium", "high", "critical" (default "info").
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """

        def _run(resolved: str) -> Any:
            snapshot = collect_hybrid_snapshot(
                client_factory, subscription_id=resolved, resource_group=resource_group
            )
            return find_network_risks(snapshot, min_severity=min_severity)

        return execute_tool_with_resolved_subscription(
            tool_name=_FIND_NETWORK_RISKS,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=_run,
        )

    @mcp.tool(
        name=_GET_NETWORK_HEALTH,
        description=(
            "Report network health for one resource group: degraded/failed "
            "resources, unhealthy VPN/ExpressRoute connections, and "
            "(opt-in, bounded to a fixed metric catalog and 24-hour lookback) "
            "Azure Monitor metrics for the resource group's gateways/circuits."
        ),
        meta=capability_meta(resource_types=["hybrid_topology"]),
    )
    def azure_get_network_health(
        resource_group: str,
        include_metrics: bool = False,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Get a resource group's network health report.

        Args:
            resource_group: Resource group to report on.
            include_metrics: If true, also query bounded Azure Monitor
                metrics for the resource group's gateways/circuits (opt-in,
                since it adds extra API calls).
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """

        def _run(resolved: str) -> Any:
            snapshot = collect_hybrid_snapshot(
                client_factory, subscription_id=resolved, resource_group=resource_group
            )
            return get_network_health(
                snapshot, client_factory=client_factory, include_metrics=include_metrics
            )

        return execute_tool_with_resolved_subscription(
            tool_name=_GET_NETWORK_HEALTH,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=_run,
        )
