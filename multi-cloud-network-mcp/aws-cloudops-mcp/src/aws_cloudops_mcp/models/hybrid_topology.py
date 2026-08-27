"""Typed graph model for ``aws_get_hybrid_topology``.

Reuses Milestone 2's ``TopologyNode``/``TopologyEdge`` shape (id, type,
label, evidence-backed edges) -- the node/edge contract generalizes
cleanly from a single VPC to a Transit Gateway-anchored hybrid graph.
Only the result container is new.

Node types this graph can produce, beyond Milestone 2's VPC-scoped set:
``transit_gateway``, ``transit_gateway_route_table``,
``transit_gateway_attachment``, ``vpn_connection``, ``customer_gateway``,
``direct_connect_gateway``, ``hosted_zone``, ``resolver_endpoint``, and
``external_endpoint`` -- the last is this milestone's explicit label for a
genuinely non-AWS entity (an on-premises device's public IP, a static
route's destination network) that the graph can name but not further
resolve, per the milestone's "labeling unresolved external endpoints"
requirement. This is distinct from an *orphan reference* (an edge whose
target has no node at all, used for AWS-domain resources outside this
milestone's scope, e.g. a cross-account peer Transit Gateway) --
``external_endpoint`` nodes exist specifically so a non-AWS network
boundary is visible in the graph, not merely absent.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import CollectionWarning
from aws_cloudops_mcp.models.topology import TopologyEdge, TopologyNode

__all__ = ["HybridTopology", "TopologyEdge", "TopologyNode"]


class HybridTopology(BaseModel):
    """The full joined graph anchored on one Transit Gateway."""

    transit_gateway_id: str
    region: str
    nodes: list[TopologyNode] = Field(default_factory=list)
    edges: list[TopologyEdge] = Field(default_factory=list)
    warnings: list[CollectionWarning] = Field(default_factory=list)
    api_call_count: int = 0
