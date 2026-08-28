"""Provider capability manifest and protocol/schema version negotiation.

Each cloud repo's adapter publishes exactly one
``ProviderCapabilityManifest`` (as a normalized-export MCP tool's
result, e.g. ``gcp_get_contract_capabilities``) describing what it can
export in this contract's shape and against which contract version it
was last verified. A federation layer -- or any consumer -- calls
``negotiate()`` against a manifest before trusting its output, rather
than assuming compatibility.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from multicloud_network_mcp.contracts.models.enums import Provider, ResourceType


def _parse_semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".", 2)
    return int(major), int(minor), int(patch)


class ResourceTypeSupport(BaseModel):
    """One resource type's normalized-export coverage for a given
    provider -- which MCP tool produces it, and whether the mapping is
    exact or best-effort (see ``docs/normalization.md`` for what
    "best-effort" means for a given type -- e.g. AWS has no first-class
    Elastic IP resource, so its ``ADDRESS`` mapping is synthesized from
    nested fields, not a 1:1 export)."""

    resource_type: ResourceType
    export_tool: str
    exact_mapping: bool = True
    notes: str | None = None


class ProviderCapabilityManifest(BaseModel):
    """What one provider's adapter can do, as of one point in time.

    ``contract_version`` is the exact ``CONTRACT_VERSION`` this manifest
    was generated against; ``min_supported_contract_version`` is the
    oldest contract *minor* version (same major) this adapter still
    round-trips without error -- normally the previous minor release,
    per this contract's backward-compatibility policy (see
    ``docs/versioning.md``). A federation layer should call
    ``negotiate()`` rather than compare these strings itself.
    """

    provider: Provider
    adapter_package: str
    adapter_version: str
    contract_version: str
    min_supported_contract_version: str
    urn_grammar_version: int
    supported_resource_types: list[ResourceTypeSupport] = Field(default_factory=list)
    supports_topology: bool = False
    supports_diagnostics: bool = False
    supports_observability: bool = False
    generated_at: str


class NegotiationResult(BaseModel):
    compatible: bool
    reason: str | None = None
    """Populated only when ``compatible`` is False -- explains which
    check failed (major version mismatch, consumer requires a newer
    minor than the manifest supports, or vice versa)."""


def negotiate(
    manifest: ProviderCapabilityManifest, *, consumer_contract_version: str
) -> NegotiationResult:
    """Decide whether a consumer built against
    ``consumer_contract_version`` can safely use data produced by
    ``manifest``'s adapter.

    Compatible iff both versions share the same major (a major bump is
    the only kind of change allowed to break an existing consumer, per
    ``docs/versioning.md``) AND the manifest's own
    ``min_supported_contract_version..contract_version`` range covers
    the consumer's minor -- i.e. the consumer isn't older than what the
    adapter still supports, and isn't newer than what the adapter has
    been verified against.
    """
    manifest_major, manifest_minor, _ = _parse_semver(manifest.contract_version)
    min_major, min_minor, _ = _parse_semver(manifest.min_supported_contract_version)
    consumer_major, consumer_minor, _ = _parse_semver(consumer_contract_version)

    if consumer_major != manifest_major:
        return NegotiationResult(
            compatible=False,
            reason=(
                f"major version mismatch: consumer requires major {consumer_major}, "
                f"manifest is contract major {manifest_major}"
            ),
        )
    if min_major != manifest_major:
        return NegotiationResult(
            compatible=False,
            reason=(
                f"manifest's min_supported_contract_version "
                f"({manifest.min_supported_contract_version}) is a different major version "
                f"than its own contract_version ({manifest.contract_version}) -- malformed manifest"
            ),
        )
    if consumer_minor < min_minor:
        return NegotiationResult(
            compatible=False,
            reason=(
                f"consumer contract minor {consumer_minor} is older than the manifest's "
                f"minimum supported minor {min_minor}"
            ),
        )
    if consumer_minor > manifest_minor:
        return NegotiationResult(
            compatible=False,
            reason=(
                f"consumer contract minor {consumer_minor} is newer than what this manifest "
                f"was verified against (minor {manifest_minor}) -- the adapter may not yet "
                f"emit fields the consumer expects"
            ),
        )
    return NegotiationResult(compatible=True)


__all__ = [
    "NegotiationResult",
    "ProviderCapabilityManifest",
    "ResourceTypeSupport",
    "negotiate",
]
