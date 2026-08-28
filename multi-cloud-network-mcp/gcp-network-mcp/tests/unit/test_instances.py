from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager

from gcp_network_mcp.gcp.instances import list_instances, normalize_instance

ZONE_SELF_LINK = f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/zones/us-central1-a/instances/vm-1"


def _instance() -> compute_v1.Instance:
    return compute_v1.Instance(
        name="vm-1",
        self_link=ZONE_SELF_LINK,
        status="RUNNING",
        can_ip_forward=True,
        tags=compute_v1.Tags(items=["web", "prod"]),
        service_accounts=[compute_v1.ServiceAccount(email="sa@proj.iam.gserviceaccount.com")],
        network_interfaces=[
            compute_v1.NetworkInterface(
                name="nic0",
                network=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1",
                subnetwork=(
                    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
                    "us-central1/subnetworks/subnet-1"
                ),
                network_i_p="10.0.0.5",
                access_configs=[
                    compute_v1.AccessConfig(
                        type_="ONE_TO_ONE_NAT", nat_i_p="34.1.2.3", name="external-nat"
                    )
                ],
            )
        ],
    )


def test_normalize_instance_extracts_zone_and_tags() -> None:
    normalized = normalize_instance(_instance(), project_id=PROJECT_ID)
    assert normalized.zone == "us-central1-a"
    assert normalized.tags == ["web", "prod"]
    assert normalized.service_accounts == ["sa@proj.iam.gserviceaccount.com"]
    assert len(normalized.network_interfaces) == 1
    interface = normalized.network_interfaces[0]
    assert interface.network_ip == "10.0.0.5"
    assert interface.access_configs[0].nat_ip == "34.1.2.3"
    assert interface.access_configs[0].type_ == "ONE_TO_ONE_NAT"


def test_list_instances_aggregates_across_zones(client_factory) -> None:
    client_factory.instances().aggregated_list.return_value = make_aggregated_pager(
        {"zones/us-central1-a": [_instance()]}, items_field="instances"
    )
    result = list_instances(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].name == "vm-1"
    assert result.warnings == []
