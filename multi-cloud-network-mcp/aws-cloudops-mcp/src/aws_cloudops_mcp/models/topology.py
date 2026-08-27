"""Typed graph models for ``aws_get_vpc_topology``.

The topology tool joins every other resource type in this milestone into a
single node/edge graph. Nodes and edges are deliberately thin (an id, a
type, and a small set of display fields) -- the full resource record is
still available from its own dedicated list tool; the graph's job is to
state *relationships*, not duplicate every field of every resource.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import CollectionWarning, Tags


class TopologyNode(BaseModel):
    """One resource in the topology graph.

    ``node_id`` is the resource's own AWS ID (e.g. a VPC ID, subnet ID) so
    edges can reference nodes without duplicating resource data.
    ``node_type`` is one of: vpc, subnet, route_table, internet_gateway,
    egress_only_internet_gateway, nat_gateway, security_group, network_acl,
    network_interface, vpc_peering_connection, vpc_endpoint, load_balancer,
    target_group.
    """

    node_id: str
    node_type: str
    label: str
    vpc_id: str | None = None
    region: str
    tags: Tags = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    """One relationship between two topology nodes.

    ``evidence`` names the specific field/API response that established
    this edge (e.g. ``"route_table rtb-123 route -> igw-abc via GatewayId"``)
    so the edge is auditable back to a concrete AWS API observation rather
    than an inferred/guessed relationship.
    """

    source_id: str
    target_id: str
    relationship: str
    evidence: str


class VpcTopology(BaseModel):
    """The full joined graph for one VPC."""

    vpc_id: str
    region: str
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)
    api_call_count: int = 0


__all__ = ["TopologyEdge", "TopologyNode", "VpcTopology"]
