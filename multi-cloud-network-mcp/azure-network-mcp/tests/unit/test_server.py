from __future__ import annotations

import pytest

from azure_network_mcp.config import Settings
from azure_network_mcp.server import build_server

MILESTONE_5_TOOL_NAMES = {
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

MILESTONE_6_TOOL_NAMES = {
    # Virtual WAN / Virtual Hub
    "azure_list_virtual_wans",
    "azure_list_virtual_hubs",
    "azure_list_hub_route_tables",
    "azure_list_hub_virtual_network_connections",
    "azure_list_virtual_hub_bgp_connections",
    "azure_get_hub_bgp_connection_routes",
    "azure_list_route_maps",
    # Route Server
    "azure_list_route_servers",
    "azure_list_route_server_peers",
    "azure_get_route_server_peer_routes",
    # VPN (vWAN-scoped and classic)
    "azure_list_vpn_gateways",
    "azure_list_vpn_sites",
    "azure_list_vpn_connections",
    "azure_list_virtual_network_gateways",
    "azure_list_local_network_gateways",
    "azure_list_virtual_network_gateway_connections",
    "azure_get_bgp_peer_status",
    # ExpressRoute
    "azure_list_express_route_circuits",
    "azure_list_express_route_circuit_peerings",
    "azure_list_express_route_circuit_connections",
    "azure_list_express_route_gateways",
    "azure_list_express_route_connections",
    "azure_list_express_route_ports",
    "azure_list_express_route_links",
    # Private Link
    "azure_list_private_endpoints",
    "azure_list_private_link_services",
    "azure_list_service_endpoint_policies",
    # Private DNS / DNS Resolver
    "azure_list_private_dns_zones",
    "azure_list_private_dns_virtual_network_links",
    "azure_list_private_dns_record_sets",
    "azure_list_dns_resolvers",
    "azure_list_dns_resolver_inbound_endpoints",
    "azure_list_dns_resolver_outbound_endpoints",
    "azure_list_dns_forwarding_rulesets",
    "azure_list_dns_forwarding_rules",
    "azure_list_dns_forwarding_ruleset_virtual_network_links",
    # Azure Firewall
    "azure_list_azure_firewalls",
    "azure_list_firewall_policies",
    "azure_list_firewall_policy_rule_collection_groups",
    # Network Watcher
    "azure_list_network_watchers",
    "azure_get_network_topology",
    "azure_list_connection_monitors",
    "azure_list_flow_logs",
    # Azure Monitor
    "azure_get_network_metrics",
    # Diagnostics
    "azure_get_hybrid_topology",
    "azure_explain_network_path",
    "azure_find_network_risks",
    "azure_get_network_health",
}

MILESTONE_9_TOOL_NAMES = {
    # multicloud-network-mcp contract adapter surface (ADR 0001: no
    # runtime coupling -- see azure_network_mcp/tools/contracts.py)
    "azure_get_contract_capabilities",
    "azure_export_normalized_topology",
}

EXPECTED_TOOL_NAMES = MILESTONE_5_TOOL_NAMES | MILESTONE_6_TOOL_NAMES | MILESTONE_9_TOOL_NAMES


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
        assert tool.name.startswith(
            ("azure_get_", "azure_list_", "azure_explain_", "azure_find_", "azure_export_")
        ), tool.name
