"""Normalized models for Milestone 2's additional VPC networking resources.

Kept in a separate module from ``models.common`` (which holds the
Milestone 1 core: VPC/Subnet/RouteTable) purely for file size -- these are
still part of the same normalized-response contract and every model here
inherits ``AwsResource`` for the common account/region/tags/observed_at
fields.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import AwsResource, Tags

# --- Internet gateways -------------------------------------------------


class InternetGatewayAttachment(BaseModel):
    vpc_id: str
    state: str | None = None


class InternetGateway(AwsResource):
    """Normalized entry from ec2:DescribeInternetGateways."""

    internet_gateway_id: str
    owner_id: str | None = None
    attachments: list[InternetGatewayAttachment] = Field(default_factory=list)


class EgressOnlyInternetGateway(AwsResource):
    """Normalized entry from ec2:DescribeEgressOnlyInternetGateways."""

    egress_only_internet_gateway_id: str
    attachments: list[InternetGatewayAttachment] = Field(default_factory=list)


# --- NAT gateways --------------------------------------------------------


class NatGatewayAddress(BaseModel):
    allocation_id: str | None = None
    network_interface_id: str | None = None
    private_ip: str | None = None
    public_ip: str | None = None
    is_primary: bool | None = None
    status: str | None = None


class NatGateway(AwsResource):
    """Normalized entry from ec2:DescribeNatGateways."""

    nat_gateway_id: str
    vpc_id: str
    subnet_id: str | None = None
    state: str
    connectivity_type: str | None = None
    addresses: list[NatGatewayAddress] = Field(default_factory=list)
    failure_code: str | None = None
    failure_message: str | None = None


# --- Security groups -----------------------------------------------------


class SecurityGroupRulePeer(BaseModel):
    """The single peer a security group rule applies to.

    ``type`` is one of ``ipv4``, ``ipv6``, ``prefix_list``, or
    ``security_group`` -- exactly one of the corresponding ``value``
    fields is populated, matching how AWS models a rule (a rule targets
    exactly one peer type).
    """

    type: str
    value: str
    referenced_group_id: str | None = None
    referenced_vpc_id: str | None = None
    referenced_owner_id: str | None = None


class SecurityGroupRule(AwsResource):
    """Normalized entry from ec2:DescribeSecurityGroupRules.

    Uses the newer rule-level API (rather than the nested
    IpPermissions/IpPermissionsEgress on DescribeSecurityGroups) because it
    is the only one that gives each rule a stable
    ``security_group_rule_id``, which the tool contract requires.
    """

    security_group_rule_id: str
    security_group_id: str
    vpc_id: str | None = None
    is_egress: bool
    ip_protocol: str
    from_port: int | None = None
    to_port: int | None = None
    peer: SecurityGroupRulePeer
    description: str | None = None


class SecurityGroup(AwsResource):
    """Normalized entry from ec2:DescribeSecurityGroups (group metadata only).

    Rules are returned separately by ``aws_list_security_groups`` under
    ``rules`` (fetched via ``DescribeSecurityGroupRules``) so each rule
    keeps its own stable ID rather than being flattened/re-derived from
    the legacy nested permission blocks.
    """

    group_id: str
    group_name: str
    description: str | None = None
    vpc_id: str | None = None
    owner_id: str | None = None
    rules: list[SecurityGroupRule] = Field(default_factory=list)


# --- Network ACLs ----------------------------------------------------------


class NetworkAclEntry(BaseModel):
    rule_number: int
    protocol: str
    rule_action: str  # allow | deny
    egress: bool
    cidr_block: str | None = None
    ipv6_cidr_block: str | None = None
    icmp_type: int | None = None
    icmp_code: int | None = None
    port_range_from: int | None = None
    port_range_to: int | None = None


class NetworkAclAssociation(BaseModel):
    network_acl_association_id: str | None = None
    subnet_id: str | None = None


class NetworkAcl(AwsResource):
    """Normalized entry from ec2:DescribeNetworkAcls.

    ``entries`` are sorted by (``egress``, ``rule_number``) so evaluation
    order -- which determines which rule actually applies -- is explicit
    and deterministic in the output, matching how AWS evaluates NACL rules
    in ascending rule-number order within each direction.
    """

    network_acl_id: str
    vpc_id: str
    is_default: bool
    entries: list[NetworkAclEntry] = Field(default_factory=list)
    associations: list[NetworkAclAssociation] = Field(default_factory=list)


# --- Elastic network interfaces --------------------------------------------


class NetworkInterfaceAttachment(BaseModel):
    attachment_id: str | None = None
    instance_id: str | None = None
    device_index: int | None = None
    status: str | None = None
    delete_on_termination: bool | None = None


class NetworkInterface(AwsResource):
    """Normalized entry from ec2:DescribeNetworkInterfaces."""

    network_interface_id: str
    subnet_id: str | None = None
    vpc_id: str | None = None
    description: str | None = None
    status: str | None = None
    interface_type: str | None = None
    private_ip_address: str | None = None
    private_ip_addresses: list[str] = Field(default_factory=list)
    public_ip: str | None = None
    security_group_ids: list[str] = Field(default_factory=list)
    attachment: NetworkInterfaceAttachment | None = None
    requester_managed: bool = False
    requester_id: str | None = None


# --- VPC peering -----------------------------------------------------------


class VpcPeeringPeer(BaseModel):
    vpc_id: str | None = None
    owner_id: str | None = None
    region: str | None = None
    cidr_blocks: list[str] = Field(default_factory=list)


class VpcPeeringConnection(AwsResource):
    """Normalized entry from ec2:DescribeVpcPeeringConnections."""

    vpc_peering_connection_id: str
    status_code: str | None = None
    status_message: str | None = None
    requester: VpcPeeringPeer
    accepter: VpcPeeringPeer


# --- Managed prefix lists ----------------------------------------------------


class ManagedPrefixListEntry(BaseModel):
    cidr: str
    description: str | None = None


class ManagedPrefixList(AwsResource):
    """Normalized entry from ec2:DescribeManagedPrefixLists.

    ``entries`` is populated only when the caller opted in
    (``include_entries`` on ``aws_list_managed_prefix_lists``) -- AWS
    requires one ``GetManagedPrefixListEntries`` call per prefix list, so
    this is bounded fan-out, not a batch call.
    """

    prefix_list_id: str
    prefix_list_name: str | None = None
    state: str | None = None
    address_family: str | None = None
    max_entries: int | None = None
    version: int | None = None
    owner_id: str | None = None
    entries: list[ManagedPrefixListEntry] | None = None


# --- VPC endpoints -----------------------------------------------------------

# Endpoint policy documents can be large and may embed account/role ARNs the
# account already has visibility into via IAM; this is a size guard against
# an oversized policy blowing up a tool response, not a claim of secrecy.
MAX_POLICY_DOCUMENT_CHARS = 8000


class VpcEndpointDnsEntry(BaseModel):
    dns_name: str | None = None
    hosted_zone_id: str | None = None


class VpcEndpoint(AwsResource):
    """Normalized entry from ec2:DescribeVpcEndpoints.

    ``policy_document`` is included only when the caller opts in
    (``include_policies`` on ``aws_list_vpc_endpoints``) and only after a
    size check: documents over ``MAX_POLICY_DOCUMENT_CHARS`` are truncated
    with ``policy_document_truncated=True`` rather than returned in full.
    """

    vpc_endpoint_id: str
    vpc_id: str
    service_name: str
    vpc_endpoint_type: str
    state: str | None = None
    route_table_ids: list[str] = Field(default_factory=list)
    subnet_ids: list[str] = Field(default_factory=list)
    security_group_ids: list[str] = Field(default_factory=list)
    network_interface_ids: list[str] = Field(default_factory=list)
    private_dns_enabled: bool | None = None
    dns_entries: list[VpcEndpointDnsEntry] = Field(default_factory=list)
    policy_document: str | None = None
    policy_document_truncated: bool = False


class VpcEndpointService(BaseModel):
    """Normalized entry from ec2:DescribeVpcEndpointServices.

    Account/region-scoped visibility, not a resource owned by the account,
    so this intentionally does not inherit ``AwsResource`` -- it has no
    tags and is not something the account can be billed for/tag.
    """

    service_name: str
    service_id: str | None = None
    service_type: list[str] = Field(default_factory=list)
    owner: str | None = None
    availability_zones: list[str] = Field(default_factory=list)
    private_dns_name: str | None = None
    vpc_endpoint_policy_supported: bool | None = None
    region: str


# --- Load balancers (ELBv2) -------------------------------------------------


class TargetHealth(BaseModel):
    target_id: str
    port: int | None = None
    availability_zone: str | None = None
    health_state: str | None = None
    health_reason: str | None = None
    health_description: str | None = None


class TargetGroup(AwsResource):
    """Normalized entry from elbv2:DescribeTargetGroups.

    ``targets`` is populated only when the caller opts into target-health
    enrichment (``include_target_health`` on ``aws_list_load_balancers``) --
    AWS requires one ``DescribeTargetHealth`` call per target group.
    """

    target_group_arn: str
    target_group_name: str
    protocol: str | None = None
    port: int | None = None
    vpc_id: str | None = None
    target_type: str | None = None
    load_balancer_arns: list[str] = Field(default_factory=list)
    targets: list[TargetHealth] | None = None


class ListenerAction(BaseModel):
    type: str
    target_group_arn: str | None = None


class Listener(BaseModel):
    listener_arn: str
    load_balancer_arn: str
    protocol: str | None = None
    port: int | None = None
    default_actions: list[ListenerAction] = Field(default_factory=list)


class LoadBalancerAzSubnet(BaseModel):
    zone_name: str | None = None
    subnet_id: str | None = None


class LoadBalancer(AwsResource):
    """Normalized entry from elbv2:DescribeLoadBalancers, joined with its
    listeners and target groups (each requiring their own AWS calls -- see
    ``aws.loadbalancers``).
    """

    load_balancer_arn: str
    load_balancer_name: str
    dns_name: str | None = None
    scheme: str | None = None
    vpc_id: str | None = None
    type: str  # application | network | gateway
    state: str | None = None
    ip_address_type: str | None = None
    availability_zones: list[LoadBalancerAzSubnet] = Field(default_factory=list)
    security_group_ids: list[str] = Field(default_factory=list)
    listeners: list[Listener] = Field(default_factory=list)
    target_groups: list[TargetGroup] = Field(default_factory=list)


__all__ = [
    "EgressOnlyInternetGateway",
    "InternetGateway",
    "InternetGatewayAttachment",
    "Listener",
    "ListenerAction",
    "LoadBalancer",
    "LoadBalancerAzSubnet",
    "ManagedPrefixList",
    "ManagedPrefixListEntry",
    "NatGateway",
    "NatGatewayAddress",
    "NetworkAcl",
    "NetworkAclAssociation",
    "NetworkAclEntry",
    "NetworkInterface",
    "NetworkInterfaceAttachment",
    "SecurityGroup",
    "SecurityGroupRule",
    "SecurityGroupRulePeer",
    "TargetGroup",
    "TargetHealth",
    "Tags",
    "VpcEndpoint",
    "VpcEndpointDnsEntry",
    "VpcEndpointService",
    "VpcPeeringConnection",
    "VpcPeeringPeer",
]
