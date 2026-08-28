"""CONSIST-001 (degraded/failed resource and connection state) and
CONSIST-002 (blackhole/orphaned user-defined routes) -- whole-snapshot
consistency checks."""

from __future__ import annotations

from azure_network_mcp.diagnostics.models import Evidence, Finding, register_rule
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot

RULE_ID_STATE = "CONSIST-001"
register_rule(
    rule_id=RULE_ID_STATE,
    version="1.0.0",
    title="Degraded or failed resource/connection state",
    description=(
        "Flags a resource with a non-Succeeded provisioning state, or a VPN/"
        "ExpressRoute connection that isn't Connected."
    ),
    default_severity="high",
)

RULE_ID_ROUTE = "CONSIST-002"
register_rule(
    rule_id=RULE_ID_ROUTE,
    version="1.0.0",
    title="Blackhole or orphaned user-defined route",
    description=(
        "Flags a user-defined route with next_hop_type='None' (a deliberate "
        "drop), or a VirtualAppliance route whose next hop IP matches no known "
        "NIC in this snapshot."
    ),
    default_severity="medium",
)

_UNHEALTHY_CONNECTION_STATUSES = {"Disconnected", "NotConnected", "Degraded", "Unknown"}


def find_degraded_resources(snapshot: HybridNetworkSnapshot) -> list[Finding]:
    findings: list[Finding] = []

    resources_with_state = (
        [
            (v.resource_id, v.name, "virtual_network", v.provisioning_state)
            for v in snapshot.virtual_networks
        ]
        + [
            (n.resource_id, n.name, "network_security_group", n.provisioning_state)
            for n in snapshot.network_security_groups
        ]
        + [
            (r.resource_id, r.name, "route_table", r.provisioning_state)
            for r in snapshot.route_tables
        ]
        + [
            (g.resource_id, g.name, "vpn_gateway", g.provisioning_state)
            for g in snapshot.vpn_gateways
        ]
        + [
            (g.resource_id, g.name, "virtual_network_gateway", g.provisioning_state)
            for g in snapshot.virtual_network_gateways
        ]
        + [
            (c.resource_id, c.name, "express_route_circuit", c.provisioning_state)
            for c in snapshot.express_route_circuits
        ]
        + [
            (g.resource_id, g.name, "express_route_gateway", g.provisioning_state)
            for g in snapshot.express_route_gateways
        ]
    )
    for resource_id, name, resource_type, state in resources_with_state:
        if state and state != "Succeeded":
            findings.append(
                Finding(
                    rule_id=RULE_ID_STATE,
                    rule_version="1.0.0",
                    severity="high",
                    confidence="high",
                    summary=(
                        f"{resource_type} {name} has provisioning_state='{state}', not 'Succeeded'."
                    ),
                    affected_resources=[resource_id],
                    evidence=[
                        Evidence(
                            source=f"{resource_type}:{name}", detail=f"provisioning_state={state}"
                        )
                    ],
                    freshness=snapshot.observed_at,
                    remediation=(
                        "Investigate the deployment or update operation that left this "
                        "resource in this state."
                    ),
                )
            )

    connections = [
        (c.resource_id, c.name, "vpn_connection", c.connection_status)
        for c in snapshot.vpn_connections
    ] + [
        (c.resource_id, c.name, "virtual_network_gateway_connection", c.connection_status)
        for c in snapshot.virtual_network_gateway_connections
    ]
    for resource_id, name, resource_type, status in connections:
        if status in _UNHEALTHY_CONNECTION_STATUSES:
            findings.append(
                Finding(
                    rule_id=RULE_ID_STATE,
                    rule_version="1.0.0",
                    severity="high",
                    confidence="high",
                    summary=f"{resource_type} {name} has connection_status='{status}'.",
                    affected_resources=[resource_id],
                    evidence=[
                        Evidence(
                            source=f"{resource_type}:{name}", detail=f"connection_status={status}"
                        )
                    ],
                    freshness=snapshot.observed_at,
                    remediation=(
                        "Check the on-premises/peer side of this connection and its BGP/IKE state."
                    ),
                )
            )

    return findings


def find_blackhole_routes(snapshot: HybridNetworkSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    known_nic_ips = {
        ipc.private_ip_address
        for nic in snapshot.network_interfaces
        for ipc in nic.ip_configurations
        if ipc.private_ip_address
    }

    for rt in snapshot.route_tables:
        for route in rt.routes:
            if route.next_hop_type == "None":
                findings.append(
                    Finding(
                        rule_id=RULE_ID_ROUTE,
                        rule_version="1.0.0",
                        severity="medium",
                        confidence="high",
                        summary=(
                            f"Route table {rt.name} has a blackhole route "
                            f"'{route.name}' ({route.address_prefix}) with "
                            "next_hop_type='None'."
                        ),
                        affected_resources=[rt.resource_id],
                        evidence=[
                            Evidence(
                                source=f"route:{route.name}@{rt.name}",
                                detail=f"address_prefix={route.address_prefix}, next_hop_type=None",
                            )
                        ],
                        freshness=snapshot.observed_at,
                        remediation=(
                            "If this is not a deliberate drop route, update or remove it "
                            f"from route table {rt.name}."
                        ),
                    )
                )
            elif (
                route.next_hop_type == "VirtualAppliance"
                and route.next_hop_ip_address
                and route.next_hop_ip_address not in known_nic_ips
            ):
                findings.append(
                    Finding(
                        rule_id=RULE_ID_ROUTE,
                        rule_version="1.0.0",
                        severity="medium",
                        confidence="indeterminate",
                        summary=(
                            f"Route table {rt.name}'s route '{route.name}' points to "
                            f"VirtualAppliance {route.next_hop_ip_address}, which matches no "
                            "network interface in this resource group's snapshot."
                        ),
                        affected_resources=[rt.resource_id],
                        evidence=[
                            Evidence(
                                source=f"route:{route.name}@{rt.name}",
                                detail=(
                                    "next_hop_type=VirtualAppliance, "
                                    f"next_hop_ip_address={route.next_hop_ip_address}"
                                ),
                            )
                        ],
                        freshness=snapshot.observed_at,
                        limitations=[
                            "The appliance may legitimately live in a different resource "
                            "group or subscription outside this snapshot's scope -- this "
                            "is not proof the route is broken."
                        ],
                    )
                )

    return findings


__all__ = [
    "RULE_ID_ROUTE",
    "RULE_ID_STATE",
    "find_blackhole_routes",
    "find_degraded_resources",
]
