"""Normalized domain models returned by the AWS service layer.

These models are the contract between the AWS service layer and the tool
layer, and (once serialized) the contract handed back to MCP clients. They
are intentionally cloud-agnostic in shape so a future multi-cloud
orchestration layer can consume AWS, Azure, and GCP MCP output consistently.
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


class Vpc(BaseModel):
    """Normalized entry from ec2:DescribeVpcs."""

    vpc_id: str
    cidr_block: str
    state: str
    is_default: bool
    dhcp_options_id: str | None = None
    tags: Tags = Field(default_factory=dict)
    region: str


class Subnet(BaseModel):
    """Normalized entry from ec2:DescribeSubnets."""

    subnet_id: str
    vpc_id: str
    cidr_block: str
    availability_zone: str
    available_ip_address_count: int
    map_public_ip_on_launch: bool
    tags: Tags = Field(default_factory=dict)
    region: str


class Route(BaseModel):
    """A single normalized route within a route table."""

    destination_cidr_block: str | None = None
    destination_prefix_list_id: str | None = None
    target: str | None = None
    target_type: str | None = None
    state: str | None = None
    origin: str | None = None


class RouteTableAssociation(BaseModel):
    """A single normalized route table association."""

    route_table_association_id: str | None = None
    subnet_id: str | None = None
    gateway_id: str | None = None
    main: bool = False


class RouteTable(BaseModel):
    """Normalized entry from ec2:DescribeRouteTables."""

    route_table_id: str
    vpc_id: str
    routes: list[Route] = Field(default_factory=list)
    associations: list[RouteTableAssociation] = Field(default_factory=list)
    tags: Tags = Field(default_factory=dict)
    region: str
