"""Stable URNs: round-trip, escaping, determinism, and rejection of
malformed input."""

from __future__ import annotations

import pytest

from multicloud_network_mcp.contracts.models.enums import ResourceType
from multicloud_network_mcp.contracts.urn import build_urn, parse_urn, scope_dict


def test_round_trip_simple() -> None:
    urn = build_urn(
        provider="aws",
        scope={"account_id": "123456789012", "region": "us-east-1"},
        resource_type=ResourceType.NETWORK,
        native_id="vpc-0abc123",
    )
    parsed = parse_urn(urn)
    assert parsed.provider == "aws"
    assert parsed.scope == {"account_id": "123456789012", "region": "us-east-1"}
    assert parsed.resource_type == "network"
    assert parsed.native_id == "vpc-0abc123"
    assert parsed.grammar_version == 1


def test_round_trip_colon_in_native_id() -> None:
    native_id = "https://www.googleapis.com/compute/v1/projects/p/global/networks/n"
    urn = build_urn(
        provider="gcp",
        scope={"project_id": "p"},
        resource_type=ResourceType.NETWORK,
        native_id=native_id,
    )
    assert parse_urn(urn).native_id == native_id


def test_round_trip_percent_sign_in_native_id() -> None:
    native_id = "weird-id-100%-legit"
    urn = build_urn(
        provider="aws", scope={}, resource_type=ResourceType.NETWORK, native_id=native_id
    )
    assert parse_urn(urn).native_id == native_id


def test_round_trip_comma_and_equals_in_native_id() -> None:
    native_id = "tag=value,other=thing"
    urn = build_urn(
        provider="aws", scope={}, resource_type=ResourceType.NETWORK, native_id=native_id
    )
    assert parse_urn(urn).native_id == native_id


def test_round_trip_non_ascii_in_native_id() -> None:
    native_id = "résource-ñame-日本語"
    urn = build_urn(
        provider="azure", scope={}, resource_type=ResourceType.NETWORK, native_id=native_id
    )
    assert parse_urn(urn).native_id == native_id


def test_round_trip_slash_left_literal() -> None:
    native_id = (
        "/subscriptions/1234/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
    )
    urn = build_urn(
        provider="azure",
        scope={"subscription_id": "1234", "resource_group": "rg1"},
        resource_type=ResourceType.NETWORK,
        native_id=native_id,
    )
    assert "%2F" not in urn
    assert parse_urn(urn).native_id == native_id


def test_empty_scope_is_valid() -> None:
    urn = build_urn(provider="aws", scope={}, resource_type=ResourceType.NETWORK, native_id="x")
    assert parse_urn(urn).scope == {}


def test_full_scope_emitted_in_fixed_key_order() -> None:
    scope = {
        "zone": "z1",
        "account_id": "acc1",
        "resource_group": "rg1",
        "tenant_id": "t1",
        "location": "loc1",
        "region": "r1",
        "subscription_id": "s1",
        "project_id": "p1",
    }
    urn = build_urn(provider="aws", scope=scope, resource_type=ResourceType.NETWORK, native_id="x")
    scope_segment = urn.split(":")[4]
    assert scope_segment == (
        "tenant_id=t1,account_id=acc1,subscription_id=s1,project_id=p1,"
        "region=r1,location=loc1,zone=z1,resource_group=rg1"
    )


def test_determinism_same_scope_dict_different_insertion_order() -> None:
    urn_a = build_urn(
        provider="aws",
        scope={"account_id": "1", "region": "r"},
        resource_type=ResourceType.NETWORK,
        native_id="x",
    )
    urn_b = build_urn(
        provider="aws",
        scope={"region": "r", "account_id": "1"},
        resource_type=ResourceType.NETWORK,
        native_id="x",
    )
    assert urn_a == urn_b


def test_absent_scope_keys_omitted_not_emitted_empty() -> None:
    urn = build_urn(
        provider="aws", scope={"account_id": "1"}, resource_type=ResourceType.NETWORK, native_id="x"
    )
    assert "region=" not in urn


def test_unknown_scope_key_raises() -> None:
    with pytest.raises(ValueError, match="Unknown scope key"):
        build_urn(
            provider="aws",
            scope={"not_a_real_key": "1"},
            resource_type=ResourceType.NETWORK,
            native_id="x",
        )


def test_empty_native_id_raises() -> None:
    with pytest.raises(ValueError, match="native_id must be non-empty"):
        build_urn(provider="aws", scope={}, resource_type=ResourceType.NETWORK, native_id="")


def test_resource_type_accepts_plain_string_too() -> None:
    urn = build_urn(provider="aws", scope={}, resource_type="network", native_id="x")
    assert parse_urn(urn).resource_type == "network"


def test_parse_malformed_urn_wrong_field_count_raises() -> None:
    with pytest.raises(ValueError, match="Malformed URN"):
        parse_urn("urn:mcnet:v1:aws:only-four-fields")


def test_parse_wrong_namespace_raises() -> None:
    with pytest.raises(ValueError, match="Not a mcnet URN"):
        parse_urn("urn:notmcnet:v1:aws::network:x")


def test_parse_empty_native_id_raises() -> None:
    with pytest.raises(ValueError, match="empty native_id"):
        parse_urn("urn:mcnet:v1:aws::network:")


def test_parse_malformed_scope_component_raises() -> None:
    with pytest.raises(ValueError, match="no '='"):
        parse_urn("urn:mcnet:v1:aws:not-a-kv-pair:network:x")


def test_parse_unknown_scope_key_in_urn_raises() -> None:
    with pytest.raises(ValueError, match="Unknown scope key"):
        parse_urn("urn:mcnet:v1:aws:bogus_key=1:network:x")


def test_scope_dict_extracts_from_cloud_scope(aws_scope) -> None:
    extracted = scope_dict(aws_scope)
    assert extracted == {"account_id": "123456789012", "region": "us-east-1"}


def test_scope_dict_omits_none_fields(azure_scope) -> None:
    extracted = scope_dict(azure_scope)
    assert "account_id" not in extracted
    assert "project_id" not in extracted
    assert extracted["subscription_id"] == "1e2d3c4b-5a69-4788-9f01-234567890abc"
    assert extracted["location"] == "eastus"
