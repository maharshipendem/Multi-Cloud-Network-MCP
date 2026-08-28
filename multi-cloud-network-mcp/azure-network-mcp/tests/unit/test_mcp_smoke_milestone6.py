"""End-to-end MCP smoke tests for every Milestone 6 tool: exercises the
real ``MCPServer.call_tool()`` path for each of the 48 new tools (44
inventory + 4 diagnostics), by monkeypatching the six ARM SDK client
classes at construction time -- the same pattern
``test_mcp_smoke.py`` established for Milestone 5.
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
def mock_private_dns_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_dns_resolver_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_monitor_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def patched_clients(
    mock_network_client: MagicMock,
    mock_resource_client: MagicMock,
    mock_subscription_client: MagicMock,
    mock_private_dns_client: MagicMock,
    mock_dns_resolver_client: MagicMock,
    mock_monitor_client: MagicMock,
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
        patch(
            "azure_network_mcp.arm.client_factory.PrivateDnsManagementClient",
            return_value=mock_private_dns_client,
        ),
        patch(
            "azure_network_mcp.arm.client_factory.DnsResolverManagementClient",
            return_value=mock_dns_resolver_client,
        ),
        patch(
            "azure_network_mcp.arm.client_factory.MonitorManagementClient",
            return_value=mock_monitor_client,
        ),
    ):
        yield


# Every M6 inventory tool, with minimal plausible arguments. The
# ExpressRoute-gateway-family and Route-Server-family "list_by_resource_group"
# operations (which return a non-paginated wrapper, not ItemPaged) and the
# two-poller effective-* computations are stubbed separately below.
_LIST_TOOL_CALLS: list[tuple[str, dict[str, object]]] = [
    ("azure_list_virtual_wans", {}),
    ("azure_list_virtual_hubs", {}),
    (
        "azure_list_hub_route_tables",
        {"resource_group": RESOURCE_GROUP, "virtual_hub_name": "hub-1"},
    ),
    (
        "azure_list_hub_virtual_network_connections",
        {"resource_group": RESOURCE_GROUP, "virtual_hub_name": "hub-1"},
    ),
    (
        "azure_list_virtual_hub_bgp_connections",
        {"resource_group": RESOURCE_GROUP, "virtual_hub_name": "hub-1"},
    ),
    ("azure_list_route_maps", {"resource_group": RESOURCE_GROUP, "virtual_hub_name": "hub-1"}),
    ("azure_list_route_servers", {}),
    (
        "azure_list_route_server_peers",
        {"resource_group": RESOURCE_GROUP, "route_server_name": "rs-1"},
    ),
    ("azure_list_vpn_gateways", {}),
    ("azure_list_vpn_sites", {}),
    ("azure_list_vpn_connections", {"resource_group": RESOURCE_GROUP, "vpn_gateway_name": "gw-1"}),
    ("azure_list_virtual_network_gateways", {"resource_group": RESOURCE_GROUP}),
    ("azure_list_local_network_gateways", {"resource_group": RESOURCE_GROUP}),
    ("azure_list_virtual_network_gateway_connections", {"resource_group": RESOURCE_GROUP}),
    ("azure_list_express_route_circuits", {}),
    (
        "azure_list_express_route_circuit_peerings",
        {"resource_group": RESOURCE_GROUP, "circuit_name": "circuit-1"},
    ),
    (
        "azure_list_express_route_circuit_connections",
        {
            "resource_group": RESOURCE_GROUP,
            "circuit_name": "circuit-1",
            "peering_name": "AzurePrivatePeering",
        },
    ),
    ("azure_list_express_route_gateways", {}),
    (
        "azure_list_express_route_connections",
        {"resource_group": RESOURCE_GROUP, "express_route_gateway_name": "ergw-1"},
    ),
    ("azure_list_express_route_ports", {}),
    ("azure_list_express_route_links", {"resource_group": RESOURCE_GROUP, "port_name": "port-1"}),
    ("azure_list_private_endpoints", {}),
    ("azure_list_private_link_services", {}),
    ("azure_list_service_endpoint_policies", {}),
    ("azure_list_private_dns_zones", {}),
    (
        "azure_list_private_dns_virtual_network_links",
        {"resource_group": RESOURCE_GROUP, "zone_name": "contoso.internal"},
    ),
    (
        "azure_list_private_dns_record_sets",
        {"resource_group": RESOURCE_GROUP, "zone_name": "contoso.internal"},
    ),
    ("azure_list_dns_resolvers", {}),
    (
        "azure_list_dns_resolver_inbound_endpoints",
        {"resource_group": RESOURCE_GROUP, "dns_resolver_name": "resolver-1"},
    ),
    (
        "azure_list_dns_resolver_outbound_endpoints",
        {"resource_group": RESOURCE_GROUP, "dns_resolver_name": "resolver-1"},
    ),
    ("azure_list_dns_forwarding_rulesets", {}),
    (
        "azure_list_dns_forwarding_rules",
        {"resource_group": RESOURCE_GROUP, "ruleset_name": "ruleset-1"},
    ),
    (
        "azure_list_dns_forwarding_ruleset_virtual_network_links",
        {"resource_group": RESOURCE_GROUP, "ruleset_name": "ruleset-1"},
    ),
    ("azure_list_azure_firewalls", {}),
    ("azure_list_firewall_policies", {}),
    (
        "azure_list_firewall_policy_rule_collection_groups",
        {"resource_group": RESOURCE_GROUP, "firewall_policy_name": "policy-1"},
    ),
    ("azure_list_network_watchers", {}),
    (
        "azure_list_connection_monitors",
        {"resource_group": RESOURCE_GROUP, "network_watcher_name": "watcher-1"},
    ),
    (
        "azure_list_flow_logs",
        {"resource_group": RESOURCE_GROUP, "network_watcher_name": "watcher-1"},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments"), _LIST_TOOL_CALLS)
async def test_every_milestone6_list_tool_runs_via_mcp_call_tool(
    mcp_settings: Settings,
    patched_clients: None,
    mock_network_client: MagicMock,
    mock_private_dns_client: MagicMock,
    mock_dns_resolver_client: MagicMock,
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    # Stub every operation group this call could possibly reach with an
    # empty paged result -- resource-group-scoped calls use "list" or
    # "list_by_resource_group" depending on the operation group (see
    # test_diagnostics_snapshot.py's _PAGED_METHODS mapping for the same
    # per-group distinction).
    for attr in (
        "virtual_wans",
        "virtual_hubs",
        "hub_route_tables",
        "hub_virtual_network_connections",
        "virtual_hub_bgp_connections",
        "route_maps",
        "vpn_sites",
        "vpn_connections",
        "virtual_network_gateways",
        "local_network_gateways",
        "virtual_network_gateway_connections",
        "express_route_circuits",
        "express_route_circuit_peerings",
        "express_route_circuit_connections",
        "express_route_ports",
        "express_route_links",
        "private_endpoints",
        "private_link_services",
        "service_endpoint_policies",
        "azure_firewalls",
        "firewall_policies",
        "firewall_policy_rule_collection_groups",
        "network_watchers",
        "connection_monitors",
        "flow_logs",
    ):
        for method in ("list", "list_by_resource_group", "list_all", "list_by_subscription"):
            getattr(getattr(mock_network_client, attr), method).return_value = make_pageable([])
    mock_network_client.vpn_gateways.list.return_value = make_pageable([])
    mock_network_client.vpn_gateways.list_by_resource_group.return_value = make_pageable([])
    mock_network_client.express_route_gateways.list_by_resource_group.return_value = (
        SimpleNamespace(value=[])
    )
    mock_network_client.express_route_gateways.list_by_subscription.return_value = SimpleNamespace(
        value=[]
    )
    mock_network_client.express_route_connections.list.return_value = SimpleNamespace(value=[])

    mock_private_dns_client.private_zones.list.return_value = make_pageable([])
    mock_private_dns_client.private_zones.list_by_resource_group.return_value = make_pageable([])
    mock_private_dns_client.virtual_network_links.list.return_value = make_pageable([])
    mock_private_dns_client.record_sets.list.return_value = make_pageable([])

    mock_dns_resolver_client.dns_resolvers.list.return_value = make_pageable([])
    mock_dns_resolver_client.dns_resolvers.list_by_resource_group.return_value = make_pageable([])
    mock_dns_resolver_client.inbound_endpoints.list.return_value = make_pageable([])
    mock_dns_resolver_client.outbound_endpoints.list.return_value = make_pageable([])
    mock_dns_resolver_client.dns_forwarding_rulesets.list.return_value = make_pageable([])
    mock_dns_resolver_client.dns_forwarding_rulesets.list_by_resource_group.return_value = (
        make_pageable([])
    )
    mock_dns_resolver_client.forwarding_rules.list.return_value = make_pageable([])
    mock_dns_resolver_client.virtual_network_links.list.return_value = make_pageable([])

    server = build_server(mcp_settings)
    result = await server.call_tool(tool_name, arguments)

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload
    assert payload["tool"] == tool_name


@pytest.mark.asyncio
async def test_get_hub_bgp_connection_routes_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    poller = MagicMock()
    poller.result.return_value = {}
    mock_network_client.virtual_hub_bgp_connections.begin_list_advertised_routes.return_value = (
        poller
    )

    server = build_server(mcp_settings)
    result = await server.call_tool(
        "azure_get_hub_bgp_connection_routes",
        {
            "resource_group": RESOURCE_GROUP,
            "virtual_hub_name": "hub-1",
            "connection_name": "conn-1",
            "direction": "advertised",
        },
    )

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


@pytest.mark.asyncio
async def test_get_route_server_peer_routes_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    poller = MagicMock()
    poller.result.return_value = {}
    mock_network_client.virtual_hub_bgp_connections.begin_list_learned_routes.return_value = poller

    server = build_server(mcp_settings)
    result = await server.call_tool(
        "azure_get_route_server_peer_routes",
        {
            "resource_group": RESOURCE_GROUP,
            "route_server_name": "rs-1",
            "peer_connection_name": "peer-1",
            "direction": "learned",
        },
    )

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


@pytest.mark.asyncio
async def test_get_bgp_peer_status_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    poller = MagicMock()
    poller.result.return_value = SimpleNamespace(value=[])
    mock_network_client.virtual_network_gateways.begin_get_bgp_peer_status.return_value = poller

    server = build_server(mcp_settings)
    result = await server.call_tool(
        "azure_get_bgp_peer_status",
        {"resource_group": RESOURCE_GROUP, "virtual_network_gateway_name": "vng-1"},
    )

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


@pytest.mark.asyncio
async def test_get_network_topology_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    mock_network_client.network_watchers.get_topology.return_value = SimpleNamespace(
        created_date_time=None, last_modified=None, resources=[]
    )

    server = build_server(mcp_settings)
    result = await server.call_tool(
        "azure_get_network_topology",
        {
            "resource_group": RESOURCE_GROUP,
            "network_watcher_name": "watcher-1",
            "target_resource_group": RESOURCE_GROUP,
        },
    )

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


@pytest.mark.asyncio
async def test_get_network_metrics_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_monitor_client: MagicMock
) -> None:
    mock_monitor_client.metrics.list.return_value = SimpleNamespace(value=[])

    server = build_server(mcp_settings)
    result = await server.call_tool(
        "azure_get_network_metrics",
        {
            "resource_id": (
                f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
                "Microsoft.Network/loadBalancers/lb-1"
            )
        },
    )

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


# --- Diagnostics tools -----------------------------------------------------------


def _stub_empty_hybrid_snapshot(mock_network_client: MagicMock) -> None:
    for attr in (
        "virtual_networks",
        "network_security_groups",
        "route_tables",
        "network_interfaces",
        "public_ip_addresses",
        "private_endpoints",
        "vpn_gateways",
        "virtual_network_gateways",
        "virtual_network_gateway_connections",
        "express_route_circuits",
    ):
        getattr(mock_network_client, attr).list.return_value = make_pageable([])
    mock_network_client.virtual_hubs.list_by_resource_group.return_value = make_pageable([])
    mock_network_client.express_route_gateways.list_by_resource_group.return_value = (
        SimpleNamespace(value=[])
    )


@pytest.mark.asyncio
async def test_get_hybrid_topology_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    _stub_empty_hybrid_snapshot(mock_network_client)

    server = build_server(mcp_settings)
    result = await server.call_tool("azure_get_hybrid_topology", {"resource_group": RESOURCE_GROUP})

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


@pytest.mark.asyncio
async def test_find_network_risks_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    _stub_empty_hybrid_snapshot(mock_network_client)

    server = build_server(mcp_settings)
    result = await server.call_tool("azure_find_network_risks", {"resource_group": RESOURCE_GROUP})

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload
    assert payload["data"] == []


@pytest.mark.asyncio
async def test_get_network_health_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    _stub_empty_hybrid_snapshot(mock_network_client)

    server = build_server(mcp_settings)
    result = await server.call_tool("azure_get_network_health", {"resource_group": RESOURCE_GROUP})

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


@pytest.mark.asyncio
async def test_explain_network_path_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    route_poller = MagicMock()
    route_poller.result.return_value = SimpleNamespace(value=[])
    mock_network_client.network_interfaces.begin_get_effective_route_table.return_value = (
        route_poller
    )
    nsg_poller = MagicMock()
    nsg_poller.result.return_value = SimpleNamespace(value=[])
    nic_ops = mock_network_client.network_interfaces
    nic_ops.begin_list_effective_network_security_groups.return_value = nsg_poller

    server = build_server(mcp_settings)
    result = await server.call_tool(
        "azure_explain_network_path",
        {
            "resource_group": RESOURCE_GROUP,
            "network_interface_name": "nic-1",
            "destination_ip": "10.0.1.5",
            "destination_port": 443,
        },
    )

    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload
    assert payload["data"]["route_verdict"] == "indeterminate"
