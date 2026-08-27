from __future__ import annotations

import pytest

from aws_cloudops_mcp.config import Settings
from aws_cloudops_mcp.server import build_server

EXPECTED_TOOL_NAMES = {
    "aws_get_caller_identity",
    "aws_list_regions",
    "aws_list_vpcs",
    "aws_list_subnets",
    "aws_list_route_tables",
}


@pytest.mark.asyncio
async def test_build_server_registers_exactly_the_milestone_1_tools(
    settings: Settings,
) -> None:
    server = build_server(settings)
    tools = await server.list_tools()
    assert {tool.name for tool in tools} == EXPECTED_TOOL_NAMES


@pytest.mark.asyncio
async def test_each_tool_declares_a_description(settings: Settings) -> None:
    server = build_server(settings)
    tools = await server.list_tools()
    for tool in tools:
        assert tool.description
