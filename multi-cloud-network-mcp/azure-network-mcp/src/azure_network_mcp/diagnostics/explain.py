"""``azure_explain_network_path``'s orchestration: collects one source
NIC's effective route table and effective NSG rules, then runs ROUTE-001
and SEC-001 against one destination IP/port/protocol.

This is the one diagnostics function that reaches past
``HybridNetworkSnapshot`` into a second, targeted ARM seam
(``diagnostics.snapshot.collect_nic_effective_state``) -- explained in
that function's own docstring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.diagnostics.models import Finding
from azure_network_mcp.diagnostics.routing import evaluate_route
from azure_network_mcp.diagnostics.security import evaluate_security_rules
from azure_network_mcp.diagnostics.snapshot import collect_nic_effective_state

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


class NetworkPathExplanation(BaseModel):
    source_nic_id: str
    destination_ip: str
    destination_port: int
    protocol: str
    route_verdict: str
    security_verdict: str
    overall_verdict: str
    findings: list[Finding]


def _overall_verdict(route_verdict: str, security_verdict: str) -> str:
    if route_verdict == "blocked" or security_verdict == "blocked":
        return "blocked"
    if route_verdict == "indeterminate" or security_verdict == "indeterminate":
        return "partially_evaluated"
    return "allowed"


def explain_network_path(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_interface_name: str,
    destination_ip: str,
    destination_port: int,
    protocol: str,
) -> NetworkPathExplanation:
    """Evaluate route resolution and NSG rules for one source NIC toward
    one destination. ``overall_verdict`` is ``"allowed"`` only when both
    route resolution and NSG evaluation independently concluded so;
    ``"blocked"`` if either did; ``"partially_evaluated"`` if either
    layer's evidence was incomplete -- never silently upgraded to
    ``"allowed"``.
    """
    source_nic_id = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/"
        f"Microsoft.Network/networkInterfaces/{network_interface_name}"
    )
    effective_routes, effective_rules = collect_nic_effective_state(
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
        network_interface_name=network_interface_name,
    )

    freshness = now_iso()

    route_verdict, route_finding = evaluate_route(
        source_nic_id=source_nic_id,
        effective_routes=effective_routes,
        destination_ip=destination_ip,
        freshness=freshness,
    )
    security_verdict, security_finding = evaluate_security_rules(
        source_nic_id=source_nic_id,
        effective_rules=effective_rules,
        destination_ip=destination_ip,
        destination_port=destination_port,
        protocol=protocol,
        freshness=freshness,
    )

    return NetworkPathExplanation(
        source_nic_id=source_nic_id,
        destination_ip=destination_ip,
        destination_port=destination_port,
        protocol=protocol,
        route_verdict=route_verdict,
        security_verdict=security_verdict,
        overall_verdict=_overall_verdict(route_verdict, security_verdict),
        findings=[route_finding, security_finding],
    )


__all__ = ["NetworkPathExplanation", "explain_network_path"]
