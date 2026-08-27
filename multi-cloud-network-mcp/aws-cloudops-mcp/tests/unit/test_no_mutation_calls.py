"""End-to-end proof that a rich topology run never invokes a mutating AWS API.

Complements security/guardrails' unit-level tests (which prove the pure
`assert_read_only_operation` function rejects bad names) with a behavioral
check: it hooks botocore's event system to record every *real* operation
name issued during a full ``aws_get_vpc_topology`` run against a
resource-rich fixture, then asserts every single one matches the read-only
shape. This is the strongest test in the suite that "no tool call results
in a mutation" -- it observes the actual wire-level operation names, not
just the guardrail's own logic in isolation.
"""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.hybrid_topology import get_hybrid_topology
from aws_cloudops_mcp.aws.topology import get_vpc_topology
from aws_cloudops_mcp.config import Settings
from aws_cloudops_mcp.security.guardrails import BLOCKED_KEYWORDS, READ_ONLY_PREFIXES


def _to_snake_case(operation_name: str) -> str:
    """botocore's before-call event fires with the PascalCase API action
    name (e.g. "DescribeVpcs"); convert to the snake_case boto3 client
    method name this codebase's guardrails operate on."""
    result = []
    for i, char in enumerate(operation_name):
        if char.isupper() and i > 0 and not operation_name[i - 1].isupper():
            result.append("_")
        result.append(char.lower())
    return "".join(result)


@pytest.fixture
def observed_operations() -> list[str]:
    return []


@mock_aws
def test_full_topology_run_issues_only_read_only_operations(
    client_factory: ClientFactory, observed_operations: list[str]
) -> None:
    ec2 = boto3.client("ec2", region_name="us-east-1")
    elbv2 = boto3.client("elbv2", region_name="us-east-1")

    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
    subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
    rt = ec2.create_route_table(VpcId=vpc["VpcId"])["RouteTable"]
    ec2.associate_route_table(RouteTableId=rt["RouteTableId"], SubnetId=subnet["SubnetId"])
    igw = ec2.create_internet_gateway()["InternetGateway"]
    ec2.attach_internet_gateway(InternetGatewayId=igw["InternetGatewayId"], VpcId=vpc["VpcId"])
    ec2.create_route(
        RouteTableId=rt["RouteTableId"],
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=igw["InternetGatewayId"],
    )
    ec2.create_nat_gateway(SubnetId=subnet["SubnetId"], ConnectivityType="public")
    sg = ec2.create_security_group(GroupName="test-sg", Description="t", VpcId=vpc["VpcId"])[
        "GroupId"
    ]
    ec2.create_network_interface(SubnetId=subnet["SubnetId"], Groups=[sg])
    ec2.create_vpc_endpoint(
        VpcId=vpc["VpcId"], ServiceName="com.amazonaws.us-east-1.s3", VpcEndpointType="Gateway"
    )
    peer_vpc = ec2.create_vpc(CidrBlock="10.9.0.0/16")["Vpc"]
    ec2.create_vpc_peering_connection(VpcId=vpc["VpcId"], PeerVpcId=peer_vpc["VpcId"])

    lb = elbv2.create_load_balancer(Name="t", Subnets=[subnet["SubnetId"]], Type="network")[
        "LoadBalancers"
    ][0]
    tg = elbv2.create_target_group(
        Name="t", Protocol="TCP", Port=80, VpcId=vpc["VpcId"], TargetType="ip"
    )["TargetGroups"][0]
    elbv2.create_listener(
        LoadBalancerArn=lb["LoadBalancerArn"],
        Protocol="TCP",
        Port=80,
        DefaultActions=[{"Type": "forward", "TargetGroupArn": tg["TargetGroupArn"]}],
    )

    def record(operation_name: str, **_kwargs: object) -> None:
        observed_operations.append(operation_name)

    watched_session = boto3.Session(region_name="us-east-1")
    watched_session.events.register("before-call.*.*", lambda model, **kw: record(model.name))

    settings = Settings(aws_default_region="us-east-1")
    manager = SessionManager(settings)
    manager._base_session = watched_session  # inject the instrumented session
    watched_client_factory = ClientFactory(settings, manager)

    get_vpc_topology(watched_client_factory, region="us-east-1", vpc_id=vpc["VpcId"])

    assert observed_operations, "expected at least one AWS API call to have been observed"
    _assert_all_read_only(observed_operations)


def _assert_all_read_only(observed_operations: list[str]) -> None:
    for operation_name in observed_operations:
        snake = _to_snake_case(operation_name)
        words = set(snake.split("_"))
        assert not (words & BLOCKED_KEYWORDS), (
            f"{operation_name} ({snake}) matches a blocked mutation keyword"
        )
        assert snake.startswith(READ_ONLY_PREFIXES), (
            f"{operation_name} ({snake}) does not start with a read-only prefix"
        )


@mock_aws
def test_full_hybrid_topology_run_issues_only_read_only_operations(
    client_factory: ClientFactory, observed_operations: list[str]
) -> None:
    """Same behavioral proof as the VPC topology run above, applied to
    Milestone 3's aws_get_hybrid_topology -- a run that spans EC2 (Transit
    Gateway, VPN, Customer Gateway), Route 53, and Route 53 Resolver."""
    ec2 = boto3.client("ec2", region_name="us-east-1")
    r53 = boto3.client("route53")
    r53r = boto3.client("route53resolver", region_name="us-east-1")

    tgw = ec2.create_transit_gateway(Description="hub")["TransitGateway"]
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
    subnet_a = ec2.create_subnet(
        VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
    )["Subnet"]
    subnet_b = ec2.create_subnet(
        VpcId=vpc["VpcId"], CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
    )["Subnet"]
    ec2.create_transit_gateway_vpc_attachment(
        TransitGatewayId=tgw["TransitGatewayId"],
        VpcId=vpc["VpcId"],
        SubnetIds=[subnet_a["SubnetId"]],
    )
    cgw = ec2.create_customer_gateway(Type="ipsec.1", PublicIp="203.0.113.9", BgpAsn=65000)[
        "CustomerGateway"
    ]
    ec2.create_vpn_connection(
        Type="ipsec.1",
        CustomerGatewayId=cgw["CustomerGatewayId"],
        TransitGatewayId=tgw["TransitGatewayId"],
    )
    r53.create_hosted_zone(
        Name="private.example.com",
        CallerReference="test-ref",
        HostedZoneConfig={"PrivateZone": True},
        VPC={"VPCRegion": "us-east-1", "VPCId": vpc["VpcId"]},
    )
    sg = ec2.create_security_group(GroupName="resolver-sg", Description="t", VpcId=vpc["VpcId"])[
        "GroupId"
    ]
    r53r.create_resolver_endpoint(
        CreatorRequestId="req-1",
        SecurityGroupIds=[sg],
        Direction="OUTBOUND",
        IpAddresses=[
            {"SubnetId": subnet_a["SubnetId"]},
            {"SubnetId": subnet_b["SubnetId"]},
        ],
    )

    def record(operation_name: str, **_kwargs: object) -> None:
        observed_operations.append(operation_name)

    watched_session = boto3.Session(region_name="us-east-1")
    watched_session.events.register("before-call.*.*", lambda model, **kw: record(model.name))

    settings = Settings(aws_default_region="us-east-1")
    manager = SessionManager(settings)
    manager._base_session = watched_session
    watched_client_factory = ClientFactory(settings, manager)

    get_hybrid_topology(
        watched_client_factory, region="us-east-1", transit_gateway_id=tgw["TransitGatewayId"]
    )

    assert observed_operations, "expected at least one AWS API call to have been observed"
    _assert_all_read_only(observed_operations)
