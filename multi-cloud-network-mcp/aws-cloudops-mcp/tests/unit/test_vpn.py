from __future__ import annotations

import json
import re

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.vpn import list_customer_gateways, list_vpn_connections, list_vpn_gateways


@pytest.fixture
def vpn_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        cgw = ec2.create_customer_gateway(Type="ipsec.1", PublicIp="203.0.113.1", BgpAsn=65000)[
            "CustomerGateway"
        ]
        vgw = ec2.create_vpn_gateway(Type="ipsec.1")["VpnGateway"]
        conn = ec2.create_vpn_connection(
            Type="ipsec.1",
            CustomerGatewayId=cgw["CustomerGatewayId"],
            VpnGatewayId=vgw["VpnGatewayId"],
            Options={"StaticRoutesOnly": True},
        )["VpnConnection"]
        yield {
            "cgw_id": cgw["CustomerGatewayId"],
            "vgw_id": vgw["VpnGatewayId"],
            "conn_id": conn["VpnConnectionId"],
        }


def test_vpn_connection_never_leaks_pre_shared_key(
    client_factory: ClientFactory, vpn_fixture: dict[str, str]
) -> None:
    """moto's DescribeVpnConnections response embeds the IKE pre-shared key
    in plaintext inside CustomerGatewayConfiguration (an AWS behavior, not
    a moto quirk -- real AWS does the same). This is the single most
    security-critical assertion in this milestone: no normalized field, at
    any nesting depth, may contain that secret."""
    connections = list_vpn_connections(client_factory, region="us-east-1")
    match = next(c for c in connections if c.vpn_connection_id == vpn_fixture["conn_id"])

    # Confirm the raw AWS response actually does contain a PSK (otherwise
    # this test would trivially pass without proving anything).
    raw = boto3.client("ec2", region_name="us-east-1").describe_vpn_connections(
        VpnConnectionIds=[vpn_fixture["conn_id"]]
    )
    raw_config = raw["VpnConnections"][0]["CustomerGatewayConfiguration"]
    assert "pre_shared_key" in raw_config

    serialized = json.dumps(match.model_dump())
    assert "pre_shared_key" not in serialized.lower()
    assert "customer_gateway_configuration" not in serialized.lower()
    # The actual secret value AWS generated, if it leaked anywhere, would
    # show up verbatim -- extract it and check for its literal presence too.
    psk_match = re.search(r"<pre_shared_key>([^<]+)</pre_shared_key>", raw_config)
    assert psk_match is not None
    assert psk_match.group(1) not in serialized

    assert match.redacted is True


def test_vpn_connection_normalizes_basic_fields(
    client_factory: ClientFactory, vpn_fixture: dict[str, str]
) -> None:
    connections = list_vpn_connections(client_factory, region="us-east-1")
    match = next(c for c in connections if c.vpn_connection_id == vpn_fixture["conn_id"])
    assert match.state == "available"
    assert match.customer_gateway_id == vpn_fixture["cgw_id"]
    assert match.vpn_gateway_id == vpn_fixture["vgw_id"]
    assert match.account_id == "123456789012"


def test_list_vpn_connections_filters_by_id(
    client_factory: ClientFactory, vpn_fixture: dict[str, str]
) -> None:
    connections = list_vpn_connections(
        client_factory, region="us-east-1", vpn_connection_ids=[vpn_fixture["conn_id"]]
    )
    assert [c.vpn_connection_id for c in connections] == [vpn_fixture["conn_id"]]


def test_list_customer_gateways(client_factory: ClientFactory, vpn_fixture: dict[str, str]) -> None:
    gateways = list_customer_gateways(client_factory, region="us-east-1")
    match = next(g for g in gateways if g.customer_gateway_id == vpn_fixture["cgw_id"])
    assert match.ip_address == "203.0.113.1"
    assert match.bgp_asn == "65000"
    assert match.state == "available"


def test_list_vpn_gateways(client_factory: ClientFactory, vpn_fixture: dict[str, str]) -> None:
    gateways = list_vpn_gateways(client_factory, region="us-east-1")
    match = next(g for g in gateways if g.vpn_gateway_id == vpn_fixture["vgw_id"])
    assert match.state == "available"
    assert match.gateway_type == "ipsec.1"


def test_list_vpn_connections_zero_resources(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert list_vpn_connections(client_factory, region="us-east-1") == []
