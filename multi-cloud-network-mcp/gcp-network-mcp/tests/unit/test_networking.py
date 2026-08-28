from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager, make_pager

from gcp_network_mcp.gcp.networking import extract_peerings, list_networks, list_subnetworks


def _network(*, auto: bool, name: str = "vpc-1", mtu: int = 1460) -> compute_v1.Network:
    return compute_v1.Network(
        name=name,
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/{name}",
        auto_create_subnetworks=auto,
        mtu=mtu,
        id=12345,
    )


def test_list_networks_derives_auto_mode(client_factory) -> None:
    client_factory.networks().list.return_value = make_pager([_network(auto=True)])
    networks = list_networks(client_factory, project_id=PROJECT_ID)
    assert len(networks) == 1
    assert networks[0].mode == "auto"
    assert networks[0].project_id == PROJECT_ID


def test_list_networks_derives_custom_mode(client_factory) -> None:
    client_factory.networks().list.return_value = make_pager([_network(auto=False)])
    networks = list_networks(client_factory, project_id=PROJECT_ID)
    assert networks[0].mode == "custom"


def test_extract_peerings_maps_owning_and_peer_network() -> None:
    network = _network(auto=True, name="vpc-a")
    network.peerings.append(
        compute_v1.NetworkPeering(
            name="peer-a-to-b",
            network=(
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-b"
            ),
            state="ACTIVE",
            exchange_subnet_routes=True,
        )
    )
    peerings = extract_peerings(network)
    assert len(peerings) == 1
    assert peerings[0].owning_network_self_link == network.self_link
    assert peerings[0].network.endswith("/vpc-b")
    assert peerings[0].state == "ACTIVE"


def test_list_subnetworks_aggregates_across_regions_with_secondary_ranges(client_factory) -> None:
    subnet = compute_v1.Subnetwork(
        name="subnet-1",
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/subnetworks/subnet-1"
        ),
        network=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1",
        ip_cidr_range="10.0.0.0/24",
        private_ip_google_access=True,
        secondary_ip_ranges=[
            compute_v1.SubnetworkSecondaryRange(range_name="pods", ip_cidr_range="10.1.0.0/16")
        ],
    )
    client_factory.subnetworks().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [subnet]}, items_field="subnetworks"
    )
    result = list_subnetworks(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].region == "us-central1"
    assert result.data[0].secondary_ip_ranges[0].range_name == "pods"
    assert result.data[0].private_ip_google_access is True
    assert result.warnings == []
