"""Compatibility test proving the previous supported minor version
still parses -- and, symmetrically, that the major/minor boundary
rules ``negotiate()`` documents are actually enforced, not just
described in ``docs/versioning.md``."""

from __future__ import annotations

from multicloud_network_mcp.contracts.models.capability import (
    ProviderCapabilityManifest,
    ResourceTypeSupport,
    negotiate,
)
from multicloud_network_mcp.contracts.version import CONTRACT_VERSION

FRESHNESS = "2026-01-01T00:00:00+00:00"


def _manifest(*, contract_version: str, min_supported: str) -> ProviderCapabilityManifest:
    return ProviderCapabilityManifest(
        provider="aws",
        adapter_package="aws-cloudops-mcp",
        adapter_version="0.4.0",
        contract_version=contract_version,
        min_supported_contract_version=min_supported,
        urn_grammar_version=1,
        supported_resource_types=[
            ResourceTypeSupport(
                resource_type="network", export_tool="aws_export_normalized_topology"
            )
        ],
        supports_topology=True,
        generated_at=FRESHNESS,
    )


def test_current_contract_version_is_self_compatible() -> None:
    manifest = _manifest(contract_version=CONTRACT_VERSION, min_supported=CONTRACT_VERSION)
    result = negotiate(manifest, consumer_contract_version=CONTRACT_VERSION)
    assert result.compatible is True
    assert result.reason is None


def test_a_consumer_built_against_the_previous_minor_still_parses() -> None:
    # The concrete proof this test module exists for: an adapter that
    # has moved on to 1.1.0 but still declares it supports 1.0.0-built
    # consumers must actually negotiate successfully against one.
    manifest = _manifest(contract_version="1.1.0", min_supported="1.0.0")
    result = negotiate(manifest, consumer_contract_version="1.0.0")
    assert result.compatible is True


def test_a_consumer_older_than_the_manifests_minimum_is_incompatible() -> None:
    manifest = _manifest(contract_version="1.2.0", min_supported="1.1.0")
    result = negotiate(manifest, consumer_contract_version="1.0.0")
    assert result.compatible is False
    assert "older than" in result.reason


def test_a_consumer_newer_than_the_manifests_own_contract_version_is_incompatible() -> None:
    manifest = _manifest(contract_version="1.0.0", min_supported="1.0.0")
    result = negotiate(manifest, consumer_contract_version="1.1.0")
    assert result.compatible is False
    assert "newer than" in result.reason


def test_different_major_versions_are_always_incompatible_regardless_of_minor() -> None:
    manifest = _manifest(contract_version="2.5.0", min_supported="2.0.0")
    result = negotiate(manifest, consumer_contract_version="1.9.0")
    assert result.compatible is False
    assert "major version mismatch" in result.reason


def test_exact_same_minor_is_compatible() -> None:
    manifest = _manifest(contract_version="1.3.2", min_supported="1.0.0")
    result = negotiate(manifest, consumer_contract_version="1.3.0")
    assert result.compatible is True


def test_malformed_manifest_min_supported_major_mismatch_reported() -> None:
    # A manifest whose own min_supported_contract_version claims a
    # different major than its own contract_version is malformed --
    # negotiate() must flag it, not silently misbehave.
    manifest = _manifest(contract_version="2.0.0", min_supported="1.0.0")
    result = negotiate(manifest, consumer_contract_version="2.0.0")
    assert result.compatible is False
    assert "malformed manifest" in result.reason
