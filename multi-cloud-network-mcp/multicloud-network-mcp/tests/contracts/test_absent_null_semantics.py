"""Absent vs. null semantics: an optional field genuinely omitted from
a payload (never observed by the provider) must default identically to
one explicitly sent as JSON ``null`` -- the two are not distinguished
anywhere in this contract, by design (no field uses Pydantic's
``PydanticUndefined``-vs-``None`` sentinel distinction), which keeps
"the provider didn't return this" and "the provider returned nothing
for this" from becoming two different states an adapter has to reason
about."""

from __future__ import annotations

import json

from multicloud_network_mcp.contracts.models import CloudScope, Network, Provider
from multicloud_network_mcp.contracts.urn import build_urn

FRESHNESS = "2026-01-01T00:00:00+00:00"


def _urn() -> str:
    return build_urn(provider="aws", scope={}, resource_type="network", native_id="vpc-1")


def _base(scope: CloudScope) -> dict:
    return {
        "urn": _urn(),
        "native_id": "vpc-1",
        "resource_type": "network",
        "provider": scope.provider.value,
        "scope": scope.model_dump(mode="json"),
        "observed_at": FRESHNESS,
        "state": "available",
    }


def test_omitted_optional_field_defaults_same_as_explicit_null(aws_scope) -> None:
    omitted = Network.model_validate(_base(aws_scope))
    explicit_null = Network.model_validate({**_base(aws_scope), "name": None})
    assert omitted.name is None
    assert explicit_null.name is None
    assert omitted.name == explicit_null.name


def test_omitted_list_field_defaults_to_empty_list_not_none(aws_scope) -> None:
    network = Network.model_validate(_base(aws_scope))
    assert network.cidr_blocks == []
    assert network.tags == {}
    assert network.extensions == {}


def test_cloud_scope_optional_fields_all_default_to_none() -> None:
    scope = CloudScope(provider=Provider.GCP, project_id="p1", collected_at=FRESHNESS)
    assert scope.tenant_id is None
    assert scope.account_id is None
    assert scope.subscription_id is None
    assert scope.resource_group is None
    assert scope.region is None
    assert scope.location is None
    assert scope.zone is None


def test_serialized_omitted_field_round_trips_to_null_in_json(aws_scope) -> None:
    network = Network.model_validate(_base(aws_scope))
    dumped = json.loads(network.model_dump_json())
    # Pydantic serializes an unset-with-default Optional field as
    # explicit `null`, not by omitting the key -- confirm that's the
    # wire behavior a consumer should expect (a key's absence from the
    # dumped JSON would mean something different -- excluded entirely --
    # and this contract's own dumps never do that by default).
    assert "name" in dumped
    assert dumped["name"] is None


def test_a_payload_missing_the_key_entirely_still_parses_correctly(aws_scope) -> None:
    payload = _base(aws_scope)
    assert "name" not in payload  # never set at all, not even to None
    network = Network.model_validate(payload)
    assert network.name is None
