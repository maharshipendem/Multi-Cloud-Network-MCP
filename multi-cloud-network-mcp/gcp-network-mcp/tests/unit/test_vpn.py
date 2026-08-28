from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager, make_pager

from gcp_network_mcp.gcp.vpn import (
    get_vpn_gateway_status,
    list_external_vpn_gateways,
    list_vpn_gateways,
    list_vpn_tunnels,
    normalize_external_vpn_gateway,
    normalize_vpn_gateway,
    normalize_vpn_tunnel,
)
from gcp_network_mcp.models.vpn import VpnTunnel

_VPN_GATEWAY_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
    "us-central1/vpnGateways/gw-1"
)
_VPN_TUNNEL_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
    "us-central1/vpnTunnels/tunnel-1"
)


def _vpn_gateway() -> compute_v1.VpnGateway:
    return compute_v1.VpnGateway(
        name="gw-1",
        self_link=_VPN_GATEWAY_SELF_LINK,
        network=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
        ),
        stack_type="IPV4_ONLY",
        gateway_ip_version="IPV4",
        vpn_interfaces=[
            compute_v1.VpnGatewayVpnGatewayInterface(id=0, ip_address="34.1.2.3"),
            compute_v1.VpnGatewayVpnGatewayInterface(id=1, ip_address="34.1.2.4"),
        ],
    )


def _vpn_tunnel(**overrides: object) -> compute_v1.VpnTunnel:
    fields = {
        "name": "tunnel-1",
        "self_link": _VPN_TUNNEL_SELF_LINK,
        "vpn_gateway": _VPN_GATEWAY_SELF_LINK,
        "vpn_gateway_interface": 0,
        "peer_ip": "203.0.113.1",
        "ike_version": 2,
        "status": "ESTABLISHED",
        "detailed_status": "Tunnel is up and running.",
        "local_traffic_selector": ["0.0.0.0/0"],
        "remote_traffic_selector": ["0.0.0.0/0"],
    }
    fields.update(overrides)
    return compute_v1.VpnTunnel(**fields)


def _external_vpn_gateway() -> compute_v1.ExternalVpnGateway:
    return compute_v1.ExternalVpnGateway(
        name="ext-gw-1",
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/"
            "externalVpnGateways/ext-gw-1"
        ),
        redundancy_type="TWO_IPS_REDUNDANCY",
        interfaces=[
            compute_v1.ExternalVpnGatewayInterface(id=0, ip_address="198.51.100.1"),
            compute_v1.ExternalVpnGatewayInterface(id=1, ip_address="198.51.100.2"),
        ],
    )


def test_normalize_vpn_gateway_extracts_region_and_interfaces() -> None:
    normalized = normalize_vpn_gateway(_vpn_gateway(), project_id=PROJECT_ID)
    assert normalized.name == "gw-1"
    assert normalized.region == "us-central1"
    assert normalized.stack_type == "IPV4_ONLY"
    assert normalized.gateway_ip_version == "IPV4"
    assert len(normalized.interfaces) == 2
    assert normalized.interfaces[0].ip_address == "34.1.2.3"
    assert normalized.interfaces[1].id == 1


def test_list_vpn_gateways_aggregates_across_regions(client_factory) -> None:
    client_factory.vpn_gateways().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [_vpn_gateway()]}, items_field="vpn_gateways"
    )
    result = list_vpn_gateways(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].name == "gw-1"


def test_list_vpn_gateways_empty(client_factory) -> None:
    client_factory.vpn_gateways().aggregated_list.return_value = make_aggregated_pager(
        {}, items_field="vpn_gateways"
    )
    result = list_vpn_gateways(client_factory, project_id=PROJECT_ID)
    assert result.data == []
    assert result.warnings == []


def test_normalize_vpn_tunnel_extracts_expected_fields() -> None:
    normalized = normalize_vpn_tunnel(_vpn_tunnel(), project_id=PROJECT_ID)
    assert normalized.name == "tunnel-1"
    assert normalized.region == "us-central1"
    assert normalized.vpn_gateway_self_link == _VPN_GATEWAY_SELF_LINK
    assert normalized.vpn_gateway_interface == 0
    assert normalized.peer_ip == "203.0.113.1"
    assert normalized.ike_version == 2
    assert normalized.status == "ESTABLISHED"
    assert normalized.local_traffic_selector == ["0.0.0.0/0"]
    assert normalized.remote_traffic_selector == ["0.0.0.0/0"]


def test_normalize_vpn_tunnel_never_leaks_shared_secret() -> None:
    """Regression test: VpnTunnel's raw SDK type carries `shared_secret`/
    `shared_secret_hash` (the IKE pre-shared key and its hash). The
    normalizer must never read them -- prove it by literal string search
    over the full repr of the normalized model, not just "the field is
    absent from the Pydantic model"."""
    raw = _vpn_tunnel(
        shared_secret="super-secret-value-xyz",
        shared_secret_hash="hash-of-super-secret-value-xyz",
    )
    normalized = normalize_vpn_tunnel(raw, project_id=PROJECT_ID)
    assert "super-secret-value-xyz" not in str(normalized)
    assert "hash-of-super-secret-value-xyz" not in str(normalized)
    assert "shared_secret" not in VpnTunnel.model_fields
    assert "shared_secret_hash" not in VpnTunnel.model_fields
    assert normalized.redacted is True


def test_list_vpn_tunnels_aggregates_across_regions(client_factory) -> None:
    client_factory.vpn_tunnels().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [_vpn_tunnel()]}, items_field="vpn_tunnels"
    )
    result = list_vpn_tunnels(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].name == "tunnel-1"


def test_list_vpn_tunnels_empty(client_factory) -> None:
    client_factory.vpn_tunnels().aggregated_list.return_value = make_aggregated_pager(
        {}, items_field="vpn_tunnels"
    )
    result = list_vpn_tunnels(client_factory, project_id=PROJECT_ID)
    assert result.data == []


def test_normalize_external_vpn_gateway_extracts_interfaces() -> None:
    normalized = normalize_external_vpn_gateway(_external_vpn_gateway(), project_id=PROJECT_ID)
    assert normalized.name == "ext-gw-1"
    assert normalized.redundancy_type == "TWO_IPS_REDUNDANCY"
    assert len(normalized.interfaces) == 2
    assert normalized.interfaces[0].ip_address == "198.51.100.1"
    assert normalized.interfaces[1].id == 1


def test_list_external_vpn_gateways_uses_plain_list(client_factory) -> None:
    client_factory.external_vpn_gateways().list.return_value = make_pager([_external_vpn_gateway()])
    result = list_external_vpn_gateways(client_factory, project_id=PROJECT_ID)
    assert len(result) == 1
    assert result[0].name == "ext-gw-1"


def test_list_external_vpn_gateways_empty(client_factory) -> None:
    client_factory.external_vpn_gateways().list.return_value = make_pager([])
    result = list_external_vpn_gateways(client_factory, project_id=PROJECT_ID)
    assert result == []


def test_get_vpn_gateway_status_extracts_ha_requirement_state(client_factory) -> None:
    """Regression test: each VPN connection's HA-redundancy state lives on
    a nested `VpnGatewayStatusHighAvailabilityRequirementState` sub-message
    (`connection.state.state` / `connection.state.unsatisfied_reason`),
    not a flat field on the connection itself. The model fields were
    renamed to `ha_requirement_state`/`ha_unsatisfied_reason` specifically
    because of this nesting."""
    raw_response = compute_v1.VpnGatewaysGetStatusResponse(
        result=compute_v1.VpnGatewayStatus(
            vpn_connections=[
                compute_v1.VpnGatewayStatusVpnConnection(
                    peer_external_gateway="https://www.googleapis.com/compute/v1/projects/"
                    f"{PROJECT_ID}/global/externalVpnGateways/ext-gw-1",
                    state=compute_v1.VpnGatewayStatusHighAvailabilityRequirementState(
                        state="CONNECTION_REDUNDANCY_MEETS_SPEC",
                        unsatisfied_reason="",
                    ),
                    tunnels=[
                        compute_v1.VpnGatewayStatusTunnel(
                            tunnel_url=_VPN_TUNNEL_SELF_LINK,
                            local_gateway_interface=0,
                            peer_gateway_interface=0,
                        )
                    ],
                )
            ]
        )
    )
    client_factory.vpn_gateways().get_status.return_value = raw_response

    status = get_vpn_gateway_status(
        client_factory, project_id=PROJECT_ID, region="us-central1", vpn_gateway_name="gw-1"
    )

    assert status.vpn_gateway_self_link == _VPN_GATEWAY_SELF_LINK
    assert len(status.connections) == 1
    connection = status.connections[0]
    assert connection.ha_requirement_state == "CONNECTION_REDUNDANCY_MEETS_SPEC"
    assert connection.ha_unsatisfied_reason is None
    assert len(connection.tunnels) == 1
    assert connection.tunnels[0].tunnel_url == _VPN_TUNNEL_SELF_LINK
    assert connection.tunnels[0].local_gateway_interface == 0


def test_get_vpn_gateway_status_with_unsatisfied_reason(client_factory) -> None:
    raw_response = compute_v1.VpnGatewaysGetStatusResponse(
        result=compute_v1.VpnGatewayStatus(
            vpn_connections=[
                compute_v1.VpnGatewayStatusVpnConnection(
                    peer_gcp_gateway="https://www.googleapis.com/compute/v1/projects/"
                    f"{PROJECT_ID}/regions/us-central1/vpnGateways/peer-gw",
                    state=compute_v1.VpnGatewayStatusHighAvailabilityRequirementState(
                        state="CONNECTION_REDUNDANCY_NOT_MEETING_SPEC",
                        unsatisfied_reason="INCOMPLETE_TUNNELS_COVERAGE",
                    ),
                    tunnels=[],
                )
            ]
        )
    )
    client_factory.vpn_gateways().get_status.return_value = raw_response

    status = get_vpn_gateway_status(
        client_factory, project_id=PROJECT_ID, region="us-central1", vpn_gateway_name="gw-1"
    )

    connection = status.connections[0]
    assert connection.ha_requirement_state == "CONNECTION_REDUNDANCY_NOT_MEETING_SPEC"
    assert connection.ha_unsatisfied_reason == "INCOMPLETE_TUNNELS_COVERAGE"
    assert connection.tunnels == []


def test_get_vpn_gateway_status_no_connections(client_factory) -> None:
    raw_response = compute_v1.VpnGatewaysGetStatusResponse(
        result=compute_v1.VpnGatewayStatus(vpn_connections=[])
    )
    client_factory.vpn_gateways().get_status.return_value = raw_response

    status = get_vpn_gateway_status(
        client_factory, project_id=PROJECT_ID, region="us-central1", vpn_gateway_name="gw-1"
    )
    assert status.connections == []
