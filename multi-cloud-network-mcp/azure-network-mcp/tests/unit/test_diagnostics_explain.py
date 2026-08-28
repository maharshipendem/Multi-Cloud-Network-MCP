from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.diagnostics.explain import explain_network_path


def _wire_effective_route_and_nsg(
    network_client: MagicMock,
    *,
    next_hop_type: str = "VnetLocal",
    nsg_access: str = "Allow",
    route_prefix: str = "10.0.1.0/24",
) -> None:
    route_poller = MagicMock()
    route_poller.result.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(
                name="default",
                address_prefix=[route_prefix],
                next_hop_type=next_hop_type,
                next_hop_ip_address=[],
                source="Default",
                state="Active",
            )
        ]
    )
    network_client.network_interfaces.begin_get_effective_route_table.return_value = route_poller

    nsg_poller = MagicMock()
    nsg_poller.result.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(
                network_security_group=SimpleNamespace(id="nsg-1"),
                effective_security_rules=[
                    SimpleNamespace(
                        name="AllowHttps",
                        protocol="Tcp",
                        source_port_ranges=["*"],
                        destination_port_ranges=["443"],
                        source_address_prefixes=["*"],
                        destination_address_prefixes=["*"],
                        expanded_source_address_prefix=[],
                        expanded_destination_address_prefix=[],
                        access=nsg_access,
                        priority=100,
                        direction="Outbound",
                    )
                ],
            )
        ]
    )
    network_client.network_interfaces.begin_list_effective_network_security_groups.return_value = (
        nsg_poller
    )


def test_explain_network_path_allowed_when_both_layers_pass(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_effective_route_and_nsg(network_client, next_hop_type="VnetLocal", nsg_access="Allow")

    result = explain_network_path(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_interface_name="nic-1",
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
    )

    assert result.route_verdict == "routable"
    assert result.security_verdict == "allowed"
    assert result.overall_verdict == "allowed"
    assert len(result.findings) == 2


def test_explain_network_path_blocked_when_nsg_denies(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_effective_route_and_nsg(network_client, next_hop_type="VnetLocal", nsg_access="Deny")

    result = explain_network_path(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_interface_name="nic-1",
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
    )

    assert result.overall_verdict == "blocked"


def test_explain_network_path_blocked_when_route_is_blackhole(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_effective_route_and_nsg(network_client, next_hop_type="None", nsg_access="Allow")

    result = explain_network_path(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_interface_name="nic-1",
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
    )

    assert result.route_verdict == "blocked"
    assert result.overall_verdict == "blocked"


def test_explain_network_path_partially_evaluated_when_route_leaves_scope(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_effective_route_and_nsg(
        network_client, next_hop_type="Internet", nsg_access="Allow", route_prefix="0.0.0.0/0"
    )

    result = explain_network_path(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_interface_name="nic-1",
        destination_ip="8.8.8.8",
        destination_port=443,
        protocol="Tcp",
    )

    assert result.route_verdict == "indeterminate"
    assert result.overall_verdict == "partially_evaluated"


def test_explain_network_path_source_nic_id_is_constructed_correctly(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_effective_route_and_nsg(network_client)

    result = explain_network_path(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_interface_name="nic-1",
        destination_ip="10.0.1.5",
        destination_port=443,
        protocol="Tcp",
    )

    assert result.source_nic_id == (
        f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
        "Microsoft.Network/networkInterfaces/nic-1"
    )
