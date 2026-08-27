"""Normalized models for Transit Gateway resources."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import AwsResource


class TransitGatewayOptions(BaseModel):
    """Configuration state for a Transit Gateway (kept separate from
    the resource's operational ``state`` field)."""

    amazon_side_asn: int | None = None
    auto_accept_shared_attachments: str | None = None
    default_route_table_association: str | None = None
    default_route_table_propagation: str | None = None
    dns_support: str | None = None
    vpn_ecmp_support: str | None = None
    multicast_support: str | None = None
    cidr_blocks: list[str] = Field(default_factory=list)


class TransitGateway(AwsResource):
    """Normalized entry from ec2:DescribeTransitGateways."""

    transit_gateway_id: str
    transit_gateway_arn: str | None = None
    owner_id: str | None = None
    description: str | None = None
    state: str
    options: TransitGatewayOptions = Field(default_factory=TransitGatewayOptions)


class TransitGatewayAttachmentAssociation(BaseModel):
    transit_gateway_route_table_id: str | None = None
    state: str | None = None


class TransitGatewayAttachment(AwsResource):
    """Normalized entry from ec2:DescribeTransitGatewayAttachments.

    ``resource_type`` is one of ``vpc``, ``vpn``, ``direct-connect-gateway``,
    ``peering``, ``connect``, or ``tgw-peering`` -- covers the VPC/VPN/
    peering/Connect attachment types the milestone asks for.
    """

    transit_gateway_attachment_id: str
    transit_gateway_id: str
    transit_gateway_owner_id: str | None = None
    resource_owner_id: str | None = None
    resource_type: str
    resource_id: str | None = None
    state: str
    association: TransitGatewayAttachmentAssociation | None = None


class TransitGatewayRouteTableAssociation(BaseModel):
    """Normalized entry from ec2:GetTransitGatewayRouteTableAssociations."""

    transit_gateway_attachment_id: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None
    state: str | None = None


class TransitGatewayRouteTablePropagation(BaseModel):
    """Normalized entry from ec2:GetTransitGatewayRouteTablePropagations."""

    transit_gateway_attachment_id: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None
    state: str | None = None


class TransitGatewayRouteTable(AwsResource):
    """Normalized entry from ec2:DescribeTransitGatewayRouteTables.

    ``associations``/``propagations`` are ``None`` unless the caller
    opted in (``include_associations``/``include_propagations`` on
    ``aws_list_transit_gateway_route_tables``) -- each requires one extra
    API call per route table, bounded by ``Settings.max_fanout_calls``,
    the same inline-enrichment pattern as Milestone 2's ``RouteTable``.
    """

    transit_gateway_route_table_id: str
    transit_gateway_id: str
    state: str
    default_association_route_table: bool = False
    default_propagation_route_table: bool = False
    associations: list[TransitGatewayRouteTableAssociation] | None = None
    propagations: list[TransitGatewayRouteTablePropagation] | None = None


class TransitGatewayRouteAttachment(BaseModel):
    transit_gateway_attachment_id: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None


class TransitGatewayRoute(BaseModel):
    """A single normalized route from ec2:SearchTransitGatewayRoutes."""

    destination_cidr_block: str | None = None
    route_type: str | None = None  # "static" | "propagated"
    state: str | None = None  # "active" | "blackhole" | "pending" | "deleted"
    attachments: list[TransitGatewayRouteAttachment] = Field(default_factory=list)


__all__ = [
    "TransitGateway",
    "TransitGatewayAttachment",
    "TransitGatewayAttachmentAssociation",
    "TransitGatewayOptions",
    "TransitGatewayRoute",
    "TransitGatewayRouteAttachment",
    "TransitGatewayRouteTable",
    "TransitGatewayRouteTableAssociation",
    "TransitGatewayRouteTablePropagation",
]
