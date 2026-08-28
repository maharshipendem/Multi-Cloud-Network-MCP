from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_pager

from gcp_network_mcp.gcp.private_service_access import list_private_service_access_ranges


def _global_address(
    *, name: str, purpose: str | None, address: str = "10.10.0.0"
) -> compute_v1.Address:
    return compute_v1.Address(
        name=name,
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/addresses/{name}"
        ),
        address=address,
        address_type="INTERNAL",
        prefix_length=16,
        purpose=purpose,
        network=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1",
        status="RESERVED",
    )


def test_list_private_service_access_ranges_filters_to_vpc_peering_purpose(client_factory) -> None:
    psa_range = _global_address(name="psa-range", purpose="VPC_PEERING")
    other_address = _global_address(name="lb-ip", purpose="GCE_ENDPOINT", address="34.0.0.1")
    client_factory.global_addresses().list.return_value = make_pager([psa_range, other_address])

    result = list_private_service_access_ranges(client_factory, project_id=PROJECT_ID)

    assert len(result) == 1
    assert result[0].name == "psa-range"
    assert result[0].address == "10.10.0.0"
    assert result[0].prefix_length == 16
    assert result[0].project_id == PROJECT_ID
    assert result[0].status == "RESERVED"
    assert result[0].network_self_link == psa_range.network


def test_list_private_service_access_ranges_empty_when_no_vpc_peering_addresses(
    client_factory,
) -> None:
    other_address = _global_address(name="lb-ip", purpose="GCE_ENDPOINT", address="34.0.0.1")
    client_factory.global_addresses().list.return_value = make_pager([other_address])

    result = list_private_service_access_ranges(client_factory, project_id=PROJECT_ID)

    assert result == []


def test_list_private_service_access_ranges_empty_when_no_addresses(client_factory) -> None:
    client_factory.global_addresses().list.return_value = make_pager([])

    result = list_private_service_access_ranges(client_factory, project_id=PROJECT_ID)

    assert result == []
