from __future__ import annotations

import json
from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber
from moto import mock_aws

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.directconnect import (
    list_direct_connect_connections,
    list_direct_connect_gateways,
    list_direct_connect_lags,
    list_direct_connect_virtual_interfaces,
)


@pytest.fixture
def dx_connection_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        dx = boto3.client("directconnect", region_name="us-east-1")
        conn = dx.create_connection(location="EqDC2", bandwidth="1Gbps", connectionName="test-conn")
        lag = dx.create_lag(
            numberOfConnections=1,
            location="EqDC2",
            connectionsBandwidth="1Gbps",
            lagName="test-lag",
        )
        yield {"connection_id": conn["connectionId"], "lag_id": lag["lagId"]}


def test_list_direct_connect_connections(
    client_factory: ClientFactory, dx_connection_fixture: dict[str, str]
) -> None:
    connections = list_direct_connect_connections(client_factory, region="us-east-1")
    match = next(
        c for c in connections if c.connection_id == dx_connection_fixture["connection_id"]
    )
    assert match.connection_name == "test-conn"
    assert match.bandwidth == "1Gbps"
    assert match.account_id == "123456789012"


def test_list_direct_connect_lags(
    client_factory: ClientFactory, dx_connection_fixture: dict[str, str]
) -> None:
    lags = list_direct_connect_lags(client_factory, region="us-east-1")
    match = next(lag for lag in lags if lag.lag_id == dx_connection_fixture["lag_id"])
    assert match.lag_name == "test-lag"


def test_list_direct_connect_connections_zero_resources(client_factory: ClientFactory) -> None:
    with mock_aws():
        assert list_direct_connect_connections(client_factory, region="us-east-1") == []


# --- Stubber-based tests -----------------------------------------------------
#
# moto does not implement directconnect:DescribeVirtualInterfaces or
# DescribeDirectConnectGateways (NotImplementedError). These are stubbed
# against the real botocore service model instead, since the security-
# critical assertion (no BGP auth key ever surfaces) can only be tested
# against a fixture that actually contains one.

_VIF_RESPONSE_WITH_AUTH_KEY = {
    "virtualInterfaces": [
        {
            "virtualInterfaceId": "dxvif-abc123",
            "virtualInterfaceName": "test-vif",
            "virtualInterfaceType": "private",
            "virtualInterfaceState": "available",
            "connectionId": "dxcon-abc123",
            "vlan": 100,
            "asn": 65000,
            "authKey": "super-secret-bgp-md5-key",
            "amazonAddress": "192.168.1.1/30",
            "customerAddress": "192.168.1.2/30",
            "addressFamily": "ipv4",
            "customerRouterConfig": (
                "<?xml version='1.0'?><config>"
                "<auth_key>super-secret-bgp-md5-key</auth_key></config>"
            ),
            "routeFilterPrefixes": [{"cidr": "10.0.0.0/24"}],
            "bgpPeers": [
                {
                    "bgpPeerId": "peer-1",
                    "asn": 65000,
                    "authKey": "another-secret-key",
                    "addressFamily": "ipv4",
                    "bgpPeerState": "available",
                    "bgpStatus": "up",
                }
            ],
        }
    ]
}


def test_direct_connect_virtual_interface_never_leaks_auth_key(
    client_factory: ClientFactory,
) -> None:
    real_client = boto3.client("directconnect", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response("describe_virtual_interfaces", _VIF_RESPONSE_WITH_AUTH_KEY, {})
    stubber.activate()

    # Pre-warm the account-id cache so get_account_id() doesn't try to route
    # an STS call through the stubbed directconnect client.
    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        vifs = list_direct_connect_virtual_interfaces(client_factory, region="us-east-1")

    assert len(vifs) == 1
    serialized = json.dumps(vifs[0].model_dump())
    assert "super-secret-bgp-md5-key" not in serialized
    assert "another-secret-key" not in serialized
    assert "authkey" not in serialized.lower()
    assert "customer_router_config" not in serialized.lower()
    assert vifs[0].bgp_peers[0].bgp_peer_id == "peer-1"
    assert vifs[0].bgp_peers[0].bgp_status == "up"
    assert vifs[0].redacted is True
    stubber.assert_no_pending_responses()


def test_list_direct_connect_gateways_with_associations(client_factory: ClientFactory) -> None:
    real_client = boto3.client("directconnect", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "describe_direct_connect_gateways",
        {
            "directConnectGateways": [
                {
                    "directConnectGatewayId": "dxgw-abc123",
                    "directConnectGatewayName": "test-dxgw",
                    "directConnectGatewayState": "available",
                    "amazonSideAsn": 64512,
                    "ownerAccount": "123456789012",
                }
            ]
        },
        {},
    )
    stubber.add_response(
        "describe_direct_connect_gateway_associations",
        {
            "directConnectGatewayAssociations": [
                {
                    "associationId": "assoc-1",
                    "directConnectGatewayId": "dxgw-abc123",
                    "associatedGateway": {"id": "tgw-abc123", "type": "transitGateway"},
                    "associationState": "associated",
                    "allowedPrefixesToDirectConnectGateway": [{"cidr": "10.0.0.0/16"}],
                }
            ]
        },
        {"directConnectGatewayId": "dxgw-abc123"},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        gateways = list_direct_connect_gateways(
            client_factory, region="us-east-1", include_associations=True
        )

    assert len(gateways) == 1
    gw = gateways[0]
    assert gw.scope == "global"
    assert len(gw.associations) == 1
    assert gw.associations[0].associated_gateway_id == "tgw-abc123"
    assert gw.associations[0].associated_gateway_type == "transitGateway"
    stubber.assert_no_pending_responses()
