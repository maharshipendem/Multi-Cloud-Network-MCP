from __future__ import annotations

from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.snapshot import collect_network_snapshot
from aws_cloudops_mcp.config import Settings
from aws_cloudops_mcp.diagnostics.risks import find_network_risks
from aws_cloudops_mcp.diagnostics.routing import resolve_path


@pytest.fixture
def snapshot_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        vpc_id = vpc["VpcId"]
        subnet_a = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")["Subnet"]
        subnet_b = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.2.0/24")["Subnet"]
        rt = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]
        ec2.associate_route_table(RouteTableId=rt["RouteTableId"], SubnetId=subnet_a["SubnetId"])
        ec2.associate_route_table(RouteTableId=rt["RouteTableId"], SubnetId=subnet_b["SubnetId"])

        other_vpc = ec2.create_vpc(CidrBlock="10.9.0.0/16")["Vpc"]

        yield {
            "vpc_id": vpc_id,
            "subnet_a_id": subnet_a["SubnetId"],
            "subnet_b_id": subnet_b["SubnetId"],
            "other_vpc_id": other_vpc["VpcId"],
        }


def test_collect_network_snapshot_feeds_routing_engine(
    client_factory: ClientFactory, snapshot_fixture: dict[str, str]
) -> None:
    """End-to-end proof: a snapshot collected via real (moto-mocked) AWS
    calls is directly consumable by the diagnostics engine without any
    adaptation -- the whole point of the layering."""
    snapshot = collect_network_snapshot(client_factory, region="us-east-1")

    assert snapshot.region == "us-east-1"
    assert snapshot.account_id == "123456789012"
    assert any(v.vpc_id == snapshot_fixture["vpc_id"] for v in snapshot.vpcs)

    result = resolve_path(
        snapshot,
        source_subnet_id=snapshot_fixture["subnet_a_id"],
        destination="10.0.2.5",
    )
    assert result.verdict == "routable"


def test_collect_network_snapshot_filters_by_vpc_ids(
    client_factory: ClientFactory, snapshot_fixture: dict[str, str]
) -> None:
    snapshot = collect_network_snapshot(
        client_factory, region="us-east-1", vpc_ids=[snapshot_fixture["vpc_id"]]
    )
    vpc_ids_in_snapshot = {v.vpc_id for v in snapshot.vpcs}
    assert snapshot_fixture["vpc_id"] in vpc_ids_in_snapshot
    assert snapshot_fixture["other_vpc_id"] not in vpc_ids_in_snapshot
    assert all(s.vpc_id == snapshot_fixture["vpc_id"] for s in snapshot.subnets)


def test_collect_network_snapshot_skips_transit_gateway_and_vpn_by_default(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        snapshot = collect_network_snapshot(client_factory, region="us-east-1")
    assert snapshot.transit_gateways == []
    assert snapshot.vpn_connections == []


def test_collect_network_snapshot_includes_transit_gateway_when_opted_in(
    client_factory: ClientFactory,
) -> None:
    """moto's SearchTransitGatewayRoutes crashes on any non-null MaxResults
    (a genuine moto bug, already documented and worked around with
    Stubber in tests/unit/test_transit_gateway.py) -- the route-search
    call itself is patched out here since this test's purpose is
    verifying the collector wires TGWs/attachments/route tables into the
    snapshot, not re-proving route-search correctness."""
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        tgw = ec2.create_transit_gateway(Description="test")["TransitGateway"]

        with patch("aws_cloudops_mcp.aws.snapshot.search_transit_gateway_routes", return_value=[]):
            snapshot = collect_network_snapshot(
                client_factory, region="us-east-1", include_transit_gateway=True
            )
    assert any(t.transit_gateway_id == tgw["TransitGatewayId"] for t in snapshot.transit_gateways)


def test_collect_network_snapshot_propagates_partial_result_warnings() -> None:
    """Scenario: partial permissions -- a bounded enrichment call that
    can't complete (here, the fanout cap; the same CollectionWarning
    path a real AccessDenied on one enrichment call would take) must
    surface in NetworkSnapshot.warnings, and downstream diagnostics must
    keep working against the partial data rather than failing outright."""
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        tgw = ec2.create_transit_gateway(Description="test")["TransitGateway"]
        rt = ec2.create_transit_gateway_route_table(TransitGatewayId=tgw["TransitGatewayId"])[
            "TransitGatewayRouteTable"
        ]

        settings = Settings(aws_default_region="us-east-1", max_fanout_calls=0)
        limited_client_factory = ClientFactory(settings, SessionManager(settings))

        with patch("aws_cloudops_mcp.aws.snapshot.search_transit_gateway_routes", return_value=[]):
            snapshot = collect_network_snapshot(
                limited_client_factory, region="us-east-1", include_transit_gateway=True
            )

    assert any(w.code == "FANOUT_CAP_REACHED" for w in snapshot.warnings)
    assert any(
        rt["TransitGatewayRouteTableId"] == t.transit_gateway_route_table_id
        for t in snapshot.transit_gateway_route_tables
    )
    # Partial data must not prevent the risk scan from running -- it just
    # runs against what was actually collected.
    findings = find_network_risks(snapshot)
    assert findings is not None


def test_collect_network_snapshot_zero_resources(client_factory: ClientFactory) -> None:
    """A fresh moto account has a default VPC per region, exactly like a
    real AWS account -- "zero resources" here means zero of everything
    this milestone's diagnostics actually care about beyond that
    baseline, not a literally empty VPC list."""
    with mock_aws():
        snapshot = collect_network_snapshot(client_factory, region="us-east-1")
    assert all(v.is_default for v in snapshot.vpcs)
    assert snapshot.route_tables == [] or all(
        rt.vpc_id in {v.vpc_id for v in snapshot.vpcs} for rt in snapshot.route_tables
    )
    assert snapshot.nat_gateways == []
    assert snapshot.vpc_peering_connections == []
    assert snapshot.warnings == []
