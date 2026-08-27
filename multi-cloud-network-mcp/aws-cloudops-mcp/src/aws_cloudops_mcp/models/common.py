"""Normalized domain models returned by the AWS service layer.

These models are the contract between the AWS service layer and the tool
layer, and (once serialized) the contract handed back to MCP clients. They
are intentionally cloud-agnostic in shape so a future multi-cloud
orchestration layer can consume AWS, Azure, and GCP MCP output consistently.

Milestone 2 note: every resource record (anything below that inherits
``AwsResource``) carries ``account_id``, ``region``, ``tags``, and
``observed_at`` -- these are additive fields with no removed/renamed
predecessors, so existing Milestone 1 consumers reading known fields by name
are unaffected. See CHANGELOG.md for the full migration note.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

Tags = dict[str, str]


class CallerIdentity(BaseModel):
    """Normalized result of sts:GetCallerIdentity."""

    account_id: str
    arn: str
    user_id: str


class RegionInfo(BaseModel):
    """Normalized entry from ec2:DescribeRegions."""

    region_name: str
    endpoint: str | None = None
    opt_in_status: str | None = None


class CollectionWarning(BaseModel):
    """A non-fatal issue encountered while collecting one resource type.

    Used whenever a tool returns a *partial* result rather than failing
    outright -- e.g. missing permission for one optional resource, or a
    bounded fan-out cap being reached. A missing permission must never be
    silently treated as "this resource type has zero instances"; it must
    surface here instead.
    """

    resource_type: str
    code: str
    message: str


class AwsResource(BaseModel):
    """Fields every normalized AWS resource record carries.

    ``observed_at`` is the collection timestamp (ISO 8601, UTC) for the API
    call(s) that produced this record, not a live/real-time value -- it lets
    a caller (or a later diffing/troubleshooting tool) reason about how
    stale a given record is.

    Milestone 3 additions (all optional/defaulted, so Milestone 1/2 service
    functions need no changes): ``scope`` distinguishes a regional resource
    from a global one (Route 53, Network Manager global networks) --
    ``region`` stays populated even for global resources (the endpoint
    region the call was actually issued through) so existing consumers
    filtering by region are unaffected. ``source_api`` names the specific
    AWS API call that produced the record, for provenance. ``collection_completeness``
    and ``redacted`` flag records assembled from a partial or
    field-redacted response (e.g. a VPN connection with its pre-shared key
    stripped) rather than leaving that ambiguous.
    """

    account_id: str
    region: str
    observed_at: str
    tags: Tags = Field(default_factory=dict)
    scope: str = "regional"
    source_api: str | None = None
    collection_completeness: str = "complete"
    redacted: bool = False


class VpcCidrBlockAssociation(BaseModel):
    """A single (primary or secondary) IPv4 CIDR association on a VPC."""

    association_id: str | None = None
    cidr_block: str
    state: str | None = None


class VpcIpv6CidrBlockAssociation(BaseModel):
    """A single IPv6 CIDR association on a VPC."""

    association_id: str | None = None
    ipv6_cidr_block: str
    state: str | None = None
    ipv6_pool: str | None = None
    network_border_group: str | None = None


class Vpc(AwsResource):
    """Normalized entry from ec2:DescribeVpcs.

    ``enable_dns_support``/``enable_dns_hostnames`` are ``None`` unless a
    caller opted into DNS-attribute enrichment (``include_dns_attributes``
    on ``aws_list_vpcs``) -- AWS does not include them in DescribeVpcs and
    fetching them requires two extra API calls per VPC, so they are
    opt-in/bounded rather than always fetched. See
    ``aws.networking.list_vpcs``.
    """

    vpc_id: str
    cidr_block: str
    cidr_block_associations: list[VpcCidrBlockAssociation] = Field(default_factory=list)
    ipv6_cidr_block_associations: list[VpcIpv6CidrBlockAssociation] = Field(default_factory=list)
    state: str
    is_default: bool
    instance_tenancy: str | None = None
    dhcp_options_id: str | None = None
    enable_dns_support: bool | None = None
    enable_dns_hostnames: bool | None = None


class SubnetIpv6CidrBlockAssociation(BaseModel):
    """A single IPv6 CIDR association on a subnet."""

    association_id: str | None = None
    ipv6_cidr_block: str
    state: str | None = None


class Subnet(AwsResource):
    """Normalized entry from ec2:DescribeSubnets."""

    subnet_id: str
    vpc_id: str
    cidr_block: str
    ipv6_cidr_block_associations: list[SubnetIpv6CidrBlockAssociation] = Field(default_factory=list)
    availability_zone: str
    availability_zone_id: str | None = None
    available_ip_address_count: int
    map_public_ip_on_launch: bool
    assign_ipv6_address_on_creation: bool | None = None
    default_for_az: bool | None = None
    state: str | None = None


class Route(BaseModel):
    """A single normalized route within a route table.

    ``is_propagated`` is derived from AWS's ``Origin`` field
    (``EnableVgwRoutePropagation``) -- AWS does not expose a separate
    boolean, so this is the explicit/propagated distinction the tool
    contract asks for.
    """

    destination_cidr_block: str | None = None
    destination_ipv6_cidr_block: str | None = None
    destination_prefix_list_id: str | None = None
    target: str | None = None
    target_type: str | None = None
    state: str | None = None
    origin: str | None = None
    is_propagated: bool = False


class RouteTableAssociation(BaseModel):
    """A single normalized route table association."""

    route_table_association_id: str | None = None
    subnet_id: str | None = None
    gateway_id: str | None = None
    main: bool = False
    association_state: str | None = None


class RouteTable(AwsResource):
    """Normalized entry from ec2:DescribeRouteTables."""

    route_table_id: str
    vpc_id: str
    routes: list[Route] = Field(default_factory=list)
    associations: list[RouteTableAssociation] = Field(default_factory=list)
    propagating_vgws: list[str] = Field(default_factory=list)
