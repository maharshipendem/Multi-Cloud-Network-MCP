from __future__ import annotations

import pytest

from aws_cloudops_mcp.config import Settings
from aws_cloudops_mcp.server import build_server

MILESTONE_1_TOOL_NAMES = {
    "aws_get_caller_identity",
    "aws_list_regions",
    "aws_list_vpcs",
    "aws_list_subnets",
    "aws_list_route_tables",
}

MILESTONE_2_TOOL_NAMES = {
    "aws_list_internet_gateways",
    "aws_list_egress_only_internet_gateways",
    "aws_list_nat_gateways",
    "aws_list_security_groups",
    "aws_list_network_acls",
    "aws_list_network_interfaces",
    "aws_list_vpc_peering_connections",
    "aws_list_managed_prefix_lists",
    "aws_list_vpc_endpoints",
    "aws_list_vpc_endpoint_services",
    "aws_list_load_balancers",
    "aws_get_vpc_topology",
}

EXPECTED_TOOL_NAMES = MILESTONE_1_TOOL_NAMES | MILESTONE_2_TOOL_NAMES


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
        assert tool.meta["cloud"] == "aws"
        assert tool.meta["read_only"] is True
        assert tool.meta["resource_types"]


@pytest.mark.asyncio
async def test_no_tool_name_implies_mutation(settings: Settings) -> None:
    """Every tool *name* must itself be recognizable as read-only.

    (Description text is not checked here: read-only tools legitimately
    describe attachment/association *state* -- e.g. "gateways attached to
    that VPC" -- using words that would be false positives for a
    substring check. Actual enforcement lives in
    security.guardrails.assert_read_only_operation, covered by
    test_guardrails.py.)
    """
    server = build_server(settings)
    tools = await server.list_tools()
    for tool in tools:
        assert tool.name.startswith(("aws_get_", "aws_list_")), tool.name
