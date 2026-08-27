"""ARM service layer: VNet peerings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import VirtualNetworkPeering

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_virtual_network_peerings(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_network_name: str,
) -> list[VirtualNetworkPeering]:
    """Call VirtualNetworkPeeringsOperations.list for one VNet.

    ``peering_state`` (Initiated/Connected/Disconnected) is Azure's own
    connection-state field -- a peering only passes traffic when both
    sides show ``Connected``.
    """
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.virtual_network_peerings,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        virtual_network_name=virtual_network_name,
    )
    result = []
    for peering in raw:
        parsed = parse_resource_id(peering.id)
        result.append(
            VirtualNetworkPeering(
                resource_id=peering.id,
                name=peering.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                provisioning_state=getattr(peering, "provisioning_state", None),
                observed_at=observed_at,
                source_api="Microsoft.Network/virtualNetworks/virtualNetworkPeerings",
                virtual_network_name=virtual_network_name,
                remote_virtual_network_id=(
                    peering.remote_virtual_network.id if peering.remote_virtual_network else None
                ),
                remote_address_space=list(
                    (peering.remote_address_space.address_prefixes or [])
                    if peering.remote_address_space
                    else []
                ),
                peering_state=getattr(peering, "peering_state", None),
                peering_sync_level=getattr(peering, "peering_sync_level", None),
                allow_virtual_network_access=getattr(peering, "allow_virtual_network_access", None),
                allow_forwarded_traffic=getattr(peering, "allow_forwarded_traffic", None),
                allow_gateway_transit=getattr(peering, "allow_gateway_transit", None),
                use_remote_gateways=getattr(peering, "use_remote_gateways", None),
            )
        )
    return result


__all__ = ["list_virtual_network_peerings"]
