from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager, make_pager

from gcp_network_mcp.gcp.addresses import list_global_addresses, list_regional_addresses


def test_list_regional_addresses_sets_source_api_and_region(client_factory) -> None:
    addr = compute_v1.Address(
        name="addr-1",
        self_link=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/"
            "us-central1/addresses/addr-1"
        ),
        address="10.0.0.9",
        address_type="INTERNAL",
    )
    client_factory.addresses().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [addr]}, items_field="addresses"
    )
    result = list_regional_addresses(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].region == "us-central1"
    assert result.data[0].source_api == "AddressesClient.aggregated_list"


def test_list_global_addresses_sets_distinct_source_api(client_factory) -> None:
    addr = compute_v1.Address(name="global-addr", address="8.8.8.8", address_type="EXTERNAL")
    client_factory.global_addresses().list.return_value = make_pager([addr])
    addresses = list_global_addresses(client_factory, project_id=PROJECT_ID)
    assert len(addresses) == 1
    assert addresses[0].source_api == "GlobalAddressesClient.list"
    assert addresses[0].region is None
