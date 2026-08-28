"""Typed node/edge graph model for ``azure_get_vnet_topology``."""

from __future__ import annotations

from pydantic import BaseModel, Field

from azure_network_mcp.models.common import CollectionWarning, Tags


class TopologyNode(BaseModel):
    node_id: str
    node_type: str
    label: str
    virtual_network_name: str | None = None
    resource_group: str | None = None
    tags: Tags = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    """One typed relationship between two nodes.

    ``evidence`` is always a specific observed field value (e.g. "subnet
    my-subnet NetworkSecurityGroup.id=..."), never an inference --
    matching the same evidence discipline this project's AWS sibling
    established for its own topology tool.
    """

    source_id: str
    target_id: str
    relationship: str
    evidence: str


class VnetTopology(BaseModel):
    virtual_network_name: str
    resource_group: str
    subscription_id: str
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)
    api_call_count: int = 0


class HybridTopology(BaseModel):
    """Typed node/edge graph for ``azure_get_hybrid_topology`` -- a whole
    resource group's VNets joined with vWAN hubs, VPN gateways/
    connections, and ExpressRoute circuits/gateways/connections, produced
    by ``diagnostics.hybrid_topology``. Broader in scope than
    ``VnetTopology`` (many VNets, hybrid connectivity included) but the
    same node/edge/evidence contract."""

    resource_group: str
    subscription_id: str
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)


__all__ = ["HybridTopology", "TopologyEdge", "TopologyNode", "VnetTopology"]
