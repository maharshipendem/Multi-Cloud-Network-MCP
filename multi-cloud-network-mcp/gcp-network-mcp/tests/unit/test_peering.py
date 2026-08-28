from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_pager

from gcp_network_mcp.gcp.peering import list_network_peerings


def test_list_network_peerings_flattens_across_networks(client_factory) -> None:
    net_a = compute_v1.Network(
        name="vpc-a",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-a",
        peerings=[
            compute_v1.NetworkPeering(
                name="a-to-b",
                network=(
                    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-b"
                ),
                state="ACTIVE",
            )
        ],
    )
    net_b = compute_v1.Network(
        name="vpc-b",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-b",
    )
    client_factory.networks().list.return_value = make_pager([net_a, net_b])

    peerings = list_network_peerings(client_factory, project_id=PROJECT_ID)
    assert len(peerings) == 1
    assert peerings[0].name == "a-to-b"
    assert peerings[0].owning_network_self_link == net_a.self_link
    assert peerings[0].network == net_b.self_link
