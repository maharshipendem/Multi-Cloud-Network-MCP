"""Service-layer function for private services access allocated IP
ranges -- a filtered, derived view over
``gcp.addresses.list_global_addresses`` (see models module docstring for
why the *connection* half of this feature isn't covered here)."""

from __future__ import annotations

from gcp_network_mcp.gcp.addresses import list_global_addresses
from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.models.private_service_access import PrivateServiceAccessRange

_VPC_PEERING_PURPOSE = "VPC_PEERING"


def list_private_service_access_ranges(
    client_factory: ClientFactory, *, project_id: str
) -> list[PrivateServiceAccessRange]:
    addresses = list_global_addresses(client_factory, project_id=project_id)
    return [
        PrivateServiceAccessRange(
            self_link=a.self_link,
            name=a.name,
            project_id=project_id,
            address=a.address,
            prefix_length=a.prefix_length,
            network_self_link=a.network_self_link,
            status=a.status,
        )
        for a in addresses
        if a.purpose == _VPC_PEERING_PURPOSE
    ]


__all__ = ["list_private_service_access_ranges"]
