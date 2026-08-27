from __future__ import annotations

from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.hybrid_topology import get_hybrid_topology
from aws_cloudops_mcp.exceptions import ResourceNotFoundError
from aws_cloudops_mcp.models.transit_gateway import TransitGatewayAttachment


@pytest.fixture
def hybrid_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
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
        vpc_att = ec2.create_transit_gateway_vpc_attachment(
            TransitGatewayId=tgw["TransitGatewayId"],
            VpcId=vpc["VpcId"],
            SubnetIds=[subnet_a["SubnetId"]],
        )["TransitGatewayVpcAttachment"]

        cgw = ec2.create_customer_gateway(Type="ipsec.1", PublicIp="203.0.113.9", BgpAsn=65000)[
            "CustomerGateway"
        ]
        vpn_conn = ec2.create_vpn_connection(
            Type="ipsec.1",
            CustomerGatewayId=cgw["CustomerGatewayId"],
            TransitGatewayId=tgw["TransitGatewayId"],
        )["VpnConnection"]

        zone = r53.create_hosted_zone(
            Name="private.example.com",
            CallerReference="test-ref",
            HostedZoneConfig={"PrivateZone": True},
            VPC={"VPCRegion": "us-east-1", "VPCId": vpc["VpcId"]},
        )["HostedZone"]

        sg = ec2.create_security_group(
            GroupName="resolver-sg", Description="t", VpcId=vpc["VpcId"]
        )["GroupId"]
        resolver_endpoint = r53r.create_resolver_endpoint(
            CreatorRequestId="req-1",
            SecurityGroupIds=[sg],
            Direction="OUTBOUND",
            IpAddresses=[
                {"SubnetId": subnet_a["SubnetId"]},
                {"SubnetId": subnet_b["SubnetId"]},
            ],
        )["ResolverEndpoint"]

        yield {
            "tgw_id": tgw["TransitGatewayId"],
            "vpc_id": vpc["VpcId"],
            "vpc_attachment_id": vpc_att["TransitGatewayAttachmentId"],
            "cgw_id": cgw["CustomerGatewayId"],
            "vpn_connection_id": vpn_conn["VpnConnectionId"],
            "hosted_zone_id": zone["Id"].removeprefix("/hostedzone/"),
            "resolver_endpoint_id": resolver_endpoint["Id"],
        }


def _node_ids(topology, node_type: str) -> set[str]:
    return {n.node_id for n in topology.nodes if n.node_type == node_type}


def test_hybrid_topology_joins_vpc_vpn_and_dns(
    client_factory: ClientFactory, hybrid_fixture: dict[str, str]
) -> None:
    topo = get_hybrid_topology(
        client_factory, region="us-east-1", transit_gateway_id=hybrid_fixture["tgw_id"]
    )

    assert _node_ids(topo, "transit_gateway") == {hybrid_fixture["tgw_id"]}
    assert hybrid_fixture["vpc_id"] in _node_ids(topo, "vpc")
    assert hybrid_fixture["vpn_connection_id"] in _node_ids(topo, "vpn_connection")
    assert hybrid_fixture["cgw_id"] in _node_ids(topo, "customer_gateway")
    assert hybrid_fixture["hosted_zone_id"] in _node_ids(topo, "hosted_zone")
    assert hybrid_fixture["resolver_endpoint_id"] in _node_ids(topo, "resolver_endpoint")


def test_hybrid_topology_labels_external_endpoint(
    client_factory: ClientFactory, hybrid_fixture: dict[str, str]
) -> None:
    """The customer gateway's public IP -- the genuine on-premises network
    boundary -- must be labeled as an explicit external_endpoint node, not
    left as an unresolved dangling reference."""
    topo = get_hybrid_topology(
        client_factory, region="us-east-1", transit_gateway_id=hybrid_fixture["tgw_id"]
    )
    external_nodes = [n for n in topo.nodes if n.node_type == "external_endpoint"]
    assert len(external_nodes) == 1
    assert external_nodes[0].label == "203.0.113.9"
    assert any(
        e.relationship == "represents" and e.target_id == external_nodes[0].node_id
        for e in topo.edges
    )


def test_hybrid_topology_edges_have_relationship_and_evidence(
    client_factory: ClientFactory, hybrid_fixture: dict[str, str]
) -> None:
    topo = get_hybrid_topology(
        client_factory, region="us-east-1", transit_gateway_id=hybrid_fixture["tgw_id"]
    )
    assert len(topo.edges) > 0
    for edge in topo.edges:
        assert edge.relationship
        assert edge.evidence


def test_hybrid_topology_deterministic_across_repeated_calls(
    client_factory: ClientFactory, hybrid_fixture: dict[str, str]
) -> None:
    topo_a = get_hybrid_topology(
        client_factory, region="us-east-1", transit_gateway_id=hybrid_fixture["tgw_id"]
    )
    topo_b = get_hybrid_topology(
        client_factory, region="us-east-1", transit_gateway_id=hybrid_fixture["tgw_id"]
    )
    keys_a = [(n.node_type, n.node_id) for n in topo_a.nodes]
    keys_b = [(n.node_type, n.node_id) for n in topo_b.nodes]
    assert keys_a == keys_b
    assert keys_a == sorted(keys_a)

    edges_a = [(e.source_id, e.target_id, e.relationship) for e in topo_a.edges]
    edges_b = [(e.source_id, e.target_id, e.relationship) for e in topo_b.edges]
    assert edges_a == edges_b
    assert edges_a == sorted(edges_a)


def test_hybrid_topology_tracks_api_call_count(
    client_factory: ClientFactory, hybrid_fixture: dict[str, str]
) -> None:
    topo = get_hybrid_topology(
        client_factory, region="us-east-1", transit_gateway_id=hybrid_fixture["tgw_id"]
    )
    assert 3 <= topo.api_call_count <= 30


def test_hybrid_topology_raises_resource_not_found_for_unknown_tgw(
    client_factory: ClientFactory,
) -> None:
    with mock_aws(), pytest.raises(ResourceNotFoundError):
        get_hybrid_topology(
            client_factory, region="us-east-1", transit_gateway_id="tgw-doesnotexist"
        )


def test_hybrid_topology_zero_attachments(client_factory: ClientFactory) -> None:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        tgw = ec2.create_transit_gateway(Description="empty hub")["TransitGateway"]

        topo = get_hybrid_topology(
            client_factory, region="us-east-1", transit_gateway_id=tgw["TransitGatewayId"]
        )
        assert {n.node_id for n in topo.nodes} == {tgw["TransitGatewayId"]}
        assert topo.edges == []
        assert topo.warnings == []


def test_hybrid_topology_flags_cross_account_attachment_and_out_of_scope_type(
    client_factory: ClientFactory,
) -> None:
    """moto cannot simulate a genuinely cross-account attachment or a DX
    gateway attachment (DescribeDirectConnectGateways isn't implemented),
    so this exercises get_hybrid_topology's attachment-handling logic
    directly against a synthetic, controlled attachment list."""
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        tgw = ec2.create_transit_gateway(Description="hub")["TransitGateway"]

        synthetic_attachments = [
            TransitGatewayAttachment(
                account_id="123456789012",
                region="us-east-1",
                observed_at="2026-01-01T00:00:00+00:00",
                transit_gateway_attachment_id="tgw-attach-crossacct",
                transit_gateway_id=tgw["TransitGatewayId"],
                resource_owner_id="999999999999",  # a different account
                resource_type="vpc",
                resource_id="vpc-otheracct",
                state="available",
            ),
            TransitGatewayAttachment(
                account_id="123456789012",
                region="us-east-1",
                observed_at="2026-01-01T00:00:00+00:00",
                transit_gateway_attachment_id="tgw-attach-peering",
                transit_gateway_id=tgw["TransitGatewayId"],
                resource_owner_id="123456789012",
                resource_type="peering",
                resource_id="tgw-attach-peer-xyz",
                state="available",
            ),
            TransitGatewayAttachment(
                account_id="123456789012",
                region="us-east-1",
                observed_at="2026-01-01T00:00:00+00:00",
                transit_gateway_attachment_id="tgw-attach-dxgw",
                transit_gateway_id=tgw["TransitGatewayId"],
                resource_owner_id="123456789012",
                resource_type="direct-connect-gateway",
                resource_id="dxgw-abc123",
                state="available",
            ),
        ]

        with patch(
            "aws_cloudops_mcp.aws.hybrid_topology.list_transit_gateway_attachments",
            return_value=synthetic_attachments,
        ):
            topo = get_hybrid_topology(
                client_factory, region="us-east-1", transit_gateway_id=tgw["TransitGatewayId"]
            )

    # Cross-account attachment: still a node (attachment-level metadata is
    # visible), plus a warning explaining the ownership boundary.
    assert "tgw-attach-crossacct" in {n.node_id for n in topo.nodes}
    assert any(w.code == "CROSS_ACCOUNT_ATTACHMENT" for w in topo.warnings)

    # Out-of-scope attachment type (peering): attachment node exists, but
    # the underlying resource is never fabricated as a node, and a warning
    # explains why.
    assert "tgw-attach-peering" in {n.node_id for n in topo.nodes}
    assert "tgw-attach-peer-xyz" not in {n.node_id for n in topo.nodes}
    assert any(w.code == "OUT_OF_SCOPE_TARGET" for w in topo.warnings)

    # Direct Connect gateway attachment: resolved into its own node.
    assert "dxgw-abc123" in {n.node_id for n in topo.nodes}
    assert any(
        e.source_id == "tgw-attach-dxgw" and e.target_id == "dxgw-abc123" for e in topo.edges
    )
