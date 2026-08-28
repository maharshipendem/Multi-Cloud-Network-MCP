"""Service-layer functions for HA Cloud VPN: gateways, tunnels,
external VPN gateways, and HA-redundancy status."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate, paginate_aggregated
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.models.common import parse_self_link
from gcp_network_mcp.models.vpn import (
    ExternalVpnGateway,
    ExternalVpnGatewayInterface,
    VpnGateway,
    VpnGatewayConnectionStatus,
    VpnGatewayConnectionTunnel,
    VpnGatewayInterface,
    VpnGatewayStatus,
    VpnTunnel,
)


def normalize_vpn_gateway(gateway: compute_v1.VpnGateway, *, project_id: str) -> VpnGateway:
    parsed = parse_self_link(gateway.self_link) if gateway.self_link else None
    return VpnGateway(
        self_link=gateway.self_link or None,
        id=str(gateway.id) if gateway.id else None,
        name=gateway.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        network_self_link=gateway.network,
        stack_type=gateway.stack_type or None,
        gateway_ip_version=gateway.gateway_ip_version or None,
        interfaces=[
            VpnGatewayInterface(
                id=i.id,
                ip_address=i.ip_address or None,
                interconnect_attachment=i.interconnect_attachment or None,
            )
            for i in gateway.vpn_interfaces
        ],
        observed_at=now_iso(),
        source_api="VpnGatewaysClient.aggregated_list",
    )


def list_vpn_gateways(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.vpn_gateways(),
        "aggregated_list",
        items_field="vpn_gateways",
        resource_type="vpn_gateway",
        project_id=project_id,
        project=project_id,
    )
    return CollectionResult(
        data=[normalize_vpn_gateway(g, project_id=project_id) for g in raw], warnings=warnings
    )


def get_vpn_gateway_status(
    client_factory: ClientFactory, *, project_id: str, region: str, vpn_gateway_name: str
) -> VpnGatewayStatus:
    """The read-only computed HA-redundancy view for one VPN gateway:
    each peer connection's tunnels and their state."""
    result = call_readonly(
        client_factory.vpn_gateways(),
        "get_status",
        project=project_id,
        region=region,
        vpn_gateway=vpn_gateway_name,
    )
    vpn_gateway_self_link = (
        f"https://www.googleapis.com/compute/v1/projects/{project_id}/regions/"
        f"{region}/vpnGateways/{vpn_gateway_name}"
    )
    connections = [
        VpnGatewayConnectionStatus(
            peer_external_gateway=c.peer_external_gateway or None,
            peer_gcp_gateway=c.peer_gcp_gateway or None,
            ha_requirement_state=(c.state.state or None) if "state" in c else None,
            ha_unsatisfied_reason=(c.state.unsatisfied_reason or None) if "state" in c else None,
            tunnels=[
                VpnGatewayConnectionTunnel(
                    tunnel_url=t.tunnel_url or None,
                    local_gateway_interface=t.local_gateway_interface,
                    peer_gateway_interface=t.peer_gateway_interface,
                )
                for t in c.tunnels
            ],
        )
        for c in result.result.vpn_connections
    ]
    return VpnGatewayStatus(
        vpn_gateway_self_link=vpn_gateway_self_link, connections=connections, observed_at=now_iso()
    )


def normalize_vpn_tunnel(tunnel: compute_v1.VpnTunnel, *, project_id: str) -> VpnTunnel:
    parsed = parse_self_link(tunnel.self_link) if tunnel.self_link else None
    return VpnTunnel(
        self_link=tunnel.self_link or None,
        id=str(tunnel.id) if tunnel.id else None,
        name=tunnel.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        vpn_gateway_self_link=tunnel.vpn_gateway or None,
        vpn_gateway_interface=tunnel.vpn_gateway_interface,
        peer_ip=tunnel.peer_ip or None,
        peer_gcp_gateway=tunnel.peer_gcp_gateway or None,
        peer_external_gateway=tunnel.peer_external_gateway or None,
        peer_external_gateway_interface=tunnel.peer_external_gateway_interface
        if "peer_external_gateway_interface" in tunnel
        else None,
        router_self_link=tunnel.router or None,
        ike_version=tunnel.ike_version or None,
        status=tunnel.status or None,
        detailed_status=tunnel.detailed_status or None,
        local_traffic_selector=list(tunnel.local_traffic_selector),
        remote_traffic_selector=list(tunnel.remote_traffic_selector),
        observed_at=now_iso(),
        source_api="VpnTunnelsClient.aggregated_list",
    )


def list_vpn_tunnels(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.vpn_tunnels(),
        "aggregated_list",
        items_field="vpn_tunnels",
        resource_type="vpn_tunnel",
        project_id=project_id,
        project=project_id,
    )
    return CollectionResult(
        data=[normalize_vpn_tunnel(t, project_id=project_id) for t in raw], warnings=warnings
    )


def normalize_external_vpn_gateway(
    gateway: compute_v1.ExternalVpnGateway, *, project_id: str
) -> ExternalVpnGateway:
    return ExternalVpnGateway(
        self_link=gateway.self_link or None,
        id=str(gateway.id) if gateway.id else None,
        name=gateway.name,
        project_id=project_id,
        redundancy_type=gateway.redundancy_type or None,
        interfaces=[
            ExternalVpnGatewayInterface(id=i.id, ip_address=i.ip_address or None)
            for i in gateway.interfaces
        ],
        observed_at=now_iso(),
        source_api="ExternalVpnGatewaysClient.list",
    )


def list_external_vpn_gateways(
    client_factory: ClientFactory, *, project_id: str
) -> list[ExternalVpnGateway]:
    raw = paginate(
        client_factory.external_vpn_gateways(),
        "list",
        resource_type="external_vpn_gateway",
        project_id=project_id,
        project=project_id,
    )
    return [normalize_external_vpn_gateway(g, project_id=project_id) for g in raw]


__all__ = [
    "get_vpn_gateway_status",
    "list_external_vpn_gateways",
    "list_vpn_gateways",
    "list_vpn_tunnels",
    "normalize_external_vpn_gateway",
    "normalize_vpn_gateway",
    "normalize_vpn_tunnel",
]
