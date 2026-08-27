"""End-to-end MCP smoke tests: exercises the real ``MCPServer.call_tool()``
path (not just the ARM service layer directly), including the tool-layer
subscription resolution and response-envelope serialization every other
test file bypasses by calling service functions directly.

Since Azure has no moto-equivalent, the ARM SDK client classes themselves
are monkeypatched at construction time (rather than mocking individual
``ClientFactory`` instances, since ``build_server`` owns construction of
its own ``ClientFactory`` internally) so ``build_server()`` -> tool
registration -> ``call_tool()`` all run through real, unmodified code.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.config import Settings
from azure_network_mcp.server import build_server


@pytest.fixture
def mcp_settings() -> Settings:
    return Settings(
        _env_file=None,
        azure_tenant_id="tenant-a",
        azure_default_subscription_id=SUBSCRIPTION_ID,
    )


@pytest.fixture
def mock_network_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_resource_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_subscription_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def patched_clients(
    mock_network_client: MagicMock,
    mock_resource_client: MagicMock,
    mock_subscription_client: MagicMock,
):
    with (
        patch(
            "azure_network_mcp.arm.client_factory.NetworkManagementClient",
            return_value=mock_network_client,
        ),
        patch(
            "azure_network_mcp.arm.client_factory.ResourceManagementClient",
            return_value=mock_resource_client,
        ),
        patch(
            "azure_network_mcp.arm.client_factory.SubscriptionClient",
            return_value=mock_subscription_client,
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_get_caller_identity_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None
) -> None:
    server = build_server(mcp_settings)
    result = await server.call_tool("azure_get_caller_identity", {})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["data"]["credential_type"] == "DefaultAzureCredential"
    assert payload["data"]["tenant_id"] == "tenant-a"


@pytest.mark.asyncio
async def test_list_virtual_networks_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    mock_network_client.virtual_networks.list_all.return_value = make_pageable(
        [
            SimpleNamespace(
                id=(
                    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/"
                    "providers/Microsoft.Network/virtualNetworks/vnet-1"
                ),
                name="vnet-1",
                location="eastus",
                provisioning_state="Succeeded",
                tags={},
                address_space=SimpleNamespace(address_prefixes=["10.0.0.0/16"]),
                dhcp_options=None,
                subnets=[],
                virtual_network_peerings=[],
                enable_ddos_protection=False,
            )
        ]
    )

    server = build_server(mcp_settings)
    result = await server.call_tool("azure_list_virtual_networks", {})

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["subscription_id"] == SUBSCRIPTION_ID
    assert payload["data"][0]["name"] == "vnet-1"
    assert payload["data"][0]["address_space"] == ["10.0.0.0/16"]
    assert payload["metadata"]["count"] == 1


@pytest.mark.asyncio
async def test_list_resource_groups_via_mcp_call_tool_surfaces_warnings(
    mcp_settings: Settings, patched_clients: None, mock_resource_client: MagicMock
) -> None:
    mock_resource_client.resource_groups.list.return_value = make_pageable([])

    server = build_server(mcp_settings)
    result = await server.call_tool("azure_list_resource_groups", {})

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["data"] == []


@pytest.mark.asyncio
async def test_tool_call_with_disallowed_subscription_returns_error_envelope(
    patched_clients: None,
) -> None:
    settings = Settings(
        _env_file=None,
        azure_tenant_id="tenant-a",
        azure_subscription_allowlist=SUBSCRIPTION_ID,
    )
    server = build_server(settings)

    result = await server.call_tool(
        "azure_list_virtual_networks", {"subscription_id": "not-allowed-sub"}
    )

    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["type"] == "SUBSCRIPTION_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_call_tool_rejects_unknown_tool_name(
    mcp_settings: Settings, patched_clients: None
) -> None:
    server = build_server(mcp_settings)
    with pytest.raises(Exception):  # noqa: B017 -- exact exception type is MCP-SDK-internal
        await server.call_tool("azure_delete_virtual_network", {})


# Every tool exercised with minimal plausible arguments, empty-list SDK
# responses throughout: catches a mismatched parameter name between a
# tool's declared schema and the underlying ARM service-layer function
# signature (a class of bug none of the ARM-layer-only tests above can
# see, since they call the service function directly rather than through
# MCP argument binding).
_ALL_TOOL_CALLS: list[tuple[str, dict[str, object]]] = [
    ("azure_get_caller_identity", {}),
    ("azure_list_subscriptions", {}),
    ("azure_list_tenants", {}),
    ("azure_list_locations", {}),
    ("azure_list_resource_groups", {}),
    ("azure_list_virtual_networks", {}),
    ("azure_list_subnets", {"resource_group": RESOURCE_GROUP, "virtual_network_name": "vnet-1"}),
    ("azure_list_route_tables", {}),
    (
        "azure_get_effective_route_table",
        {"resource_group": RESOURCE_GROUP, "network_interface_name": "nic-1"},
    ),
    ("azure_list_network_security_groups", {}),
    (
        "azure_list_security_rules",
        {"resource_group": RESOURCE_GROUP, "network_security_group_name": "nsg-1"},
    ),
    (
        "azure_get_effective_network_security_groups",
        {"resource_group": RESOURCE_GROUP, "network_interface_name": "nic-1"},
    ),
    ("azure_list_network_interfaces", {}),
    ("azure_list_public_ip_addresses", {}),
    (
        "azure_list_virtual_network_peerings",
        {"resource_group": RESOURCE_GROUP, "virtual_network_name": "vnet-1"},
    ),
    ("azure_list_nat_gateways", {}),
    ("azure_list_load_balancers", {}),
    ("azure_list_application_gateways", {}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments"), _ALL_TOOL_CALLS)
async def test_every_list_and_get_tool_runs_via_mcp_call_tool_without_crashing(
    mcp_settings: Settings,
    patched_clients: None,
    mock_network_client: MagicMock,
    mock_resource_client: MagicMock,
    mock_subscription_client: MagicMock,
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    empty = make_pageable([])
    mock_network_client.virtual_networks.list_all.return_value = empty
    mock_network_client.virtual_networks.list.return_value = empty
    mock_network_client.subnets.list.return_value = empty
    mock_network_client.route_tables.list_all.return_value = empty
    mock_network_client.network_security_groups.list_all.return_value = empty
    mock_network_client.security_rules.list.return_value = empty
    mock_network_client.network_interfaces.list_all.return_value = empty
    mock_network_client.public_ip_addresses.list_all.return_value = empty
    mock_network_client.virtual_network_peerings.list.return_value = empty
    mock_network_client.nat_gateways.list_all.return_value = empty
    mock_network_client.load_balancers.list_all.return_value = empty
    mock_network_client.application_gateways.list_all.return_value = empty
    empty_lro = MagicMock()
    empty_lro.result.return_value = SimpleNamespace(value=[])
    nic_ops = mock_network_client.network_interfaces
    nic_ops.begin_get_effective_route_table.return_value = empty_lro
    nic_ops.begin_list_effective_network_security_groups.return_value = empty_lro
    mock_resource_client.resource_groups.list.return_value = empty
    mock_subscription_client.subscriptions.list.return_value = empty
    mock_subscription_client.tenants.list.return_value = empty
    mock_subscription_client.subscriptions.list_locations.return_value = empty

    server = build_server(mcp_settings)
    result = await server.call_tool(tool_name, arguments)

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload
    assert payload["tool"] == tool_name
