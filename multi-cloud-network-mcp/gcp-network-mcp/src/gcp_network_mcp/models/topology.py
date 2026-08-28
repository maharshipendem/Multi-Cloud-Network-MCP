"""Typed node/edge graph model for ``gcp_get_vpc_topology``."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import CollectionWarning, Labels


class TopologyNode(BaseModel):
    node_id: str
    node_type: str
    label: str
    project_id: str | None = None
    region: str | None = None
    zone: str | None = None
    labels: Labels = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    """One typed relationship between two nodes.

    ``evidence`` is always a specific observed field value (e.g.
    "subnetwork my-subnet.network=projects/p/global/networks/my-vpc"),
    never an inference.
    """

    source_id: str
    target_id: str
    relationship: str
    evidence: str


class VpcTopology(BaseModel):
    """A deterministic node/edge graph over one project's VPC networking,
    joining Networks, Subnetworks, Routes, Firewall rules/policies,
    instances' network interfaces, Cloud NAT, and VPC peerings.

    ``completeness`` is ``"complete"`` unless a partial-result warning was
    recorded while collecting any joined resource type, in which case it
    is ``"partial"`` -- never silently downgraded to an empty graph.
    ``observed_at`` is the single collection timestamp shared by every
    node/edge in the graph (not a live/real-time value). Nodes and edges
    are always emitted in a stable, deterministic order (sorted by
    ``node_id``/``(source_id, target_id, relationship)``) so repeated
    calls against unchanged infrastructure produce byte-identical output.
    """

    project_id: str
    observed_at: str
    completeness: str = "complete"
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)
    api_call_count: int = 0


class HybridTopology(BaseModel):
    """Typed node/edge graph for ``gcp_get_hybrid_topology`` -- one
    project's VPC networking joined with NCC hubs/spokes, VPN gateways/
    tunnels, and Interconnect attachments, produced by
    ``diagnostics.hybrid_topology``. Broader in scope than ``VpcTopology``
    (hybrid connectivity included) but the same node/edge/evidence
    contract."""

    project_id: str
    observed_at: str
    completeness: str = "complete"
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)


__all__ = ["HybridTopology", "TopologyEdge", "TopologyNode", "VpcTopology"]
