"""Extension preservation: a provider-native fact this contract has no
first-class field for must survive intact in ``extensions[provider]``,
namespaced correctly, and an unrecognized namespace is rejected rather
than silently accepted (which would defeat the point of namespacing)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from multicloud_network_mcp.contracts.models import Network, Provider
from multicloud_network_mcp.contracts.urn import build_urn

FRESHNESS = "2026-01-01T00:00:00+00:00"


def _urn() -> str:
    return build_urn(
        provider="aws", scope={"account_id": "1"}, resource_type="network", native_id="vpc-1"
    )


def test_extensions_preserved_through_round_trip(aws_scope) -> None:
    network = Network(
        urn=_urn(),
        native_id="vpc-1",
        resource_type="network",
        provider=Provider.AWS,
        scope=aws_scope,
        observed_at=FRESHNESS,
        cidr_blocks=["10.0.0.0/16"],
        state="available",
        extensions={
            "aws": {
                "InstanceTenancy": "default",
                "DhcpOptionsId": "dopt-0123456789abcdef0",
                "EnableDnsSupport": True,
            }
        },
    )
    dumped = network.model_dump_json()
    reloaded = Network.model_validate_json(dumped)
    assert reloaded.extensions == {
        "aws": {
            "InstanceTenancy": "default",
            "DhcpOptionsId": "dopt-0123456789abcdef0",
            "EnableDnsSupport": True,
        }
    }


def test_extensions_can_carry_arbitrarily_nested_structure(aws_scope) -> None:
    nested = {"a": {"b": [1, 2, {"c": "d"}]}, "e": None}
    network = Network(
        urn=_urn(),
        native_id="vpc-1",
        resource_type="network",
        provider=Provider.AWS,
        scope=aws_scope,
        observed_at=FRESHNESS,
        state="available",
        extensions={"aws": nested},
    )
    reloaded = Network.model_validate_json(network.model_dump_json())
    assert reloaded.extensions["aws"] == nested


def test_extensions_default_empty(aws_scope) -> None:
    network = Network(
        urn=_urn(),
        native_id="vpc-1",
        resource_type="network",
        provider=Provider.AWS,
        scope=aws_scope,
        observed_at=FRESHNESS,
        state="available",
    )
    assert network.extensions == {}


def test_extensions_rejects_unknown_provider_namespace(aws_scope) -> None:
    with pytest.raises(ValidationError, match="known provider slug"):
        Network(
            urn=_urn(),
            native_id="vpc-1",
            resource_type="network",
            provider=Provider.AWS,
            scope=aws_scope,
            observed_at=FRESHNESS,
            state="available",
            extensions={"not_a_real_provider": {"x": 1}},
        )


def test_extensions_can_carry_multiple_provider_namespaces_at_once(aws_scope) -> None:
    # Rare but legitimate: a resource whose provenance spans more than
    # one provider's own raw data (e.g. a cross-cloud-peering adapter
    # enriching one side with the peer provider's facts too).
    network = Network(
        urn=_urn(),
        native_id="vpc-1",
        resource_type="network",
        provider=Provider.AWS,
        scope=aws_scope,
        observed_at=FRESHNESS,
        state="available",
        extensions={"aws": {"x": 1}, "azure": {"y": 2}},
    )
    assert set(network.extensions) == {"aws", "azure"}
