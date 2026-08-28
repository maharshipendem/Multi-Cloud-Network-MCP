from __future__ import annotations

import pytest
from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_pager

from gcp_network_mcp.gcp.routes import list_routes, normalize_route


def _route(**kwargs: object) -> compute_v1.Route:
    return compute_v1.Route(
        name="route-1",
        network=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1",
        dest_range="10.5.0.0/16",
        priority=1000,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("field", "value", "expected_type"),
    [
        ("next_hop_gateway", "default-internet-gateway", "internet_gateway"),
        ("next_hop_ip", "10.0.0.1", "ip_address"),
        ("next_hop_instance", "projects/p/zones/z/instances/vm-1", "instance"),
        ("next_hop_vpn_tunnel", "projects/p/regions/r/vpnTunnels/tun-1", "vpn_tunnel"),
        ("next_hop_peering", "peer-a", "vpc_peering"),
        (
            "next_hop_interconnect_attachment",
            "projects/p/regions/r/interconnectAttachments/a1",
            "interconnect_attachment",
        ),
        ("next_hop_ilb", "projects/p/regions/r/forwardingRules/ilb-1", "internal_load_balancer"),
    ],
)
def test_next_hop_type_derived_from_populated_field(
    field: str, value: str, expected_type: str
) -> None:
    route = _route(**{field: value})
    normalized = normalize_route(route, project_id=PROJECT_ID)
    assert normalized.next_hop_type == expected_type
    assert normalized.next_hop_target == value


def test_route_with_no_next_hop_field_set_is_unknown() -> None:
    route = _route()
    normalized = normalize_route(route, project_id=PROJECT_ID)
    assert normalized.next_hop_type == "unknown"
    assert normalized.next_hop_target is None


def test_list_routes_is_project_scoped_not_region_scoped(client_factory) -> None:
    client_factory.routes().list.return_value = make_pager([_route(next_hop_gateway="gw")])
    routes = list_routes(client_factory, project_id=PROJECT_ID)
    assert len(routes) == 1
    client_factory.routes().list.assert_called_once()
    _, kwargs = client_factory.routes().list.call_args
    assert kwargs == {"project": PROJECT_ID}
