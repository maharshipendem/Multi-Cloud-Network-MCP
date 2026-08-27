"""Normalized models for Direct Connect resources."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import AwsResource


class DirectConnectConnection(AwsResource):
    """Normalized entry from directconnect:DescribeConnections.

    Includes hosted connections visible to this identity (a hosted
    connection's owner sees it via the same API, with
    ``lag_id``/``partner_name`` distinguishing it from a connection
    owned directly by this account).
    """

    connection_id: str
    connection_name: str | None = None
    connection_state: str
    location: str | None = None
    bandwidth: str | None = None
    vlan: int | None = None
    partner_name: str | None = None
    lag_id: str | None = None
    aws_device: str | None = None
    has_logical_redundancy: str | None = None


class Lag(AwsResource):
    """Normalized entry from directconnect:DescribeLags (a Link Aggregation Group)."""

    lag_id: str
    lag_name: str | None = None
    lag_state: str
    location: str | None = None
    number_of_connections: int | None = None
    minimum_links: int | None = None
    connections_bandwidth: str | None = None
    has_logical_redundancy: str | None = None


class VirtualInterfaceBgpPeer(BaseModel):
    """Operational BGP peer state, kept separate from VIF configuration.

    No authentication key is included here -- ``DescribeVirtualInterfaces``
    does not return the configured BGP MD5 auth key in cleartext, and this
    model does not map one through even if present.
    """

    bgp_peer_id: str | None = None
    asn: int | None = None
    address_family: str | None = None
    bgp_peer_state: str | None = None  # configuration state
    bgp_status: str | None = None  # operational: "up" | "down"


class VirtualInterface(AwsResource):
    """Normalized entry from directconnect:DescribeVirtualInterfaces.

    ``virtual_interface_type`` is one of ``private`` or ``public`` (a
    private VIF terminates on a VGW/DXGW into a VPC; a public VIF reaches
    AWS public endpoints/services directly).
    """

    virtual_interface_id: str
    virtual_interface_name: str | None = None
    virtual_interface_type: str | None = None
    virtual_interface_state: str
    connection_id: str | None = None
    direct_connect_gateway_id: str | None = None
    vlan: int | None = None
    asn: int | None = None
    amazon_address: str | None = None
    customer_address: str | None = None
    address_family: str | None = None
    route_filter_prefixes: list[str] = Field(default_factory=list)
    bgp_peers: list[VirtualInterfaceBgpPeer] = Field(default_factory=list)


class DirectConnectGatewayAssociation(BaseModel):
    """Normalized entry from directconnect:DescribeDirectConnectGatewayAssociations."""

    association_id: str | None = None
    direct_connect_gateway_id: str | None = None
    associated_gateway_id: str | None = None  # a VGW or TGW ID
    associated_gateway_type: str | None = None  # "virtualPrivateGateway" | "transitGateway"
    association_state: str | None = None
    allowed_prefixes: list[str] = Field(default_factory=list)


class DirectConnectGateway(AwsResource):
    """Normalized entry from directconnect:DescribeDirectConnectGateways.

    A Direct Connect Gateway is itself a global-scope resource (see
    ``AwsResource.scope``); ``associations`` are fetched separately and
    attached here for convenience.
    """

    direct_connect_gateway_id: str
    direct_connect_gateway_name: str | None = None
    direct_connect_gateway_state: str
    amazon_side_asn: int | None = None
    owner_account: str | None = None
    associations: list[DirectConnectGatewayAssociation] = Field(default_factory=list)


__all__ = [
    "DirectConnectConnection",
    "DirectConnectGateway",
    "DirectConnectGatewayAssociation",
    "Lag",
    "VirtualInterface",
    "VirtualInterfaceBgpPeer",
]
