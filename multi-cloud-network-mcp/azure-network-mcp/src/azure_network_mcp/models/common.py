"""Normalized domain models returned by the ARM service layer.

These models are the contract between the ARM service layer and the tool
layer, and (once serialized) the contract handed back to MCP clients. They
are intentionally cloud-agnostic in *shape* (mirroring the response
envelope concept from this project's AWS sibling) while every field name
stays Azure-native -- ``resource_group``/``location``/``provisioning_state``
rather than forcing an AWS vocabulary onto Azure concepts. A future
Milestone 9 unifies naming/schemas across clouds; this milestone
deliberately does not attempt that.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

Tags = dict[str, str]


class CollectionWarning(BaseModel):
    """A non-fatal issue encountered while collecting one resource type.

    Used whenever a tool returns a *partial* result rather than failing
    outright -- e.g. missing RBAC permission for one resource type, or a
    bounded fan-out cap being reached. A missing permission must never be
    silently treated as "this resource type has zero instances"; it must
    surface here instead.
    """

    resource_type: str
    code: str
    message: str


class AzureResource(BaseModel):
    """Fields every normalized Azure resource record carries.

    ``resource_id`` is the full ARM resource ID (e.g.
    ``/subscriptions/.../resourceGroups/.../providers/Microsoft.Network/
    virtualNetworks/...``), preserved exactly as Azure returned it --
    joins between resources (e.g. a subnet referencing its VNet's ID)
    must compare resource IDs case-*insensitively* (ARM itself treats
    resource IDs as case-insensitive for routing purposes, but does not
    normalize casing in its own responses), so callers doing such a join
    should use ``normalize_resource_id`` below rather than a direct
    string `==` comparison, while still displaying/returning the
    original-cased value.

    ``resource_group`` and ``location`` are both nullable: a subscription-
    or tenant-scoped resource (e.g. the subscription itself) has neither;
    a global Azure construct has no ``location``. ``provisioning_state``
    is Azure's own deployment-state field (``Succeeded``/``Failed``/
    ``Updating``/...) -- kept distinct from any resource-specific
    *operational* state field (e.g. a NAT gateway's own health), per this
    milestone's requirement to "distinguish provisioning state from
    operational state."

    ``observed_at`` is the collection timestamp (ISO 8601, UTC), not a
    live/real-time value. ``source_api`` names the specific Azure SDK
    operation that produced this record, for provenance.
    ``collection_completeness`` flags a record assembled from a partial
    response (e.g. an enrichment call that hit a fan-out cap).
    """

    resource_id: str
    name: str
    subscription_id: str
    resource_group: str | None = None
    location: str | None = None
    provisioning_state: str | None = None
    tags: Tags = Field(default_factory=dict)
    observed_at: str
    source_api: str | None = None
    collection_completeness: str = "complete"


def normalize_resource_id(resource_id: str) -> str:
    """Lowercase an ARM resource ID for case-insensitive comparison/joins.

    Never use this for a value returned to a client -- always return the
    original-cased ``resource_id`` from the record itself; this helper
    exists only for internal dict-key lookups and equality checks.
    """
    return resource_id.lower()


class ParsedResourceId(BaseModel):
    """The scoping fields decoded out of an ARM resource ID string."""

    subscription_id: str | None = None
    resource_group: str | None = None
    provider_namespace: str | None = None
    resource_type: str | None = None
    resource_name: str | None = None


def parse_resource_id(resource_id: str) -> ParsedResourceId:
    """Decode ``subscription_id``/``resource_group``/... out of an ARM
    resource ID (``/subscriptions/{sub}/resourceGroups/{rg}/providers/
    {provider}/{type}/{name}[/{childType}/{childName}...]``).

    Many child resources (a subnet, a security rule, a VNet peering) come
    back from the Azure SDK with only their own ``id``/``name`` -- no
    separate ``subscription_id``/``resource_group`` fields -- so this is
    the one place that logic lives, rather than being re-derived
    ad hoc by every normalizer. Returns a ``ParsedResourceId`` with all
    fields ``None`` if ``resource_id`` doesn't match the expected shape,
    never raises -- a malformed or unexpected ID should degrade to
    missing metadata, not fail the whole tool call.
    """
    parts = [p for p in resource_id.split("/") if p]
    fields: dict[str, str] = {}
    i = 0
    while i < len(parts) - 1:
        key, value = parts[i].lower(), parts[i + 1]
        if key == "subscriptions":
            fields["subscription_id"] = value
        elif key == "resourcegroups":
            fields["resource_group"] = value
        elif key == "providers":
            fields["provider_namespace"] = value
            # Everything after the provider namespace is type/name pairs;
            # the *last* pair is the resource this ID actually names (a
            # child resource's ID ends with its own type/name, not its
            # parent's).
            remaining = parts[i + 2 :]
            if len(remaining) >= 2:
                fields["resource_type"] = remaining[-2]
                fields["resource_name"] = remaining[-1]
            break
        i += 2
    return ParsedResourceId(**fields)


__all__ = [
    "AzureResource",
    "CollectionWarning",
    "ParsedResourceId",
    "Tags",
    "normalize_resource_id",
    "parse_resource_id",
]
