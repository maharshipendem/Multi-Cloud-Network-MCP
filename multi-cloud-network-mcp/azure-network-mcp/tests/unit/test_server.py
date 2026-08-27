from __future__ import annotations

import pytest

from azure_network_mcp.config import Settings
from azure_network_mcp.server import build_server

EXPECTED_TOOL_NAMES = {
    "azure_get_caller_identity",
    "azure_list_subscriptions",
    "azure_list_tenants",
    "azure_list_locations",
    "azure_list_resource_groups",
    "azure_list_virtual_networks",
    "azure_list_subnets",
    "azure_list_route_tables",
    "azure_get_effective_route_table",
    "azure_list_network_security_groups",
    "azure_list_security_rules",
    "azure_get_effective_network_security_groups",
    "azure_list_network_interfaces",
    "azure_list_public_ip_addresses",
    "azure_list_virtual_network_peerings",
    "azure_list_nat_gateways",
    "azure_list_load_balancers",
    "azure_list_application_gateways",
    "azure_get_vnet_topology",
}


@pytest.mark.asyncio
async def test_build_server_registers_every_expected_tool(settings: Settings) -> None:
    server = build_server(settings)
    tools = await server.list_tools()
    assert {tool.name for tool in tools} == EXPECTED_TOOL_NAMES


@pytest.mark.asyncio
async def test_each_tool_declares_a_description(settings: Settings) -> None:
    server = build_server(settings)
    tools = await server.list_tools()
    for tool in tools:
        assert tool.description


@pytest.mark.asyncio
async def test_each_tool_declares_read_only_capability_metadata(settings: Settings) -> None:
    """Every tool's ``meta`` must let a federation layer confirm it is
    read-only and discover its resource types without importing this
    codebase."""
    server = build_server(settings)
    tools = await server.list_tools()
    for tool in tools:
        assert tool.meta is not None, f"{tool.name} has no capability metadata"
        assert tool.meta["cloud"] == "azure"
        assert tool.meta["read_only"] is True
        assert tool.meta["resource_types"]


@pytest.mark.asyncio
async def test_no_tool_name_implies_mutation(settings: Settings) -> None:
    server = build_server(settings)
    tools = await server.list_tools()
    for tool in tools:
        assert tool.name.startswith(("azure_get_", "azure_list_")), tool.name
