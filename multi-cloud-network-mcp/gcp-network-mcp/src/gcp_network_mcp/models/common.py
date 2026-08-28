"""Normalized domain models returned by the GCP service layer.

These models are the contract between the GCP service layer and the tool
layer, and (once serialized) the contract handed back to MCP clients. They
are intentionally cloud-agnostic in *shape* (mirroring the response
envelope concept from this project's AWS/Azure siblings) while every field
name stays GCP-native (``self_link``/``project_id``/``region``/``zone``
rather than forcing an AWS/Azure vocabulary onto GCP concepts). A future
Milestone 9 unifies naming/schemas across clouds; this milestone
deliberately does not attempt that.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

Labels = dict[str, str]

_SELF_LINK_RE = re.compile(
    r"^https://www\.googleapis\.com/compute/v\d+/projects/(?P<project_id>[^/]+)/"
    r"(?:"
    r"(?P<scope_type>global)"
    r"|(?P<region_type>regions)/(?P<region>[^/]+)"
    r"|(?P<zone_type>zones)/(?P<zone>[^/]+)"
    r")/(?P<resource_type>[^/]+)/(?P<resource_name>[^/]+)$"
)


class CollectionWarning(BaseModel):
    """A non-fatal issue encountered while collecting one resource type.

    Used whenever a tool returns a *partial* result rather than failing
    outright -- e.g. a disabled API, missing IAM permission for one
    resource type/scope, or a bounded fan-out cap being reached. A
    disabled API or missing permission must never be silently treated as
    "this project has zero instances of this resource type"; it must
    surface here instead.
    """

    resource_type: str
    code: str
    message: str
    project_id: str | None = None
    scope: str | None = None


class GcpResource(BaseModel):
    """Fields every normalized GCP resource record carries.

    ``self_link`` is the full GCP API self-link, preserved exactly as GCP
    returned it. ``project_id`` is always set (GCP resources are always
    project-scoped, even "global" ones). ``region``/``zone`` are both
    nullable: a global resource (e.g. a Network) has neither; a regional
    resource (e.g. a Subnetwork) has only ``region``; a zonal resource
    (e.g. an Instance) has only ``zone``.

    ``observed_at`` is the collection timestamp (ISO 8601, UTC), not a
    live/real-time value. ``source_api`` names the specific GCP client
    library operation that produced this record, for provenance.
    ``collection_completeness`` flags a record assembled from a partial
    response (e.g. an enrichment call that hit a fan-out cap).
    """

    self_link: str | None = None
    id: str | None = None
    name: str
    project_id: str
    region: str | None = None
    zone: str | None = None
    labels: Labels = Field(default_factory=dict)
    observed_at: str
    source_api: str | None = None
    collection_completeness: str = "complete"


class ParsedSelfLink(BaseModel):
    """The scoping fields decoded out of a GCP Compute Engine self-link."""

    project_id: str | None = None
    scope: str | None = None  # "global", or "regions/<region>", or "zones/<zone>"
    region: str | None = None
    zone: str | None = None
    resource_type: str | None = None
    resource_name: str | None = None


def parse_self_link(self_link: str) -> ParsedSelfLink:
    """Decode ``project_id``/``region``/``zone``/... out of a GCP Compute
    Engine self-link (``https://www.googleapis.com/compute/v1/projects/
    {project}/(global|regions/{region}|zones/{zone})/{type}/{name}``).

    Returns a ``ParsedSelfLink`` with all fields ``None`` if ``self_link``
    doesn't match the expected shape, never raises -- a malformed or
    unexpected self-link should degrade to missing metadata, not fail the
    whole tool call.
    """
    match = _SELF_LINK_RE.match(self_link)
    if not match:
        return ParsedSelfLink()
    groups = match.groupdict()
    scope: str | None
    if groups.get("scope_type"):
        scope = "global"
    elif groups.get("region_type"):
        scope = f"regions/{groups['region']}"
    elif groups.get("zone_type"):
        scope = f"zones/{groups['zone']}"
    else:
        scope = None
    return ParsedSelfLink(
        project_id=groups.get("project_id"),
        scope=scope,
        region=groups.get("region"),
        zone=groups.get("zone"),
        resource_type=groups.get("resource_type"),
        resource_name=groups.get("resource_name"),
    )


__all__ = [
    "CollectionWarning",
    "GcpResource",
    "Labels",
    "ParsedSelfLink",
    "parse_self_link",
]
