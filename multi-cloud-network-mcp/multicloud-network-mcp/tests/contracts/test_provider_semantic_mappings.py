"""Provider semantic mappings: the specific, documented cross-provider
differences from ``docs/normalization.md`` actually hold in the golden
examples -- not just described in prose, verified against real example
data. Each test here corresponds to one row/section of that document."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "contracts" / "examples"


def _load(provider: str, slug_prefix: str) -> list[dict]:
    matches = sorted((_EXAMPLES_DIR / provider).glob(f"{slug_prefix}.*.json"))
    return [json.loads(p.read_text()) for p in matches]


def test_aws_has_two_firewall_rule_examples_demonstrating_the_stateful_split() -> None:
    # AWS is the one provider with two distinct firewall mechanisms
    # (stateful Security Group rules, stateless NACL entries) mapped
    # onto the single canonical FirewallRule.stateful field.
    rules = _load("aws", "firewall-rule")
    assert len(rules) >= 2, "AWS should have at least two firewall-rule examples"
    stateful_values = {r["stateful"] for r in rules}
    assert stateful_values == {True, False}, (
        f"expected both stateful=True (Security Group) and stateful=False (NACL) "
        f"AWS examples, got {stateful_values}"
    )


@pytest.mark.parametrize("provider", ["azure", "gcp"])
def test_azure_and_gcp_firewall_rules_are_always_stateful(provider: str) -> None:
    rules = _load(provider, "firewall-rule")
    if not rules:
        pytest.skip(f"no firewall-rule examples for {provider}")
    assert all(r["stateful"] is True for r in rules), (
        f"{provider} has exactly one firewall mechanism, and it's always stateful"
    )


def test_aws_address_example_is_documented_as_synthesized() -> None:
    # AWS has no first-class Elastic IP resource -- the Address
    # example must exist (since the milestone wants full coverage)
    # but the accompanying NOTES.md must say so explicitly.
    notes = (_EXAMPLES_DIR / "aws" / "NOTES.md").read_text().lower()
    assert "synthes" in notes, "AWS's NOTES.md should document the Address example as synthesized"


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_no_vpn_tunnel_or_interconnect_example_leaks_a_secret_field(provider: str) -> None:
    for slug in ("vpn-tunnel", "interconnect", "interconnect-attachment"):
        for example in _load(provider, slug):
            serialized = json.dumps(example).lower()
            for forbidden in (
                "shared_secret",
                "sharedsecret",
                "pre_shared_key",
                "presharedkey",
                "pairing_key",
                "pairingkey",
                "authorization_key",
                "authorizationkey",
                "service_key",
                "servicekey",
            ):
                assert forbidden not in serialized, (
                    f"{provider} {slug} example contains a forbidden secret-shaped field name: "
                    f"{forbidden!r}"
                )
            if "redacted" in example:
                assert example["redacted"] is True


def test_gcp_route_example_has_unknown_origin_and_state_but_real_priority() -> None:
    routes = _load("gcp", "route")
    if not routes:
        pytest.skip("no GCP route examples yet")
    for route in routes:
        assert route["origin"] == "unknown", (
            "GCP has no Route.origin field to observe -- the canonical origin must "
            "normalize to 'unknown', never a guessed value"
        )
        assert route["state"] == "unknown"
        # priority is GCP's real strength here -- AWS/Azure have no
        # equivalent tie-break field at all.
        assert route.get("priority") is not None


@pytest.mark.parametrize("provider,slugs", [("gcp", ["dns-resolver", "dns-rule"])])
def test_gcp_has_no_dns_resolver_or_rule_examples(provider: str, slugs: list[str]) -> None:
    for slug in slugs:
        assert not _load(provider, slug), (
            f"{provider} should have zero {slug} examples -- it has no such resource "
            f"(see docs/normalization.md's DNS resolver/rule section)"
        )


def test_azure_transit_hub_example_has_its_own_cidr_unlike_aws_and_gcp() -> None:
    azure_hubs = _load("azure", "transit-hub")
    if not azure_hubs:
        pytest.skip("no Azure transit-hub examples yet")
    assert any(hub.get("cidr_blocks") for hub in azure_hubs), (
        "Azure's Virtual Hub is the one transit hub among the three providers with its "
        "own address_prefix -- at least one Azure transit-hub example should show it"
    )


def test_azure_cloud_scope_uses_location_not_region() -> None:
    for provider_examples_dir in (_EXAMPLES_DIR / "azure").glob("*.json"):
        if provider_examples_dir.name == "NOTES.md":
            continue
        data = json.loads(provider_examples_dir.read_text())
        scope = data.get("scope")
        if not isinstance(scope, dict):
            continue
        if scope.get("provider") == "azure":
            assert scope.get("region") is None, (
                f"{provider_examples_dir.name}: Azure scope must use 'location', never 'region'"
            )


def test_aws_dns_zone_example_has_no_region_since_route53_is_global() -> None:
    zones = _load("aws", "dns-zone")
    if not zones:
        pytest.skip("no AWS dns-zone examples yet")
    for zone in zones:
        assert zone["scope"].get("region") is None, (
            "Route 53 is a global service -- an AWS DnsZone example's scope should carry no region"
        )
