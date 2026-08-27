"""``NetworkSnapshot``: the single input every diagnostic module consumes.

A snapshot is a plain, already-normalized bundle of the resource lists
diagnostics need -- built by ``aws_cloudops_mcp.aws.snapshot`` from live AWS
calls, or loaded from a saved JSON fixture for the offline dry-run mode
(``diagnostics.offline``). Either way, this module and everything under
``diagnostics.*`` reads only this type; it never touches boto3 or an MCP
context directly.
"""

from __future__ import annotations

import ipaddress

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import CollectionWarning, RouteTable, Subnet, Vpc
from aws_cloudops_mcp.models.network_resources import (
    EgressOnlyInternetGateway,
    InternetGateway,
    LoadBalancer,
    ManagedPrefixList,
    NatGateway,
    NetworkAcl,
    NetworkInterface,
    SecurityGroup,
    VpcEndpoint,
    VpcPeeringConnection,
)
from aws_cloudops_mcp.models.transit_gateway import (
    TransitGateway,
    TransitGatewayAttachment,
    TransitGatewayRoute,
    TransitGatewayRouteTable,
)
from aws_cloudops_mcp.models.vpn import CustomerGateway, VpnConnection


class NetworkSnapshot(BaseModel):
    """A point-in-time bundle of normalized network resources.

    ``collected_at`` is when this snapshot was assembled (may post-date
    the individual ``observed_at`` timestamp on each resource, if a
    caller merges records collected at slightly different times -- the
    offline fixture loader stamps this explicitly rather than leaving it
    to be inferred). ``region``/``account_id`` describe the primary scope
    this snapshot was collected for; resources with a different
    (``region``, ``account_id``) can still appear (e.g. a cross-region
    Transit Gateway peer) and are matched by their own IDs, not filtered
    by these two fields.

    Every list defaults to empty, not missing -- a diagnostic reading an
    empty ``vpn_connections`` list must be able to tell "this account has
    none" from "this wasn't collected" only via ``warnings`` (a
    :class:`CollectionWarning` for anything not collected), never by the
    list's mere emptiness.
    """

    region: str
    account_id: str
    collected_at: str

    vpcs: list[Vpc] = Field(default_factory=list)
    subnets: list[Subnet] = Field(default_factory=list)
    route_tables: list[RouteTable] = Field(default_factory=list)
    security_groups: list[SecurityGroup] = Field(default_factory=list)
    network_acls: list[NetworkAcl] = Field(default_factory=list)
    network_interfaces: list[NetworkInterface] = Field(default_factory=list)
    internet_gateways: list[InternetGateway] = Field(default_factory=list)
    egress_only_internet_gateways: list[EgressOnlyInternetGateway] = Field(default_factory=list)
    nat_gateways: list[NatGateway] = Field(default_factory=list)
    vpc_peering_connections: list[VpcPeeringConnection] = Field(default_factory=list)
    vpc_endpoints: list[VpcEndpoint] = Field(default_factory=list)
    managed_prefix_lists: list[ManagedPrefixList] = Field(default_factory=list)
    load_balancers: list[LoadBalancer] = Field(default_factory=list)
    transit_gateways: list[TransitGateway] = Field(default_factory=list)
    transit_gateway_attachments: list[TransitGatewayAttachment] = Field(default_factory=list)
    transit_gateway_route_tables: list[TransitGatewayRouteTable] = Field(default_factory=list)
    transit_gateway_routes: list[TransitGatewayRoute] = Field(default_factory=list)
    vpn_connections: list[VpnConnection] = Field(default_factory=list)
    customer_gateways: list[CustomerGateway] = Field(default_factory=list)

    warnings: list[CollectionWarning] = Field(default_factory=list)

    def subnet_by_id(self, subnet_id: str) -> Subnet | None:
        return next((s for s in self.subnets if s.subnet_id == subnet_id), None)

    def vpc_by_id(self, vpc_id: str) -> Vpc | None:
        return next((v for v in self.vpcs if v.vpc_id == vpc_id), None)

    def eni_by_id(self, network_interface_id: str) -> NetworkInterface | None:
        return next(
            (e for e in self.network_interfaces if e.network_interface_id == network_interface_id),
            None,
        )

    def route_table_for_subnet(self, subnet_id: str, vpc_id: str) -> RouteTable | None:
        """The route table AWS actually uses for a subnet: an explicit
        association if one exists, otherwise the VPC's main route table --
        exactly AWS's own resolution order, never "the first table found."
        """
        for rt in self.route_tables:
            for assoc in rt.associations:
                if assoc.subnet_id == subnet_id:
                    return rt
        for rt in self.route_tables:
            if rt.vpc_id != vpc_id:
                continue
            for assoc in rt.associations:
                if assoc.main:
                    return rt
        return None

    def security_group_by_id(self, group_id: str) -> SecurityGroup | None:
        return next((sg for sg in self.security_groups if sg.group_id == group_id), None)

    def network_acl_for_subnet(self, subnet_id: str) -> NetworkAcl | None:
        for nacl in self.network_acls:
            for assoc in nacl.associations:
                if assoc.subnet_id == subnet_id:
                    return nacl
        return None

    def subnet_containing_ip(self, vpc_id: str, ip: str) -> str | None:
        """The subnet in ``vpc_id`` whose CIDR contains ``ip``, or
        ``None`` if ``ip`` isn't a valid address or no subnet matches."""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        for subnet in self.subnets:
            if subnet.vpc_id != vpc_id:
                continue
            try:
                net = ipaddress.ip_network(subnet.cidr_block, strict=False)
            except ValueError:
                continue
            if addr in net:
                return subnet.subnet_id
        return None


__all__ = ["NetworkSnapshot"]
