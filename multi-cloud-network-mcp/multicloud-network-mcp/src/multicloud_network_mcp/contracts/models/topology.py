"""Topology graph: nodes/edges with stable URNs, native IDs,
relationships, source evidence, ownership, and unresolved references.

Mirrors the node/edge/evidence contract all three cloud repos'
``VpcTopology``/``VnetTopology``/``HybridTopology`` models already share
almost verbatim, unified onto stable cross-cloud ``urn``s and a formal
``NodeKind`` (see ``enums.py``'s docstring for why AWS's
``external_endpoint`` convention, Azure's free-form ``node_type``
strings, and GCP's ``OUT_OF_SCOPE_TARGET`` warning code all collapse
onto one explicit field here).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from multicloud_network_mcp.contracts.models.common import (
    CloudScope,
    Ownership,
    SourceEvidence,
    Tags,
)
from multicloud_network_mcp.contracts.models.enums import Completeness, NodeKind
from multicloud_network_mcp.contracts.models.envelope import CollectionWarning


class TopologyNode(BaseModel):
    """One node in the graph.

    ``resource_type`` is ``str`` (not the strict ``ResourceType`` enum,
    see ``enums.py``) and ``None`` only when ``kind`` is ``EXTERNAL`` or
    ``UNRESOLVED`` and no canonical type meaningfully applies (e.g. a
    bare on-premises IP terminating a VPN tunnel). ``scope`` is ``None``
    for an ``EXTERNAL`` node with no cloud scope at all -- it is always
    present for ``RESOURCE`` nodes.
    """

    urn: str
    native_id: str
    kind: NodeKind
    resource_type: str | None = None
    label: str
    scope: CloudScope | None = None
    ownership: Ownership | None = None
    tags: Tags = Field(default_factory=dict)
    extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    """One typed relationship between two nodes, addressed by URN
    (never by a provider-native ID alone -- an edge between resources in
    two different scopes must be unambiguous without extra context).

    ``relationship`` is free text describing the edge's kind (e.g.
    ``"routes_to"``, ``"protected_by"``, ``"attached_to"``,
    ``"peers_with"``, ``"member_of"``, ``"resolves_to"``,
    ``"load_balances"``, ``"terminates_at"``, ``"propagates_to"`` --
    see ``docs/normalization.md`` for the recommended vocabulary); kept
    open rather than a closed enum since real cross-cloud relationship
    kinds are too varied to enumerate exhaustively without this contract
    constantly chasing new provider features.

    ``evidence`` is always at least one specific, already-observed fact
    (never an inference) that established this edge -- the same
    discipline every cloud repo's own topology builder already follows.
    """

    source_urn: str
    target_urn: str
    relationship: str
    evidence: list[SourceEvidence] = Field(min_length=1)


class TopologyGraph(BaseModel):
    """A deterministic node/edge graph over one collection scope.

    ``completeness`` is ``PARTIAL`` whenever ``warnings`` is non-empty --
    enforced at construction time (raises ``ValueError``), never silently
    ``COMPLETE`` alongside a recorded warning. Nodes and edges should
    always be emitted in a stable, deterministic order (sorted by
    ``urn``/``(source_urn, target_urn, relationship)``) so repeated calls
    against unchanged infrastructure produce byte-identical output -- the
    same discipline every cloud repo's own topology tool already
    follows.
    """

    scope: CloudScope
    completeness: Completeness = Completeness.COMPLETE
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)
    api_call_count: int = 0

    @model_validator(mode="after")
    def _partial_whenever_warnings_present(self) -> TopologyGraph:
        if self.warnings and self.completeness != Completeness.PARTIAL:
            raise ValueError(
                "completeness must be PARTIAL whenever warnings is non-empty "
                f"(got completeness={self.completeness!r} with {len(self.warnings)} warning(s))"
            )
        return self


__all__ = ["TopologyEdge", "TopologyGraph", "TopologyNode"]
