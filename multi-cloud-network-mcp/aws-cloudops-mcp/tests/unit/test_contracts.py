"""MCP-level tests for the two multicloud-network-mcp contract-adapter
tools: ``aws_get_contract_capabilities`` and
``aws_export_normalized_topology``. Exercises the real
``MCPServer.call_tool()`` path (not just the module's internal
helpers), matching ``test_diagnostics_tools.py``'s convention."""

from __future__ import annotations

import json
import re

import boto3
import pytest
from moto import mock_aws

from aws_cloudops_mcp.config import Settings
from aws_cloudops_mcp.server import build_server

_URN_RE = re.compile(r"^urn:mcnet:v\d+:aws:[^:]*:[^:]+:.+$")


@pytest.fixture
def settings() -> Settings:
    return Settings(aws_default_region="us-east-1")


@pytest.fixture
def topology_fixture() -> dict[str, str]:
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]
        vpc_id = vpc["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")["Subnet"]

        rt = ec2.create_route_table(VpcId=vpc_id)["RouteTable"]
        ec2.associate_route_table(RouteTableId=rt["RouteTableId"], SubnetId=subnet["SubnetId"])

        igw = ec2.create_internet_gateway()["InternetGateway"]
        ec2.attach_internet_gateway(InternetGatewayId=igw["InternetGatewayId"], VpcId=vpc_id)
        ec2.create_route(
            RouteTableId=rt["RouteTableId"],
            DestinationCidrBlock="0.0.0.0/0",
            GatewayId=igw["InternetGatewayId"],
        )

        yield {
            "vpc_id": vpc_id,
            "subnet_id": subnet["SubnetId"],
            "route_table_id": rt["RouteTableId"],
            "igw_id": igw["InternetGatewayId"],
        }


@pytest.mark.asyncio
async def test_get_contract_capabilities_via_mcp_call_tool(settings: Settings) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool("aws_get_contract_capabilities", {})
    payload = json.loads(result.content[0].text)

    assert payload["success"] is True
    assert payload["tool"] == "aws_get_contract_capabilities"
    assert payload["region"] is None

    manifest = payload["data"]
    assert manifest["provider"] == "aws"
    assert manifest["adapter_package"] == "aws-cloudops-mcp"
    assert manifest["contract_version"] == "1.0.0"
    assert manifest["urn_grammar_version"] == 1
    assert manifest["supports_topology"] is True
    assert manifest["supported_resource_types"], "manifest must list at least one resource type"

    for entry in manifest["supported_resource_types"]:
        assert entry["export_tool"] == "aws_export_normalized_topology"
        assert isinstance(entry["exact_mapping"], bool)


@pytest.mark.asyncio
async def test_get_contract_capabilities_envelope_shape(settings: Settings) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool("aws_get_contract_capabilities", {})
    payload = json.loads(result.content[0].text)

    assert set(payload) == {"success", "tool", "account_id", "region", "data", "metadata", "error"}
    assert payload["error"] is None
    assert "request_id" in payload["metadata"]


@pytest.mark.asyncio
async def test_export_normalized_topology_via_mcp_call_tool(
    settings: Settings, topology_fixture: dict[str, str]
) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_export_normalized_topology",
            {"region": "us-east-1", "vpc_id": topology_fixture["vpc_id"]},
        )
    payload = json.loads(result.content[0].text)

    assert payload["success"] is True
    assert payload["tool"] == "aws_export_normalized_topology"
    assert payload["region"] == "us-east-1"

    graph = payload["data"]
    assert graph["scope"]["provider"] == "aws"
    assert graph["scope"]["region"] == "us-east-1"
    assert graph["nodes"], "graph must include at least one node"

    node_by_native_id = {node["native_id"]: node for node in graph["nodes"]}
    assert topology_fixture["vpc_id"] in node_by_native_id
    assert topology_fixture["subnet_id"] in node_by_native_id
    assert node_by_native_id[topology_fixture["vpc_id"]]["resource_type"] == "network"
    assert node_by_native_id[topology_fixture["subnet_id"]]["resource_type"] == "subnet"


@pytest.mark.asyncio
async def test_export_normalized_topology_urns_are_well_formed(
    settings: Settings, topology_fixture: dict[str, str]
) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_export_normalized_topology",
            {"region": "us-east-1", "vpc_id": topology_fixture["vpc_id"]},
        )
    payload = json.loads(result.content[0].text)
    graph = payload["data"]

    assert graph["nodes"], "graph must include at least one node"
    for node in graph["nodes"]:
        urn = node["urn"]
        assert urn.startswith("urn:mcnet:v1:aws:"), urn
        assert _URN_RE.match(urn), urn

    node_urns = {node["urn"] for node in graph["nodes"]}
    for edge in graph["edges"]:
        # Every emitted edge must resolve to two real nodes (unresolved
        # out-of-scope references are dropped, not fabricated -- see
        # contracts.py's `_map_topology_to_graph` docstring).
        assert edge["source_urn"] in node_urns
        assert edge["target_urn"] in node_urns
        assert edge["evidence"], "every edge must carry at least one evidence entry"


@pytest.mark.asyncio
async def test_export_normalized_topology_envelope_shape(
    settings: Settings, topology_fixture: dict[str, str]
) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_export_normalized_topology",
            {"region": "us-east-1", "vpc_id": topology_fixture["vpc_id"]},
        )
    payload = json.loads(result.content[0].text)

    assert set(payload) == {"success", "tool", "account_id", "region", "data", "metadata", "error"}
    assert payload["error"] is None
    assert "request_id" in payload["metadata"]


@pytest.mark.asyncio
async def test_export_normalized_topology_unknown_vpc_is_a_tool_error(settings: Settings) -> None:
    with mock_aws():
        server = build_server(settings)
        result = await server.call_tool(
            "aws_export_normalized_topology",
            {"region": "us-east-1", "vpc_id": "vpc-doesnotexist"},
        )
    payload = json.loads(result.content[0].text)

    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"] is not None
