from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.topology import get_vpc_topology
from aws_cloudops_mcp.exceptions import ResourceNotFoundError


@pytest.fixture
def rich_topology_fixture(client_factory: ClientFactory) -> dict[str, str]:
    """A VPC with one of nearly every resource type the topology tool
    joins, plus an out-of-scope route target (a virtual private gateway)
    to exercise the orphan-reference path deliberately."""
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        elbv2 = boto3.client("elbv2", region_name="us-east-1")

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        vpc_id = vpc["VpcId"]
        ec2.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": "topo-vpc"}])

        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")["Subnet"]
        subnet_id = subnet["SubnetId"]

        rt = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]
        rt_id = rt["RouteTableId"]
        ec2.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_id)

        igw = ec2.create_internet_gateway()["InternetGateway"]
        igw_id = igw["InternetGatewayId"]
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        ec2.create_route(RouteTableId=rt_id, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw_id)

        # Out-of-scope target (a VPN gateway) -- deliberately not collected
        # by this milestone, so its route becomes an orphan reference.
        vgw = ec2.create_vpn_gateway(Type="ipsec.1")["VpnGateway"]
        ec2.attach_vpn_gateway(VpnGatewayId=vgw["VpnGatewayId"], VpcId=vpc_id)
        ec2.create_route(
            RouteTableId=rt_id,
            DestinationCidrBlock="192.168.0.0/16",
            GatewayId=vgw["VpnGatewayId"],
        )

        nat = ec2.create_nat_gateway(SubnetId=subnet_id, ConnectivityType="public")["NatGateway"]

        sg = ec2.create_security_group(GroupName="topo-sg", Description="topo", VpcId=vpc_id)[
            "GroupId"
        ]

        nacl = ec2.create_network_acl(VpcId=vpc_id)["NetworkAcl"]
        default_assoc = ec2.describe_network_acls(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "default", "Values": ["true"]},
            ]
        )["NetworkAcls"][0]["Associations"][0]["NetworkAclAssociationId"]
        ec2.replace_network_acl_association(
            AssociationId=default_assoc, NetworkAclId=nacl["NetworkAclId"]
        )

        eni = ec2.create_network_interface(SubnetId=subnet_id, Groups=[sg])["NetworkInterface"]

        peer_vpc = ec2.create_vpc(CidrBlock="10.9.0.0/16")["Vpc"]
        pcx = ec2.create_vpc_peering_connection(VpcId=vpc_id, PeerVpcId=peer_vpc["VpcId"])[
            "VpcPeeringConnection"
        ]

        vpce = ec2.create_vpc_endpoint(
            VpcId=vpc_id,
            ServiceName="com.amazonaws.us-east-1.s3",
            VpcEndpointType="Gateway",
            RouteTableIds=[rt_id],
        )["VpcEndpoint"]

        lb = elbv2.create_load_balancer(Name="topo-lb", Subnets=[subnet_id], Type="network")[
            "LoadBalancers"
        ][0]
        tg = elbv2.create_target_group(
            Name="topo-tg", Protocol="TCP", Port=80, VpcId=vpc_id, TargetType="ip"
        )["TargetGroups"][0]
        elbv2.create_listener(
            LoadBalancerArn=lb["LoadBalancerArn"],
            Protocol="TCP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg["TargetGroupArn"]}],
        )

        yield {
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "route_table_id": rt_id,
            "igw_id": igw_id,
            "vgw_id": vgw["VpnGatewayId"],
            "nat_id": nat["NatGatewayId"],
            "sg_id": sg,
            "nacl_id": nacl["NetworkAclId"],
            "eni_id": eni["NetworkInterfaceId"],
            "peer_vpc_id": peer_vpc["VpcId"],
            "pcx_id": pcx["VpcPeeringConnectionId"],
            "vpce_id": vpce["VpcEndpointId"],
            "lb_arn": lb["LoadBalancerArn"],
            "tg_arn": tg["TargetGroupArn"],
        }


def _node_ids(topology: object, node_type: str) -> set[str]:
    return {n.node_id for n in topology.nodes if n.node_type == node_type}  # type: ignore[attr-defined]


def test_topology_includes_every_resource_type_as_a_node(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )

    assert _node_ids(topo, "vpc") == {rich_topology_fixture["vpc_id"]}
    assert rich_topology_fixture["subnet_id"] in _node_ids(topo, "subnet")
    assert rich_topology_fixture["route_table_id"] in _node_ids(topo, "route_table")
    assert rich_topology_fixture["igw_id"] in _node_ids(topo, "internet_gateway")
    assert rich_topology_fixture["nat_id"] in _node_ids(topo, "nat_gateway")
    assert rich_topology_fixture["sg_id"] in _node_ids(topo, "security_group")
    assert rich_topology_fixture["nacl_id"] in _node_ids(topo, "network_acl")
    assert rich_topology_fixture["eni_id"] in _node_ids(topo, "network_interface")
    assert rich_topology_fixture["pcx_id"] in _node_ids(topo, "vpc_peering_connection")
    assert rich_topology_fixture["vpce_id"] in _node_ids(topo, "vpc_endpoint")
    assert rich_topology_fixture["lb_arn"] in _node_ids(topo, "load_balancer")
    assert rich_topology_fixture["tg_arn"] in _node_ids(topo, "target_group")

    # The out-of-scope VGW must NOT be fabricated as a node.
    assert rich_topology_fixture["vgw_id"] not in {n.node_id for n in topo.nodes}


def test_topology_edges_have_relationship_and_evidence(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    assert len(topo.edges) > 0
    for edge in topo.edges:
        assert edge.relationship
        assert edge.evidence
        assert edge.source_id
        assert edge.target_id


def test_topology_vpc_contains_subnet_edge(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    assert any(
        e.relationship == "contains"
        and e.source_id == rich_topology_fixture["vpc_id"]
        and e.target_id == rich_topology_fixture["subnet_id"]
        for e in topo.edges
    )


def test_topology_route_to_igw_edge(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    assert any(
        e.relationship == "routes_to"
        and e.source_id == rich_topology_fixture["route_table_id"]
        and e.target_id == rich_topology_fixture["igw_id"]
        for e in topo.edges
    )


def test_topology_orphan_reference_to_out_of_scope_vgw(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    """A route to a resource type outside this milestone's coverage (a VPN
    gateway) must still produce an edge -- with no corresponding node --
    plus a warning, never a crash or a silently dropped route."""
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    vgw_id = rich_topology_fixture["vgw_id"]

    orphan_edges = [e for e in topo.edges if e.target_id == vgw_id]
    assert len(orphan_edges) == 1
    assert orphan_edges[0].relationship == "routes_to"
    assert vgw_id not in {n.node_id for n in topo.nodes}
    assert any(w.code == "OUT_OF_SCOPE_TARGET" and vgw_id in w.message for w in topo.warnings)


def test_topology_orphan_reference_to_peer_vpc_outside_scope(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    """The peered VPC on the other side of a peering connection is outside
    this topology's single-VPC scope; it must appear as an edge target
    without a node, plus a warning."""
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    peer_vpc_id = rich_topology_fixture["peer_vpc_id"]

    assert any(
        e.relationship == "peers_with_vpc" and e.target_id == peer_vpc_id for e in topo.edges
    )
    assert peer_vpc_id not in {n.node_id for n in topo.nodes}
    assert any(w.code == "OUT_OF_SCOPE_TARGET" and peer_vpc_id in w.message for w in topo.warnings)


def test_topology_deterministic_across_repeated_calls(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    topo_a = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    topo_b = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )

    keys_a = [(n.node_type, n.node_id) for n in topo_a.nodes]
    keys_b = [(n.node_type, n.node_id) for n in topo_b.nodes]
    assert keys_a == keys_b
    assert keys_a == sorted(keys_a)  # nodes sorted by (node_type, node_id)

    edges_a = [(e.source_id, e.target_id, e.relationship) for e in topo_a.edges]
    edges_b = [(e.source_id, e.target_id, e.relationship) for e in topo_b.edges]
    assert edges_a == edges_b
    assert edges_a == sorted(edges_a)


def test_topology_tracks_api_call_count(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    """Recorded-call-budget test: topology assembly must report a positive,
    bounded call count rather than leaving callers unable to reason about
    the API cost of a single aws_get_vpc_topology invocation."""
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    # One call per resource-type collector (VPC, subnets, route tables,
    # IGWs, EIGWs, NAT gateways, SGs [x2: groups + rules], NACLs, ENIs,
    # peering, endpoints, LBs [x2: LBs + target groups], listeners,
    # managed prefix lists for the referenced pl if any) -- assert a
    # generous, non-brittle upper bound rather than an exact count that
    # would break on every unrelated collector change.
    assert 5 <= topo.api_call_count <= 40


def test_topology_zero_resources_for_empty_vpc(client_factory: ClientFactory) -> None:
    """A brand-new VPC still has the resources AWS creates automatically
    (a main route table, a default NACL, a default security group) --
    "zero resources" here means zero *user-created* resources, not a
    literally empty topology."""
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.5.0.0/16")["Vpc"]

        topo = get_vpc_topology(client_factory, region="us-east-1", vpc_id=vpc["VpcId"])

        node_types = {n.node_type for n in topo.nodes}
        assert node_types == {"vpc", "route_table", "network_acl", "security_group"}
        assert not any(n.node_type == "subnet" for n in topo.nodes)
        assert not any(n.node_type == "internet_gateway" for n in topo.nodes)
        assert topo.warnings == []
        assert topo.api_call_count > 0


def test_topology_raises_resource_not_found_for_unknown_vpc(client_factory: ClientFactory) -> None:
    with mock_aws(), pytest.raises(ResourceNotFoundError):
        get_vpc_topology(client_factory, region="us-east-1", vpc_id="vpc-doesnotexist")


def test_topology_local_route_edge(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    assert any(
        e.relationship == "local_route"
        and e.source_id == rich_topology_fixture["route_table_id"]
        and e.target_id == rich_topology_fixture["vpc_id"]
        for e in topo.edges
    )


def test_topology_eni_member_of_security_group_edge(
    client_factory: ClientFactory, rich_topology_fixture: dict[str, str]
) -> None:
    topo = get_vpc_topology(
        client_factory, region="us-east-1", vpc_id=rich_topology_fixture["vpc_id"]
    )
    assert any(
        e.relationship == "member_of"
        and e.source_id == rich_topology_fixture["eni_id"]
        and e.target_id == rich_topology_fixture["sg_id"]
        for e in topo.edges
    )
