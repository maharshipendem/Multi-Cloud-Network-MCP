"""Shared building blocks every resource/topology/diagnostic model in
this contract is built from: cloud scope, evidence, ownership, and the
extension-preservation contract.

**Extension preservation is not optional.** Every model that represents
a real cloud resource carries an ``extensions: dict[str, Any]`` field,
namespaced by provider (``extensions["aws"]``/``["azure"]``/``["gcp"]``),
for provider-native facts this schema has no first-class property for.
An adapter must never drop a fact merely because the common schema
lacks a matching field -- see ``docs/normalization.md``'s "never
silently coerce unknown data" guardrail and
``tests/contracts/test_extensions_preserved.py``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from multicloud_network_mcp.contracts.models.enums import Provider

Tags = dict[str, str]


class CloudScope(BaseModel):
    """Where a fact was observed: which provider, which tenancy
    boundary, which geography, and when. Every field beyond ``provider``
    and ``collected_at`` is optional because no single provider
    populates all of them -- see the field-by-field mapping below and
    ``docs/normalization.md``.

    - ``tenant_id``: Azure AD tenant. Rarely meaningful for AWS/GCP.
    - ``account_id``: AWS account ID (12 digits).
    - ``subscription_id``: Azure subscription GUID.
    - ``project_id``: GCP project ID.
    - ``resource_group``: Azure resource group -- kept as its own field
      (not folded into ``extensions``) because Azure resource identity is
      genuinely incomplete without it, unlike a merely-supplementary fact.
    - ``region``: AWS/GCP-style region (``us-east-1``/``us-central1``).
    - ``location``: Azure's own term for the same granularity (ARM
      responses literally use the JSON field name ``location``, not
      ``region``) -- kept as a separate field rather than aliased onto
      ``region``, since forcing Azure's ``location`` string into a field
      named ``region`` would misrepresent which provider vocabulary it
      came from.
    - ``zone``: availability-zone-level granularity, when the provider
      exposes it (AWS AZ, Azure zone number, GCP zone).
    - ``collected_at``: ISO 8601 UTC timestamp this scope's data was
      observed at -- never a live/real-time value.
    """

    provider: Provider
    tenant_id: str | None = None
    account_id: str | None = None
    subscription_id: str | None = None
    project_id: str | None = None
    resource_group: str | None = None
    region: str | None = None
    location: str | None = None
    zone: str | None = None
    collected_at: str


class Ownership(BaseModel):
    """Who owns/is billed for a resource, when that differs from the
    scope it was *collected* under -- e.g. a cross-account VPC peering
    accepter, a cross-subscription hub connection, a GCP Shared VPC
    service project referencing a host project's network. Absent when
    ownership and collection scope are the same (the overwhelmingly
    common case)."""

    owner_account_id: str | None = None
    owner_subscription_id: str | None = None
    owner_project_id: str | None = None
    owner_tenant_id: str | None = None


class SourceEvidence(BaseModel):
    """One specific, already-collected fact a topology edge or
    diagnostic finding's reasoning relies on -- never an inference
    dressed up as an observation. Identical shape to what all three
    cloud repos' own diagnostics engines already call ``Evidence``;
    renamed ``SourceEvidence`` here only to avoid colliding with this
    module's own vocabulary once re-exported alongside ``CloudScope``/
    ``Ownership``.

    ``source`` identifies exactly which provider-native record the fact
    came from (e.g. ``"route_table:rtb-0123"``,
    ``"firewall_rule:allow-internal@vpc-1"``); ``detail`` is the
    specific field/value that was observed.
    """

    source: str
    detail: str


class ExtensibleModel(BaseModel):
    """Base for every model that represents a real provider fact and
    therefore must be able to carry provider-native data the common
    schema doesn't model. ``extensions`` is namespaced by provider slug
    (``"aws"``/``"azure"``/``"gcp"``) so a consumer reading it always
    knows which provider's vocabulary a given nested value uses --
    ``extensions.get("azure", {}).get("provisioningState")``, never a
    flat unnamespaced bag. An adapter populating a canonical field with
    a lossy/best-effort mapping should still put the *original* raw
    value under ``extensions`` even when a canonical field exists, if
    the mapping was not a lossless 1:1 rename -- see
    ``docs/normalization.md``."""

    extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator("extensions")
    @classmethod
    def _namespaced_by_known_provider(
        cls, value: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        unknown = set(value) - {p.value for p in Provider}
        if unknown:
            raise ValueError(
                f"extensions must be namespaced by a known provider slug, got: {sorted(unknown)}"
            )
        return value


__all__ = [
    "CloudScope",
    "ExtensibleModel",
    "Ownership",
    "SourceEvidence",
    "Tags",
]
