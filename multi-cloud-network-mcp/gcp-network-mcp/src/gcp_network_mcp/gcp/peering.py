"""Service-layer function for VPC Network Peering.

GCP has no dedicated peering-listing API -- peerings are embedded on
each ``Network``'s ``peerings`` field, so listing every peering in a
project means listing every Network and flattening their embedded
peerings.
"""

from __future__ import annotations

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.networking import extract_peerings
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.models.peering import NetworkPeering


def list_network_peerings(
    client_factory: ClientFactory, *, project_id: str
) -> list[NetworkPeering]:
    raw_networks = paginate(
        client_factory.networks(),
        "list",
        resource_type="network",
        project_id=project_id,
        project=project_id,
    )
    peerings: list[NetworkPeering] = []
    for network in raw_networks:
        peerings.extend(extract_peerings(network))
    return peerings


__all__ = ["list_network_peerings"]
