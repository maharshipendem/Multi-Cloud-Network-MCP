from __future__ import annotations

from azure_network_mcp.models.common import normalize_resource_id, parse_resource_id

SUB = "11111111-1111-1111-1111-111111111111"
RG = "rg-network-test"


def test_parse_full_subnet_resource_id() -> None:
    resource_id = (
        f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/"
        "virtualNetworks/vnet-1/subnets/subnet-a"
    )
    parsed = parse_resource_id(resource_id)
    assert parsed.subscription_id == SUB
    assert parsed.resource_group == RG
    assert parsed.provider_namespace == "Microsoft.Network"
    assert parsed.resource_type == "subnets"
    assert parsed.resource_name == "subnet-a"


def test_parse_vnet_only_resource_id() -> None:
    resource_id = (
        f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/"
        "virtualNetworks/vnet-1"
    )
    parsed = parse_resource_id(resource_id)
    assert parsed.resource_type == "virtualNetworks"
    assert parsed.resource_name == "vnet-1"


def test_parse_resource_group_only_id() -> None:
    resource_id = f"/subscriptions/{SUB}/resourceGroups/{RG}"
    parsed = parse_resource_id(resource_id)
    assert parsed.subscription_id == SUB
    assert parsed.resource_group == RG
    assert parsed.provider_namespace is None
    assert parsed.resource_type is None


def test_parse_malformed_id_degrades_to_all_none_without_raising() -> None:
    parsed = parse_resource_id("not-a-resource-id")
    assert parsed.subscription_id is None
    assert parsed.resource_group is None
    assert parsed.provider_namespace is None
    assert parsed.resource_type is None
    assert parsed.resource_name is None


def test_parse_empty_string_does_not_raise() -> None:
    parsed = parse_resource_id("")
    assert parsed.subscription_id is None


def test_normalize_resource_id_lowercases() -> None:
    resource_id = f"/subscriptions/{SUB}/resourceGroups/RG-Mixed-Case"
    assert normalize_resource_id(resource_id) == resource_id.lower()
