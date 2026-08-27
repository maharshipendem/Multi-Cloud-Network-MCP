"""ARM service layer: virtual networks and subnets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import (
    Subnet,
    SubnetDelegation,
    SubnetServiceEndpoint,
    VirtualNetwork,
    VirtualNetworkPeeringSummary,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def _normalize_vnet(vnet: Any, *, subscription_id: str, observed_at: str) -> VirtualNetwork:
    parsed = parse_resource_id(vnet.id)
    return VirtualNetwork(
        resource_id=vnet.id,
        name=vnet.name,
        subscription_id=parsed.subscription_id or subscription_id,
        resource_group=parsed.resource_group,
        location=vnet.location,
        provisioning_state=getattr(vnet, "provisioning_state", None),
        tags=normalize_tags(vnet.tags),
        observed_at=observed_at,
        source_api="Microsoft.Network/virtualNetworks",
        address_space=list(
            (vnet.address_space.address_prefixes or []) if vnet.address_space else []
        ),
        dns_servers=list((vnet.dhcp_options.dns_servers or []) if vnet.dhcp_options else []),
        subnet_ids=[s.id for s in (vnet.subnets or []) if s.id],
        peerings=[
            VirtualNetworkPeeringSummary(
                name=p.name,
                remote_virtual_network_id=(
                    p.remote_virtual_network.id if p.remote_virtual_network else None
                ),
                peering_state=getattr(p, "peering_state", None),
            )
            for p in (vnet.virtual_network_peerings or [])
        ],
        enable_ddos_protection=getattr(vnet, "enable_ddos_protection", None),
    )


def list_virtual_networks(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[VirtualNetwork]:
    """Call VirtualNetworksOperations.list_all (whole subscription) or
    .list (one resource group), depending on whether ``resource_group``
    is given."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.virtual_networks,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.virtual_networks, "list_all", max_items=settings.max_page_results)

    return [
        _normalize_vnet(v, subscription_id=subscription_id, observed_at=observed_at) for v in raw
    ]


def _normalize_subnet(
    subnet: Any, *, subscription_id: str, virtual_network_name: str, observed_at: str
) -> Subnet:
    parsed = parse_resource_id(subnet.id)
    return Subnet(
        resource_id=subnet.id,
        name=subnet.name,
        subscription_id=parsed.subscription_id or subscription_id,
        resource_group=parsed.resource_group,
        provisioning_state=getattr(subnet, "provisioning_state", None),
        observed_at=observed_at,
        source_api="Microsoft.Network/virtualNetworks/subnets",
        virtual_network_name=virtual_network_name,
        address_prefix=getattr(subnet, "address_prefix", None),
        address_prefixes=list(getattr(subnet, "address_prefixes", None) or []),
        network_security_group_id=(
            subnet.network_security_group.id if subnet.network_security_group else None
        ),
        route_table_id=(subnet.route_table.id if subnet.route_table else None),
        nat_gateway_id=(subnet.nat_gateway.id if subnet.nat_gateway else None),
        service_endpoints=[
            SubnetServiceEndpoint(service=se.service, locations=list(se.locations or []))
            for se in (subnet.service_endpoints or [])
        ],
        delegations=[
            SubnetDelegation(
                name=d.name, service_name=d.service_name, actions=list(d.actions or [])
            )
            for d in (subnet.delegations or [])
        ],
    )


def list_subnets(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_network_name: str,
) -> list[Subnet]:
    """Call SubnetsOperations.list for one VNet."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(
        client.subnets,
        "list",
        max_items=settings.max_page_results,
        resource_group_name=resource_group,
        virtual_network_name=virtual_network_name,
    )
    return [
        _normalize_subnet(
            s,
            subscription_id=subscription_id,
            virtual_network_name=virtual_network_name,
            observed_at=observed_at,
        )
        for s in raw
    ]


__all__ = ["list_subnets", "list_virtual_networks"]
