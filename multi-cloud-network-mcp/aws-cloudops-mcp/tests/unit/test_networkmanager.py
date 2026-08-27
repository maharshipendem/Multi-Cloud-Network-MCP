from __future__ import annotations

from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber
from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.networkmanager import (
    list_core_networks,
    list_global_networks,
    list_network_manager_connections,
    list_network_manager_devices,
    list_network_manager_links,
    list_network_manager_sites,
    list_transit_gateway_registrations,
)
from aws_cloudops_mcp.config import Settings


@pytest.fixture
def nm_fixture(client_factory: ClientFactory) -> dict[str, str]:
    with mock_aws():
        nm = boto3.client("networkmanager", region_name="us-east-1")
        gn = nm.create_global_network(Description="test global network")["GlobalNetwork"]
        site = nm.create_site(GlobalNetworkId=gn["GlobalNetworkId"], Description="hq")["Site"]
        device = nm.create_device(
            GlobalNetworkId=gn["GlobalNetworkId"], SiteId=site["SiteId"], Description="router"
        )["Device"]
        link = nm.create_link(
            GlobalNetworkId=gn["GlobalNetworkId"],
            SiteId=site["SiteId"],
            Bandwidth={"UploadSpeed": 100, "DownloadSpeed": 100},
        )["Link"]
        core_network = nm.create_core_network(GlobalNetworkId=gn["GlobalNetworkId"])["CoreNetwork"]
        yield {
            "global_network_id": gn["GlobalNetworkId"],
            "site_id": site["SiteId"],
            "device_id": device["DeviceId"],
            "link_id": link["LinkId"],
            "core_network_id": core_network["CoreNetworkId"],
        }


def test_list_global_networks(client_factory: ClientFactory, nm_fixture: dict[str, str]) -> None:
    networks = list_global_networks(client_factory, region="us-east-1")
    match = next(n for n in networks if n.global_network_id == nm_fixture["global_network_id"])
    assert match.scope == "global"
    assert match.state == "AVAILABLE"


def test_list_network_manager_sites(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    sites = list_network_manager_sites(
        client_factory, region="us-east-1", global_network_id=nm_fixture["global_network_id"]
    )
    match = next(s for s in sites if s.site_id == nm_fixture["site_id"])
    assert match.description == "hq"


def test_list_network_manager_devices(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    devices = list_network_manager_devices(
        client_factory, region="us-east-1", global_network_id=nm_fixture["global_network_id"]
    )
    match = next(d for d in devices if d.device_id == nm_fixture["device_id"])
    assert match.site_id == nm_fixture["site_id"]


def test_list_network_manager_links(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    links = list_network_manager_links(
        client_factory, region="us-east-1", global_network_id=nm_fixture["global_network_id"]
    )
    match = next(link for link in links if link.link_id == nm_fixture["link_id"])
    assert match.bandwidth is not None
    assert match.bandwidth.upload_speed == 100


def test_list_core_networks_without_enrichment(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    result = list_core_networks(client_factory, region="us-east-1")
    match = next(cn for cn in result.data if cn.core_network_id == nm_fixture["core_network_id"])
    assert match.segments is None
    assert match.policy_document is None
    assert result.warnings == []


def test_list_core_networks_with_details(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    result = list_core_networks(client_factory, region="us-east-1", include_details=True)
    match = next(cn for cn in result.data if cn.core_network_id == nm_fixture["core_network_id"])
    assert match.segments == []  # moto's GetCoreNetwork returns no segments, but the call succeeds
    assert match.collection_completeness == "complete"


def test_list_core_networks_policy_degrades_when_unsupported(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    """moto does not implement GetCoreNetworkPolicy -- exactly the
    "account and SDK support them; return explicit unsupported-capability
    metadata otherwise" scenario the milestone asks for."""
    result = list_core_networks(client_factory, region="us-east-1", include_policy=True)
    match = next(cn for cn in result.data if cn.core_network_id == nm_fixture["core_network_id"])
    assert match.policy_document is None
    assert match.collection_completeness == "partial"
    assert any(w.code == "UNSUPPORTED_CAPABILITY" for w in result.warnings)


def test_list_core_networks_details_degrade_when_get_core_network_denied(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    real_client = boto3.client("networkmanager", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "list_core_networks",
        {
            "CoreNetworks": [
                {
                    "CoreNetworkId": nm_fixture["core_network_id"],
                    "GlobalNetworkId": nm_fixture["global_network_id"],
                    "State": "AVAILABLE",
                }
            ]
        },
        {},
    )
    stubber.add_client_error(
        "get_core_network",
        service_error_code="AccessDeniedException",
        service_message="User is not authorized to perform this action",
        http_status_code=403,
        expected_params={"CoreNetworkId": nm_fixture["core_network_id"]},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        result = list_core_networks(client_factory, region="us-east-1", include_details=True)

    match = next(cn for cn in result.data if cn.core_network_id == nm_fixture["core_network_id"])
    assert match.segments is None
    assert match.collection_completeness == "partial"
    assert any(w.code == "UNSUPPORTED_CAPABILITY" for w in result.warnings)
    stubber.assert_no_pending_responses()


def test_list_core_networks_policy_happy_path_with_truncation(
    client_factory: ClientFactory, nm_fixture: dict[str, str]
) -> None:
    real_client = boto3.client("networkmanager", region_name="us-east-1")
    stubber = Stubber(real_client)
    long_policy = "x" * 10_000
    stubber.add_response(
        "list_core_networks",
        {
            "CoreNetworks": [
                {
                    "CoreNetworkId": nm_fixture["core_network_id"],
                    "GlobalNetworkId": nm_fixture["global_network_id"],
                    "State": "AVAILABLE",
                }
            ]
        },
        {},
    )
    stubber.add_response(
        "get_core_network_policy",
        {"CoreNetworkPolicy": {"PolicyDocument": long_policy}},
        {"CoreNetworkId": nm_fixture["core_network_id"]},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        result = list_core_networks(client_factory, region="us-east-1", include_policy=True)

    match = next(cn for cn in result.data if cn.core_network_id == nm_fixture["core_network_id"])
    assert match.policy_document is not None
    assert match.policy_document_truncated is True
    assert len(match.policy_document) < len(long_policy)
    assert result.warnings == []
    stubber.assert_no_pending_responses()


def test_list_core_networks_policy_fanout_cap_reached(nm_fixture: dict[str, str]) -> None:
    settings = Settings(aws_default_region="us-east-1", max_fanout_calls=0)
    client_factory = ClientFactory(settings, SessionManager(settings))

    result = list_core_networks(client_factory, region="us-east-1", include_policy=True)
    match = next(cn for cn in result.data if cn.core_network_id == nm_fixture["core_network_id"])
    assert match.policy_document is None
    assert match.collection_completeness == "partial"
    assert any(
        w.code == "FANOUT_CAP_REACHED" and w.resource_type == "core_network_policy"
        for w in result.warnings
    )


def test_list_core_networks_zero_resources_for_account_with_no_cloud_wan(
    client_factory: ClientFactory,
) -> None:
    """An account that has never used Cloud WAN returns an empty list --
    the normal, non-error case, not something that should look like a
    failure."""
    with mock_aws():
        result = list_core_networks(client_factory, region="us-east-1")
        assert result.data == []
        assert result.warnings == []


# --- Stubber-based tests -----------------------------------------------------
#
# moto's GetConnections/GetTransitGatewayRegistrations return "Not yet
# implemented" (a real ClientError, but not representative of the actual
# AWS response shape needed to test normalization).


def test_list_network_manager_connections(client_factory: ClientFactory) -> None:
    real_client = boto3.client("networkmanager", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "get_connections",
        {
            "Connections": [
                {
                    "ConnectionId": "connection-abc123",
                    "GlobalNetworkId": "global-network-abc123",
                    "DeviceId": "device-1",
                    "ConnectedDeviceId": "device-2",
                    "State": "AVAILABLE",
                }
            ]
        },
        {"GlobalNetworkId": "global-network-abc123"},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        connections = list_network_manager_connections(
            client_factory, region="us-east-1", global_network_id="global-network-abc123"
        )

    assert len(connections) == 1
    assert connections[0].device_id == "device-1"
    assert connections[0].scope == "global"
    stubber.assert_no_pending_responses()


def test_list_transit_gateway_registrations(client_factory: ClientFactory) -> None:
    real_client = boto3.client("networkmanager", region_name="us-east-1")
    stubber = Stubber(real_client)
    tgw_arn = "arn:aws:ec2:us-east-1:123456789012:transit-gateway/tgw-abc123"
    stubber.add_response(
        "get_transit_gateway_registrations",
        {
            "TransitGatewayRegistrations": [
                {
                    "GlobalNetworkId": "global-network-abc123",
                    "TransitGatewayArn": tgw_arn,
                    "State": {"Code": "AVAILABLE"},
                }
            ]
        },
        {"GlobalNetworkId": "global-network-abc123"},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        registrations = list_transit_gateway_registrations(
            client_factory, region="us-east-1", global_network_id="global-network-abc123"
        )

    assert len(registrations) == 1
    assert registrations[0].state == "AVAILABLE"
    stubber.assert_no_pending_responses()
