from __future__ import annotations

from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber
from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.transit_gateway import (
    list_transit_gateway_attachments,
    list_transit_gateway_route_tables,
    list_transit_gateways,
    search_transit_gateway_routes,
)
from aws_cloudops_mcp.config import Settings


@pytest.fixture
def tgw_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        tgw = ec2.create_transit_gateway(Description="hub")["TransitGateway"]
        rt = ec2.create_transit_gateway_route_table(TransitGatewayId=tgw["TransitGatewayId"])[
            "TransitGatewayRouteTable"
        ]
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
        att = ec2.create_transit_gateway_vpc_attachment(
            TransitGatewayId=tgw["TransitGatewayId"],
            VpcId=vpc["VpcId"],
            SubnetIds=[subnet["SubnetId"]],
        )["TransitGatewayVpcAttachment"]
        ec2.associate_transit_gateway_route_table(
            TransitGatewayRouteTableId=rt["TransitGatewayRouteTableId"],
            TransitGatewayAttachmentId=att["TransitGatewayAttachmentId"],
        )
        ec2.enable_transit_gateway_route_table_propagation(
            TransitGatewayRouteTableId=rt["TransitGatewayRouteTableId"],
            TransitGatewayAttachmentId=att["TransitGatewayAttachmentId"],
        )
        ec2.create_transit_gateway_route(
            TransitGatewayRouteTableId=rt["TransitGatewayRouteTableId"],
            DestinationCidrBlock="10.0.0.0/16",
            TransitGatewayAttachmentId=att["TransitGatewayAttachmentId"],
        )
        yield {
            "tgw_id": tgw["TransitGatewayId"],
            "rt_id": rt["TransitGatewayRouteTableId"],
            "vpc_id": vpc["VpcId"],
            "att_id": att["TransitGatewayAttachmentId"],
        }


def test_list_transit_gateways(client_factory: ClientFactory, tgw_fixture: dict[str, str]) -> None:
    tgws = list_transit_gateways(client_factory, region="us-east-1")
    match = next(t for t in tgws if t.transit_gateway_id == tgw_fixture["tgw_id"])
    assert match.state == "available"
    assert match.account_id == "123456789012"
    assert match.source_api == "ec2:DescribeTransitGateways"


def test_list_transit_gateway_attachments_covers_vpc_type(
    client_factory: ClientFactory, tgw_fixture: dict[str, str]
) -> None:
    atts = list_transit_gateway_attachments(
        client_factory, region="us-east-1", transit_gateway_id=tgw_fixture["tgw_id"]
    )
    match = next(a for a in atts if a.transit_gateway_attachment_id == tgw_fixture["att_id"])
    assert match.resource_type == "vpc"
    assert match.resource_id == tgw_fixture["vpc_id"]


def test_list_transit_gateway_attachments_filters_by_resource_type(
    client_factory: ClientFactory, tgw_fixture: dict[str, str]
) -> None:
    atts = list_transit_gateway_attachments(
        client_factory,
        region="us-east-1",
        transit_gateway_id=tgw_fixture["tgw_id"],
        resource_type="vpn",
    )
    assert atts == []


def test_list_transit_gateway_route_tables_without_enrichment(
    client_factory: ClientFactory, tgw_fixture: dict[str, str]
) -> None:
    result = list_transit_gateway_route_tables(
        client_factory, region="us-east-1", transit_gateway_id=tgw_fixture["tgw_id"]
    )
    match = next(
        rt for rt in result.data if rt.transit_gateway_route_table_id == tgw_fixture["rt_id"]
    )
    assert match.associations is None
    assert match.propagations is None
    assert result.warnings == []


def test_list_transit_gateway_route_tables_with_enrichment(
    client_factory: ClientFactory, tgw_fixture: dict[str, str]
) -> None:
    result = list_transit_gateway_route_tables(
        client_factory,
        region="us-east-1",
        transit_gateway_id=tgw_fixture["tgw_id"],
        include_associations=True,
        include_propagations=True,
    )
    match = next(
        rt for rt in result.data if rt.transit_gateway_route_table_id == tgw_fixture["rt_id"]
    )
    assert match.associations is not None
    assert any(a.resource_id == tgw_fixture["vpc_id"] for a in match.associations)
    assert match.propagations is not None
    assert any(p.resource_id == tgw_fixture["vpc_id"] for p in match.propagations)


def test_transit_gateway_route_table_enrichment_respects_fanout_cap(
    tgw_fixture: dict[str, str],
) -> None:
    settings = Settings(aws_default_region="us-east-1", max_fanout_calls=0)
    client_factory = ClientFactory(settings, SessionManager(settings))

    result = list_transit_gateway_route_tables(
        client_factory,
        region="us-east-1",
        transit_gateway_id=tgw_fixture["tgw_id"],
        include_associations=True,
    )
    match = next(
        rt for rt in result.data if rt.transit_gateway_route_table_id == tgw_fixture["rt_id"]
    )
    assert match.associations is None
    assert any(w.code == "FANOUT_CAP_REACHED" for w in result.warnings)


def _stubbed_search_response(routes: list[dict]) -> dict:
    return {"Routes": routes, "AdditionalRoutesAvailable": False}


def test_search_transit_gateway_routes_finds_static_route(client_factory: ClientFactory) -> None:
    """moto's SearchTransitGatewayRoutes crashes whenever MaxResults is
    passed (a dict is sliced with a slice object) -- our product code
    always sets MaxResults, so this call can never succeed against moto.
    Stubbed against the real botocore service model instead."""
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "search_transit_gateway_routes",
        _stubbed_search_response(
            [{"DestinationCidrBlock": "10.0.0.0/16", "Type": "static", "State": "active"}]
        ),
        {
            "TransitGatewayRouteTableId": "tgw-rtb-000",
            "Filters": [{"Name": "type", "Values": ["static", "propagated"]}],
            "MaxResults": 100,
        },
    )
    stubber.activate()

    with patch.object(client_factory, "get_client", return_value=real_client):
        routes = search_transit_gateway_routes(
            client_factory, region="us-east-1", transit_gateway_route_table_id="tgw-rtb-000"
        )
    assert len(routes) == 1
    assert routes[0].destination_cidr_block == "10.0.0.0/16"
    assert routes[0].route_type == "static"
    stubber.assert_no_pending_responses()


def test_search_transit_gateway_routes_exact_match_filter(client_factory: ClientFactory) -> None:
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "search_transit_gateway_routes",
        _stubbed_search_response(
            [{"DestinationCidrBlock": "10.0.0.0/16", "Type": "static", "State": "active"}]
        ),
        {
            "TransitGatewayRouteTableId": "tgw-rtb-000",
            "Filters": [{"Name": "route-search.exact-match", "Values": ["10.0.0.0/16"]}],
            "MaxResults": 100,
        },
    )
    stubber.activate()

    with patch.object(client_factory, "get_client", return_value=real_client):
        routes = search_transit_gateway_routes(
            client_factory,
            region="us-east-1",
            transit_gateway_route_table_id="tgw-rtb-000",
            destination_cidr_block="10.0.0.0/16",
        )
    assert len(routes) == 1
    stubber.assert_no_pending_responses()


def test_search_transit_gateway_routes_caps_max_results_below_aws_minimum(
    client_factory: ClientFactory,
) -> None:
    """AWS enforces MaxResults >= 5; a caller asking for fewer (e.g. 1)
    should still only get back the number they asked for, even though the
    underlying AWS call requests AWS's minimum of 5."""
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "search_transit_gateway_routes",
        _stubbed_search_response(
            [
                {"DestinationCidrBlock": f"10.{i}.0.0/16", "Type": "static", "State": "active"}
                for i in range(5)
            ]
        ),
        {
            "TransitGatewayRouteTableId": "tgw-rtb-000",
            "Filters": [{"Name": "type", "Values": ["static", "propagated"]}],
            "MaxResults": 5,  # clamped up from the caller's max_results=1
        },
    )
    stubber.activate()

    with patch.object(client_factory, "get_client", return_value=real_client):
        routes = search_transit_gateway_routes(
            client_factory,
            region="us-east-1",
            transit_gateway_route_table_id="tgw-rtb-000",
            max_results=1,
        )
    assert len(routes) == 1
    stubber.assert_no_pending_responses()


def test_list_transit_gateways_zero_resources_for_unmatched_id(
    client_factory: ClientFactory,
) -> None:
    with mock_aws():
        assert (
            list_transit_gateways(
                client_factory, region="us-east-1", transit_gateway_ids=["tgw-doesnotexist"]
            )
            == []
        )
