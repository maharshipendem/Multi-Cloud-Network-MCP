"""MCP-level tests for the three diagnostic tools: exercises the real
``MCPServer.call_tool()`` path (not just the diagnostics engine directly),
including the tool-layer input validation this module owns."""

from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.config import Settings
from aws_cloudops_mcp.server import build_server


@pytest.fixture
def settings() -> Settings:
    return Settings(aws_default_region="us-east-1")


@pytest.fixture
def diagnostics_fixture() -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        subnet_a = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.1.0/24")["Subnet"]
        subnet_b = ec2.create_subnet(VpcId=vpc["VpcId"], CidrBlock="10.0.2.0/24")["Subnet"]
        rt = ec2.create_route_table(VpcId=vpc["VpcId"])["RouteTable"]
        ec2.associate_route_table(RouteTableId=rt["RouteTableId"], SubnetId=subnet_a["SubnetId"])
        ec2.associate_route_table(RouteTableId=rt["RouteTableId"], SubnetId=subnet_b["SubnetId"])
        yield {
            "vpc_id": vpc["VpcId"],
            "subnet_a": subnet_a["SubnetId"],
            "subnet_b": subnet_b["SubnetId"],
        }


@pytest.mark.asyncio
async def test_explain_network_path_via_mcp_call_tool(
    settings: Settings, diagnostics_fixture: dict[str, str]
) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_explain_network_path",
            {
                "region": "us-east-1",
                "source_subnet_id": diagnostics_fixture["subnet_a"],
                "destination": "10.0.2.5",
            },
        )
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["data"]["route_verdict"] == "routable"
    assert payload["data"]["findings"][0]["rule_id"] == "ROUTE-001"


@pytest.mark.asyncio
async def test_find_network_risks_via_mcp_call_tool(
    settings: Settings, diagnostics_fixture: dict[str, str]
) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_find_network_risks",
            {"region": "us-east-1", "vpc_ids": [diagnostics_fixture["vpc_id"]]},
        )
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert isinstance(payload["data"], list)


@pytest.mark.asyncio
async def test_find_network_risks_rejects_invalid_min_severity(
    settings: Settings, diagnostics_fixture: dict[str, str]
) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_find_network_risks",
            {"region": "us-east-1", "min_severity": "extremely-bad"},
        )
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["type"] == "TOOL_EXECUTION_ERROR"


@pytest.mark.asyncio
async def test_get_network_health_via_mcp_call_tool(
    settings: Settings, diagnostics_fixture: dict[str, str]
) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_get_network_health",
            {"region": "us-east-1", "vpc_ids": [diagnostics_fixture["vpc_id"]]},
        )
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert "degraded_resources" in payload["data"]


@pytest.mark.asyncio
async def test_explain_network_path_unresolvable_source_is_indeterminate_not_an_error(
    settings: Settings,
) -> None:
    """An unresolvable source is a normal INDETERMINATE finding, not a
    tool-level error -- the envelope's success flag stays true."""
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_explain_network_path",
            {
                "region": "us-east-1",
                "source_subnet_id": "subnet-does-not-exist",
                "destination": "10.0.0.1",
            },
        )
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["data"]["route_verdict"] == "indeterminate"
