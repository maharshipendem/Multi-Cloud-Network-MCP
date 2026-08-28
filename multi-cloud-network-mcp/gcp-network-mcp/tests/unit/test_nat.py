from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager

from gcp_network_mcp.gcp.nat import list_routers, normalize_router


def _router() -> compute_v1.Router:
    return compute_v1.Router(
        name="router-1",
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/routers/router-1"
        ),
        network=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1",
        bgp=compute_v1.RouterBgp(asn=64512),
        nats=[
            compute_v1.RouterNat(
                name="nat-1",
                nat_ip_allocate_option="AUTO_ONLY",
                source_subnetwork_ip_ranges_to_nat="ALL_SUBNETWORKS_ALL_IP_RANGES",
                min_ports_per_vm=64,
            )
        ],
    )


def test_normalize_router_extracts_nat_and_bgp_asn() -> None:
    normalized = normalize_router(_router(), project_id=PROJECT_ID)
    assert normalized.region == "us-central1"
    assert normalized.bgp_asn == 64512
    assert len(normalized.nats) == 1
    assert normalized.nats[0].name == "nat-1"
    assert normalized.nats[0].min_ports_per_vm == 64


def test_normalize_router_without_bgp_has_no_asn() -> None:
    router = compute_v1.Router(name="router-2", network="net")
    normalized = normalize_router(router, project_id=PROJECT_ID)
    assert normalized.bgp_asn is None


def test_list_routers_aggregates_across_regions(client_factory) -> None:
    client_factory.routers().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [_router()]}, items_field="routers"
    )
    result = list_routers(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].nats[0].name == "nat-1"
