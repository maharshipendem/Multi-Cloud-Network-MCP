"""The single ARM-bridging seam for the diagnostics engine.

``collect_hybrid_snapshot`` is the only function in ``diagnostics.*`` that
touches ``arm.*`` (and therefore, transitively, the Azure SDK) -- every
rule module downstream (``routing.py``, ``security.py``, ``exposure.py``,
``consistency.py``, ``hybrid_topology.py``) is a pure function of the
``HybridNetworkSnapshot`` this module produces, exactly mirroring the
AWS-sibling project's ``aws/snapshot.py`` -> ``NetworkSnapshot`` seam. It
adds zero new Azure API surface beyond what Milestones 5 and 6's own
``arm.*`` collectors already provide.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from azure_network_mcp.arm.collection import CollectionResult, now_iso
from azure_network_mcp.arm.expressroute import (
    list_express_route_circuits,
    list_express_route_connections,
    list_express_route_gateways,
)
from azure_network_mcp.arm.network_interfaces import list_network_interfaces
from azure_network_mcp.arm.network_security_groups import (
    get_effective_network_security_groups,
    list_network_security_groups,
)
from azure_network_mcp.arm.networking import list_subnets, list_virtual_networks
from azure_network_mcp.arm.private_link import list_private_endpoints
from azure_network_mcp.arm.public_ips import list_public_ip_addresses
from azure_network_mcp.arm.route_tables import get_effective_route_table, list_route_tables
from azure_network_mcp.arm.virtual_wan import (
    list_hub_virtual_network_connections,
    list_virtual_hubs,
)
from azure_network_mcp.arm.vpn import (
    list_virtual_network_gateway_connections,
    list_virtual_network_gateways,
    list_vpn_connections,
    list_vpn_gateways,
)
from azure_network_mcp.models.common import CollectionWarning
from azure_network_mcp.models.hybrid_connectivity import (
    ExpressRouteCircuit,
    ExpressRouteConnection,
    ExpressRouteGateway,
    HubVirtualNetworkConnection,
    VirtualHub,
    VirtualNetworkGateway,
    VirtualNetworkGatewayConnection,
    VpnConnection,
    VpnGateway,
)
from azure_network_mcp.models.network_resources import (
    EffectiveRoute,
    EffectiveSecurityRule,
    NetworkInterface,
    NetworkSecurityGroup,
    PublicIpAddress,
    RouteTable,
    Subnet,
    VirtualNetwork,
)
from azure_network_mcp.models.private_link import PrivateEndpoint

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


class HybridNetworkSnapshot(BaseModel):
    """Every fact the diagnostics engine's rules reason over, for one
    resource group. A pure data container -- collection (this module) and
    reasoning (routing.py/security.py/exposure.py/consistency.py) are
    fully separate, mirroring the AWS sibling's NetworkSnapshot design."""

    subscription_id: str
    resource_group: str
    observed_at: str

    virtual_networks: list[VirtualNetwork] = Field(default_factory=list)
    subnets: list[Subnet] = Field(default_factory=list)
    network_security_groups: list[NetworkSecurityGroup] = Field(default_factory=list)
    route_tables: list[RouteTable] = Field(default_factory=list)
    network_interfaces: list[NetworkInterface] = Field(default_factory=list)
    public_ip_addresses: list[PublicIpAddress] = Field(default_factory=list)
    private_endpoints: list[PrivateEndpoint] = Field(default_factory=list)

    virtual_hubs: list[VirtualHub] = Field(default_factory=list)
    hub_virtual_network_connections: list[HubVirtualNetworkConnection] = Field(default_factory=list)
    vpn_gateways: list[VpnGateway] = Field(default_factory=list)
    vpn_connections: list[VpnConnection] = Field(default_factory=list)
    virtual_network_gateways: list[VirtualNetworkGateway] = Field(default_factory=list)
    virtual_network_gateway_connections: list[VirtualNetworkGatewayConnection] = Field(
        default_factory=list
    )
    express_route_circuits: list[ExpressRouteCircuit] = Field(default_factory=list)
    express_route_gateways: list[ExpressRouteGateway] = Field(default_factory=list)
    express_route_connections: list[ExpressRouteConnection] = Field(default_factory=list)

    warnings: list[CollectionWarning] = Field(default_factory=list)


def collect_hybrid_snapshot(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str
) -> HybridNetworkSnapshot:
    """Collect every fact the diagnostics engine needs for one resource
    group. Best-effort per resource family: a family this identity lacks
    RBAC for (or that doesn't exist in this resource group) contributes an
    empty list plus a ``CollectionWarning`` rather than failing the whole
    snapshot -- see ``_collect`` below."""
    warnings: list[CollectionWarning] = []

    def _collect(resource_type: str, func: object, *args: object, **kwargs: object) -> list:
        try:
            result = func(*args, **kwargs)  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any collection
            # failure degrades to an empty, warned family rather than
            # failing the whole snapshot (partial RBAC, unsupported
            # region/API version, throttling all land here).
            warnings.append(
                CollectionWarning(
                    resource_type=resource_type,
                    code="COLLECTION_FAILED",
                    message=f"Could not collect {resource_type}: {exc}",
                )
            )
            return []
        if isinstance(result, CollectionResult):
            warnings.extend(result.warnings)
            return result.data
        return result

    virtual_networks = _collect(
        "virtual_network",
        list_virtual_networks,
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
    )
    subnets: list[Subnet] = []
    for vnet in virtual_networks:
        subnets.extend(
            _collect(
                "subnet",
                list_subnets,
                client_factory,
                subscription_id=subscription_id,
                resource_group=resource_group,
                virtual_network_name=vnet.name,
            )
        )

    hub_vnet_connections: list[HubVirtualNetworkConnection] = []
    virtual_hubs = _collect(
        "virtual_hub",
        list_virtual_hubs,
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
    )
    for hub in virtual_hubs:
        hub_vnet_connections.extend(
            _collect(
                "hub_virtual_network_connection",
                list_hub_virtual_network_connections,
                client_factory,
                subscription_id=subscription_id,
                resource_group=resource_group,
                virtual_hub_name=hub.name,
            )
        )

    vpn_gateways = _collect(
        "vpn_gateway",
        list_vpn_gateways,
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
    )
    vpn_connections: list[VpnConnection] = []
    for gw in vpn_gateways:
        vpn_connections.extend(
            _collect(
                "vpn_connection",
                list_vpn_connections,
                client_factory,
                subscription_id=subscription_id,
                resource_group=resource_group,
                vpn_gateway_name=gw.name,
            )
        )

    express_route_gateways = _collect(
        "express_route_gateway",
        list_express_route_gateways,
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
    )
    express_route_connections: list[ExpressRouteConnection] = []
    for gw in express_route_gateways:
        express_route_connections.extend(
            _collect(
                "express_route_connection",
                list_express_route_connections,
                client_factory,
                subscription_id=subscription_id,
                resource_group=resource_group,
                express_route_gateway_name=gw.name,
            )
        )

    return HybridNetworkSnapshot(
        subscription_id=subscription_id,
        resource_group=resource_group,
        observed_at=now_iso(),
        virtual_networks=virtual_networks,
        subnets=subnets,
        network_security_groups=_collect(
            "network_security_group",
            list_network_security_groups,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        route_tables=_collect(
            "route_table",
            list_route_tables,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        network_interfaces=_collect(
            "network_interface",
            list_network_interfaces,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        public_ip_addresses=_collect(
            "public_ip_address",
            list_public_ip_addresses,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        private_endpoints=_collect(
            "private_endpoint",
            list_private_endpoints,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        virtual_hubs=virtual_hubs,
        hub_virtual_network_connections=hub_vnet_connections,
        vpn_gateways=vpn_gateways,
        vpn_connections=vpn_connections,
        virtual_network_gateways=_collect(
            "virtual_network_gateway",
            list_virtual_network_gateways,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        virtual_network_gateway_connections=_collect(
            "virtual_network_gateway_connection",
            list_virtual_network_gateway_connections,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        express_route_circuits=_collect(
            "express_route_circuit",
            list_express_route_circuits,
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
        ),
        express_route_gateways=express_route_gateways,
        express_route_connections=express_route_connections,
        warnings=warnings,
    )


def collect_nic_effective_state(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    network_interface_name: str,
) -> tuple[list[EffectiveRoute], list[EffectiveSecurityRule]]:
    """Collect one named NIC's effective route table and effective NSG
    rules -- the two targeted, per-NIC computations
    ``diagnostics.explain`` needs. Kept out of ``HybridNetworkSnapshot``
    deliberately: fetching these for every NIC in a resource group would
    be an unbounded fan-out, so they're collected only for the one NIC an
    ``azure_explain_network_path`` call actually names.
    """
    effective_routes = get_effective_route_table(
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
        network_interface_name=network_interface_name,
    )
    effective_nsgs = get_effective_network_security_groups(
        client_factory,
        subscription_id=subscription_id,
        resource_group=resource_group,
        network_interface_name=network_interface_name,
    )
    effective_rules = [rule for nsg in effective_nsgs for rule in nsg.effective_security_rules]
    return effective_routes, effective_rules


__all__ = ["HybridNetworkSnapshot", "collect_hybrid_snapshot", "collect_nic_effective_state"]
