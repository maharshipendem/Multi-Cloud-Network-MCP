from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager

from gcp_network_mcp.gcp.packet_mirroring import (
    list_packet_mirroring_policies,
    normalize_packet_mirroring,
)


def test_normalize_packet_mirroring_maps_fields() -> None:
    policy = compute_v1.PacketMirroring(
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/packetMirrorings/mirror-1"
        ),
        id=456,
        name="mirror-1",
        region=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1",
        network=compute_v1.PacketMirroringNetworkInfo(
            url=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
        ),
        collector_ilb=compute_v1.PacketMirroringForwardingRuleInfo(
            url=(
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
                "us-central1/forwardingRules/collector-fr"
            )
        ),
        enable="TRUE",
        priority=1000,
        mirrored_resources=compute_v1.PacketMirroringMirroredResourceInfo(
            instances=[
                compute_v1.PacketMirroringMirroredResourceInfoInstanceInfo(
                    url=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/zones/us-central1-a/instances/vm-1"
                )
            ],
            subnetworks=[
                compute_v1.PacketMirroringMirroredResourceInfoSubnetInfo(
                    url=(
                        f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
                        "us-central1/subnetworks/subnet-1"
                    )
                )
            ],
            tags=["mirror-me"],
        ),
        filter=compute_v1.PacketMirroringFilter(
            I_p_protocols=["tcp", "udp"],
            cidr_ranges=["10.0.0.0/8"],
            direction="BOTH",
        ),
    )

    result = normalize_packet_mirroring(policy, project_id=PROJECT_ID)

    assert result.name == "mirror-1"
    assert result.id == "456"
    assert result.project_id == PROJECT_ID
    assert result.region == "us-central1"
    assert result.network_self_link == policy.network.url
    assert result.collector_ilb_forwarding_rule == policy.collector_ilb.url
    assert result.enable == "TRUE"
    assert result.priority == 1000
    assert result.mirrored_instance_self_links == [policy.mirrored_resources.instances[0].url]
    assert result.mirrored_subnetwork_self_links == [policy.mirrored_resources.subnetworks[0].url]
    assert result.mirrored_tags == ["mirror-me"]
    assert result.filter is not None
    assert result.filter.ip_protocols == ["tcp", "udp"]
    assert result.filter.cidr_ranges == ["10.0.0.0/8"]
    assert result.filter.direction == "BOTH"
    assert result.source_api == "PacketMirroringsClient.aggregated_list"


def test_normalize_packet_mirroring_without_filter_or_mirrored_resources() -> None:
    policy = compute_v1.PacketMirroring(
        name="mirror-minimal",
        network=compute_v1.PacketMirroringNetworkInfo(
            url=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
        ),
    )

    result = normalize_packet_mirroring(policy, project_id=PROJECT_ID)

    assert result.filter is None
    assert result.mirrored_instance_self_links == []
    assert result.mirrored_subnetwork_self_links == []
    assert result.mirrored_tags == []
    assert result.collector_ilb_forwarding_rule is None
    assert result.enable is None
    assert result.priority is None


def test_normalize_packet_mirroring_without_network_defaults_empty_string() -> None:
    policy = compute_v1.PacketMirroring(name="mirror-no-network")

    result = normalize_packet_mirroring(policy, project_id=PROJECT_ID)

    assert result.network_self_link == ""


def test_list_packet_mirroring_policies_flattens_aggregated_scopes(client_factory) -> None:
    policy = compute_v1.PacketMirroring(
        name="mirror-1",
        region=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1",
        network=compute_v1.PacketMirroringNetworkInfo(
            url=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
        ),
    )
    client_factory.packet_mirrorings().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [policy]}, items_field="packet_mirrorings"
    )

    result = list_packet_mirroring_policies(client_factory, project_id=PROJECT_ID)

    assert len(result.data) == 1
    assert result.data[0].name == "mirror-1"
    assert result.warnings == []


def test_list_packet_mirroring_policies_empty(client_factory) -> None:
    client_factory.packet_mirrorings().aggregated_list.return_value = make_aggregated_pager(
        {}, items_field="packet_mirrorings"
    )

    result = list_packet_mirroring_policies(client_factory, project_id=PROJECT_ID)

    assert result.data == []
