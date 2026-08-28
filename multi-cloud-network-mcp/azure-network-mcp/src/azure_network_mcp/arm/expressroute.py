"""ARM service layer: ExpressRoute circuits, peerings, connections,
gateways, ports, and links.

Never reads ``authorization_key``, ``service_key``, or ``shared_key`` from
any SDK response -- see models/hybrid_connectivity.py's module docstring
for the full redaction-by-omission rationale. This module also never
calls ``ExpressRouteCircuitAuthorizationsOperations`` at all (the
operation group that manages circuit authorizations, which embed the
actual authorization key) -- there is simply no collector for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.readonly import call_readonly
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.hybrid_connectivity import (
    ExpressRouteCircuit,
    ExpressRouteCircuitConnection,
    ExpressRouteCircuitPeering,
    ExpressRouteConnection,
    ExpressRouteGateway,
    ExpressRouteLink,
    ExpressRoutePort,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def _normalize_peering(
    peering: Any, *, subscription_id: str, circuit_name: str, observed_at: str
) -> ExpressRouteCircuitPeering:
    parsed = parse_resource_id(peering.id) if getattr(peering, "id", None) else None
    return ExpressRouteCircuitPeering(
        resource_id=peering.id or "",
        name=peering.name,
        subscription_id=(parsed.subscription_id if parsed else None) or subscription_id,
        resource_group=parsed.resource_group if parsed else None,
        provisioning_state=getattr(peering, "provisioning_state", None),
        observed_at=observed_at,
        source_api="Microsoft.Network/expressRouteCircuits/peerings",
        circuit_name=circuit_name,
        peering_type=getattr(peering, "peering_type", None),
        state=getattr(peering, "state", None),
        azure_asn=getattr(peering, "azure_asn", None),
        peer_asn=getattr(peering, "peer_asn", None),
        primary_peer_address_prefix=getattr(peering, "primary_peer_address_prefix", None),
        secondary_peer_address_prefix=getattr(peering, "secondary_peer_address_prefix", None),
        vlan_id=getattr(peering, "vlan_id", None),
    )


def list_express_route_circuits(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[ExpressRouteCircuit]:
    """Call ExpressRouteCircuitsOperations.list (one resource group) or
    .list_all (whole subscription). Never reads ``authorization_key``,
    ``service_key``, or ``authorization_status``."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.express_route_circuits,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(
            client.express_route_circuits, "list_all", max_items=settings.max_page_results
        )

    result = []
    for circuit in raw:
        parsed = parse_resource_id(circuit.id)
        sku = getattr(circuit, "sku", None)
        result.append(
            ExpressRouteCircuit(
                resource_id=circuit.id,
                name=circuit.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=circuit.location,
                provisioning_state=getattr(circuit, "provisioning_state", None),
                tags=normalize_tags(circuit.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/expressRouteCircuits",
                sku_name=(getattr(sku, "name", None) if sku else None),
                sku_tier=(getattr(sku, "tier", None) if sku else None),
                sku_family=(getattr(sku, "family", None) if sku else None),
                circuit_provisioning_state=getattr(circuit, "circuit_provisioning_state", None),
                service_provider_provisioning_state=getattr(
                    circuit, "service_provider_provisioning_state", None
                ),
                service_provider_name=(
                    getattr(circuit.service_provider_properties, "service_provider_name", None)
                    if getattr(circuit, "service_provider_properties", None)
                    else None
                ),
                peering_location=(
                    getattr(circuit.service_provider_properties, "peering_location", None)
                    if getattr(circuit, "service_provider_properties", None)
                    else None
                ),
                bandwidth_in_mbps=(
                    getattr(circuit.service_provider_properties, "bandwidth_in_mbps", None)
                    if getattr(circuit, "service_provider_properties", None)
                    else None
                ),
                express_route_port_id=(
                    circuit.express_route_port.id
                    if getattr(circuit, "express_route_port", None)
                    else None
                ),
                global_reach_enabled=getattr(circuit, "global_reach_enabled", None),
                peerings=[
                    _normalize_peering(
                        p,
                        subscription_id=subscription_id,
                        circuit_name=circuit.name,
                        observed_at=observed_at,
                    )
                    for p in (circuit.peerings or [])
                ],
            )
        )
    return result


def list_express_route_circuit_peerings(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str, circuit_name: str
) -> list[ExpressRouteCircuitPeering]:
    """Call ExpressRouteCircuitPeeringsOperations.list for one circuit."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.express_route_circuit_peerings,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        circuit_name=circuit_name,
    )
    return [
        _normalize_peering(
            p, subscription_id=subscription_id, circuit_name=circuit_name, observed_at=observed_at
        )
        for p in raw
    ]


def list_express_route_circuit_connections(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    circuit_name: str,
    peering_name: str,
) -> list[ExpressRouteCircuitConnection]:
    """Call ExpressRouteCircuitConnectionsOperations.list -- circuit-to-
    circuit (Global Reach) connections for one peering. Never reads
    ``authorization_key``."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.express_route_circuit_connections,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        circuit_name=circuit_name,
        peering_name=peering_name,
    )
    result = []
    for conn in raw:
        parsed = parse_resource_id(conn.id) if getattr(conn, "id", None) else None
        result.append(
            ExpressRouteCircuitConnection(
                resource_id=conn.id or "",
                name=conn.name,
                subscription_id=(parsed.subscription_id if parsed else None) or subscription_id,
                resource_group=parsed.resource_group if parsed else resource_group,
                provisioning_state=getattr(conn, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/expressRouteCircuits/peerings/connections",
                circuit_name=circuit_name,
                peering_name=peering_name,
                express_route_circuit_peering_id=(
                    conn.express_route_circuit_peering.id
                    if getattr(conn, "express_route_circuit_peering", None)
                    else None
                ),
                peer_express_route_circuit_peering_id=(
                    conn.peer_express_route_circuit_peering.id
                    if getattr(conn, "peer_express_route_circuit_peering", None)
                    else None
                ),
                address_prefix=getattr(conn, "address_prefix", None),
                circuit_connection_status=getattr(conn, "circuit_connection_status", None),
            )
        )
    return result


def list_express_route_gateways(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[ExpressRouteGateway]:
    """Call ExpressRouteGatewaysOperations.list_by_subscription or
    .list_by_resource_group -- both return a non-paginated ``*List``
    wrapper (``.value``), not an ``ItemPaged`` iterator."""
    client = client_factory.get_network_client(subscription_id)
    observed_at = now_iso()

    if resource_group:
        wrapper = call_readonly(
            client.express_route_gateways,
            "list_by_resource_group",
            resource_group_name=resource_group,
        )
    else:
        wrapper = call_readonly(client.express_route_gateways, "list_by_subscription")

    result = []
    for gw in getattr(wrapper, "value", None) or []:
        parsed = parse_resource_id(gw.id)
        auto_scale = getattr(gw, "auto_scale_configuration", None)
        bounds = getattr(auto_scale, "bounds", None) if auto_scale else None
        result.append(
            ExpressRouteGateway(
                resource_id=gw.id,
                name=gw.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=gw.location,
                provisioning_state=getattr(gw, "provisioning_state", None),
                tags=normalize_tags(gw.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/expressRouteGateways",
                virtual_hub_id=(gw.virtual_hub.id if getattr(gw, "virtual_hub", None) else None),
                min_scale_units=(getattr(bounds, "min", None) if bounds else None),
                max_scale_units=(getattr(bounds, "max", None) if bounds else None),
                allow_non_virtual_wan_traffic=getattr(gw, "allow_non_virtual_wan_traffic", None),
            )
        )
    return result


def list_express_route_connections(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    express_route_gateway_name: str,
) -> list[ExpressRouteConnection]:
    """Call ExpressRouteConnectionsOperations.list -- also returns a
    non-paginated ``*List`` wrapper. Never reads ``authorization_key``."""
    client = client_factory.get_network_client(subscription_id)
    observed_at = now_iso()

    wrapper = call_readonly(
        client.express_route_connections,
        "list",
        resource_group_name=resource_group,
        express_route_gateway_name=express_route_gateway_name,
    )
    result = []
    for conn in getattr(wrapper, "value", None) or []:
        parsed = parse_resource_id(conn.id) if getattr(conn, "id", None) else None
        result.append(
            ExpressRouteConnection(
                resource_id=conn.id or "",
                name=conn.name,
                subscription_id=(parsed.subscription_id if parsed else None) or subscription_id,
                resource_group=parsed.resource_group if parsed else resource_group,
                provisioning_state=getattr(conn, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/expressRouteGateways/expressRouteConnections",
                express_route_gateway_name=express_route_gateway_name,
                express_route_circuit_peering_id=(
                    conn.express_route_circuit_peering.id
                    if getattr(conn, "express_route_circuit_peering", None)
                    else None
                ),
                routing_weight=getattr(conn, "routing_weight", None),
                enable_internet_security=getattr(conn, "enable_internet_security", None),
            )
        )
    return result


def list_express_route_ports(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[ExpressRoutePort]:
    """Call ExpressRoutePortsOperations.list (whole subscription) or
    .list_by_resource_group (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.express_route_ports,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.express_route_ports, "list", max_items=settings.max_page_results)

    result = []
    for port in raw:
        parsed = parse_resource_id(port.id)
        result.append(
            ExpressRoutePort(
                resource_id=port.id,
                name=port.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=port.location,
                provisioning_state=getattr(port, "provisioning_state", None),
                tags=normalize_tags(port.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/expressRoutePorts",
                peering_location=getattr(port, "peering_location", None),
                bandwidth_in_gbps=getattr(port, "bandwidth_in_gbps", None),
                provisioned_bandwidth_in_gbps=getattr(port, "provisioned_bandwidth_in_gbps", None),
                encapsulation=getattr(port, "encapsulation", None),
                ether_type=getattr(port, "ether_type", None),
                link_ids=[link_.id for link_ in (port.links or []) if getattr(link_, "id", None)],
                circuit_ids=[
                    c.id for c in (getattr(port, "circuits", None) or []) if getattr(c, "id", None)
                ],
            )
        )
    return result


def list_express_route_links(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str, port_name: str
) -> list[ExpressRouteLink]:
    """Call ExpressRouteLinksOperations.list -- the physical fiber links
    within one ExpressRoute Direct port."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.express_route_links,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        express_route_port_name=port_name,
    )
    result = []
    for link_ in raw:
        parsed = parse_resource_id(link_.id) if getattr(link_, "id", None) else None
        result.append(
            ExpressRouteLink(
                resource_id=link_.id or "",
                name=link_.name,
                subscription_id=(parsed.subscription_id if parsed else None) or subscription_id,
                resource_group=parsed.resource_group if parsed else resource_group,
                provisioning_state=getattr(link_, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/expressRoutePorts/links",
                port_name=port_name,
                router_name=getattr(link_, "router_name", None),
                interface_name=getattr(link_, "interface_name", None),
                colo_location=getattr(link_, "colo_location", None),
                admin_state=getattr(link_, "admin_state", None),
            )
        )
    return result


__all__ = [
    "list_express_route_circuit_connections",
    "list_express_route_circuit_peerings",
    "list_express_route_circuits",
    "list_express_route_connections",
    "list_express_route_gateways",
    "list_express_route_links",
    "list_express_route_ports",
]
