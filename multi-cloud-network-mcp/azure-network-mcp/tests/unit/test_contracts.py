"""Tests for azure_network_mcp.tools.contracts: the multicloud-network-mcp
adapter surface (azure_get_contract_capabilities, azure_export_normalized_topology).

Mirrors this project's own convention (test_topology.py: direct
service-layer calls with ``SimpleNamespace``-mocked ARM SDK objects;
test_mcp_smoke.py: real ``MCPServer.call_tool()`` round trips) rather
than importing anything from the sibling ``multicloud-network-mcp``
package -- per that package's ADR 0001, this repo has no runtime (or
test-time) dependency on it.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp import __version__
from azure_network_mcp.config import Settings
from azure_network_mcp.models.common import CollectionWarning
from azure_network_mcp.models.topology import TopologyEdge, TopologyNode, VnetTopology
from azure_network_mcp.server import build_server
from azure_network_mcp.tools.contracts import (
    CAPABILITIES_TOOL_NAME,
    EXPORT_TOOL_NAME,
    _build_capability_manifest,
    _build_urn,
    _map_topology,
)

_URN_RE = re.compile(
    r"^urn:mcnet:v1:azure:(?P<scope>[^:]*):(?P<resource_type>[^:]+):(?P<native_id>.+)$"
)

BASE = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.Network"
)
VNET_ID = f"{BASE}/virtualNetworks/vnet-1"
SUBNET_ID = f"{VNET_ID}/subnets/subnet-a"
NSG_ID = f"{BASE}/networkSecurityGroups/nsg-1"
OUT_OF_SCOPE_NSG_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/rg-other/providers/"
    "Microsoft.Network/networkSecurityGroups/nsg-external"
)


# --- URN grammar -------------------------------------------------------------


def test_build_urn_matches_mcnet_grammar() -> None:
    urn = _build_urn(
        scope={
            "subscription_id": SUBSCRIPTION_ID,
            "location": "eastus",
            "resource_group": RESOURCE_GROUP,
        },
        resource_type="network",
        native_id=VNET_ID,
    )
    match = _URN_RE.match(urn)
    assert match is not None, urn
    assert match.group("resource_type") == "network"
    # native_id keeps '/' literal (safe chars), so an ARM ID reads almost verbatim.
    assert match.group("native_id") == VNET_ID


def test_build_urn_scope_keys_emitted_in_fixed_order() -> None:
    # Deliberately pass keys out of order -- the grammar's own fixed order
    # (subscription_id, location, resource_group here) must still win.
    urn = _build_urn(
        scope={
            "resource_group": RESOURCE_GROUP,
            "subscription_id": SUBSCRIPTION_ID,
            "location": "eastus",
        },
        resource_type="subnet",
        native_id=SUBNET_ID,
    )
    scope_str = _URN_RE.match(urn).group("scope")
    assert (
        scope_str
        == f"subscription_id={SUBSCRIPTION_ID},location=eastus,resource_group={RESOURCE_GROUP}"
    )


def test_build_urn_percent_encodes_delimiter_characters() -> None:
    urn = _build_urn(
        scope={"subscription_id": SUBSCRIPTION_ID, "resource_group": "rg,with:special=chars%"},
        resource_type="network",
        native_id=VNET_ID,
    )
    assert "rg,with:special=chars%" not in urn
    assert "rg%2Cwith%3Aspecial%3Dchars%25" in urn


def test_build_urn_omits_absent_scope_keys() -> None:
    urn = _build_urn(
        scope={"subscription_id": SUBSCRIPTION_ID}, resource_type="network", native_id=VNET_ID
    )
    scope_str = _URN_RE.match(urn).group("scope")
    assert scope_str == f"subscription_id={SUBSCRIPTION_ID}"


# --- azure_get_contract_capabilities ----------------------------------------


def test_build_capability_manifest_shape() -> None:
    manifest = _build_capability_manifest()

    assert manifest["provider"] == "azure"
    assert manifest["adapter_package"] == "azure-network-mcp"
    assert manifest["adapter_version"] == __version__
    assert manifest["contract_version"] == "1.0.0"
    assert manifest["min_supported_contract_version"] == "1.0.0"
    assert manifest["urn_grammar_version"] == 1
    assert manifest["supports_topology"] is True
    assert manifest["supports_diagnostics"] is False
    assert manifest["supports_observability"] is False
    # A real, parseable UTC ISO 8601 timestamp, computed at call time.
    from datetime import datetime

    datetime.fromisoformat(manifest["generated_at"])

    resource_types = {rt["resource_type"] for rt in manifest["supported_resource_types"]}
    for expected in (
        "network",
        "subnet",
        "network-interface",
        "address",
        "route-table",
        "route",
        "firewall-rule",
        "transit-hub",
        "attachment",
        "peering",
        "vpn-gateway",
        "vpn-tunnel",
        "interconnect",
        "interconnect-attachment",
        "dns-zone",
        "dns-resolver",
        "dns-rule",
        "load-balancer",
        "endpoint",
    ):
        assert expected in resource_types

    for entry in manifest["supported_resource_types"]:
        assert entry["export_tool"] == EXPORT_TOOL_NAME
        assert isinstance(entry["exact_mapping"], bool)

    transit_hub = next(
        rt for rt in manifest["supported_resource_types"] if rt["resource_type"] == "transit-hub"
    )
    assert transit_hub["exact_mapping"] is False
    assert "address_prefix" in transit_hub["notes"]


# --- azure_export_normalized_topology mapping --------------------------------


def _sample_topology() -> VnetTopology:
    nodes = [
        TopologyNode(
            node_id=VNET_ID,
            node_type="virtual_network",
            label="vnet-1",
            virtual_network_name="vnet-1",
            resource_group=RESOURCE_GROUP,
            tags={"env": "test"},
        ),
        TopologyNode(
            node_id=SUBNET_ID,
            node_type="subnet",
            label="subnet-a",
            virtual_network_name="vnet-1",
            resource_group=RESOURCE_GROUP,
        ),
    ]
    edges = [
        TopologyEdge(
            source_id=VNET_ID,
            target_id=SUBNET_ID,
            relationship="contains",
            evidence="subnet subnet-a is listed under VNet vnet-1",
        ),
        TopologyEdge(
            source_id=SUBNET_ID,
            target_id=OUT_OF_SCOPE_NSG_ID,
            relationship="protected_by",
            evidence=f"subnet subnet-a NetworkSecurityGroup.id={OUT_OF_SCOPE_NSG_ID}",
        ),
    ]
    return VnetTopology(
        virtual_network_name="vnet-1",
        resource_group=RESOURCE_GROUP,
        subscription_id=SUBSCRIPTION_ID,
        nodes=nodes,
        edges=edges,
        warnings=[
            CollectionWarning(
                resource_type="NetworkSecurityGroup",
                code="OUT_OF_SCOPE_TARGET",
                message="out of scope",
            )
        ],
        api_call_count=7,
    )


def test_map_topology_builds_urn_nodes_with_resource_kind() -> None:
    graph = _map_topology(_sample_topology(), location="eastus")

    assert graph["scope"]["provider"] == "azure"
    assert graph["scope"]["subscription_id"] == SUBSCRIPTION_ID
    assert graph["scope"]["resource_group"] == RESOURCE_GROUP
    assert graph["scope"]["location"] == "eastus"
    assert graph["api_call_count"] == 7

    node_ids = {n["native_id"] for n in graph["nodes"]}
    assert node_ids == {VNET_ID, SUBNET_ID}
    for node in graph["nodes"]:
        assert node["kind"] == "resource"
        assert _URN_RE.match(node["urn"]) is not None
        assert node["urn"].endswith(node["native_id"])


def test_map_topology_edge_evidence_preserves_original_string() -> None:
    graph = _map_topology(_sample_topology(), location="eastus")

    contains_edge = next(e for e in graph["edges"] if e["relationship"] == "contains")
    assert contains_edge["evidence"] == [
        {"source": "contains", "detail": "subnet subnet-a is listed under VNet vnet-1"}
    ]
    assert _URN_RE.match(contains_edge["source_urn"]) is not None
    assert _URN_RE.match(contains_edge["target_urn"]) is not None

    # An edge whose target has no matching node (out-of-scope reference)
    # still gets a well-formed target_urn, inferred from the ARM ID itself.
    protected_by_edge = next(e for e in graph["edges"] if e["relationship"] == "protected_by")
    assert protected_by_edge["target_urn"].endswith(OUT_OF_SCOPE_NSG_ID)


def test_map_topology_completeness_reflects_warnings() -> None:
    graph = _map_topology(_sample_topology(), location="eastus")
    assert graph["completeness"] == "partial"
    assert len(graph["warnings"]) == 1
    assert graph["warnings"][0]["code"] == "OUT_OF_SCOPE_TARGET"

    empty_warnings_topology = _sample_topology().model_copy(update={"warnings": []})
    clean_graph = _map_topology(empty_warnings_topology, location="eastus")
    assert clean_graph["completeness"] == "complete"


def test_map_topology_handles_missing_location() -> None:
    graph = _map_topology(_sample_topology(), location=None)
    assert graph["scope"]["location"] is None
    for node in graph["nodes"]:
        # location is simply omitted from the URN scope segment, never emitted as "location=".
        assert "location=" not in node["urn"]


# --- MCP-level envelope round trip -------------------------------------------


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
def patched_clients(mock_network_client: MagicMock):
    with (
        patch(
            "azure_network_mcp.arm.client_factory.NetworkManagementClient",
            return_value=mock_network_client,
        ),
        patch(
            "azure_network_mcp.arm.client_factory.ResourceManagementClient",
            return_value=MagicMock(),
        ),
        patch("azure_network_mcp.arm.client_factory.SubscriptionClient", return_value=MagicMock()),
    ):
        yield


def _vnet() -> SimpleNamespace:
    return SimpleNamespace(
        id=VNET_ID,
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


@pytest.mark.asyncio
async def test_get_contract_capabilities_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None
) -> None:
    server = build_server(mcp_settings)
    result = await server.call_tool(CAPABILITIES_TOOL_NAME, {})
    payload = json.loads(result.content[0].text)

    assert payload["success"] is True
    assert payload["tool"] == CAPABILITIES_TOOL_NAME
    assert payload["data"]["provider"] == "azure"
    assert payload["data"]["urn_grammar_version"] == 1


@pytest.mark.asyncio
async def test_export_normalized_topology_via_mcp_call_tool(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    mock_network_client.virtual_networks.list.return_value = make_pageable([_vnet()])
    mock_network_client.network_security_groups.list.return_value = make_pageable([])
    mock_network_client.route_tables.list.return_value = make_pageable([])
    mock_network_client.nat_gateways.list.return_value = make_pageable([])
    mock_network_client.network_interfaces.list.return_value = make_pageable([])
    mock_network_client.public_ip_addresses.list.return_value = make_pageable([])
    mock_network_client.subnets.list.return_value = make_pageable([])
    mock_network_client.virtual_network_peerings.list.return_value = make_pageable([])

    server = build_server(mcp_settings)
    result = await server.call_tool(
        EXPORT_TOOL_NAME,
        {"resource_group": RESOURCE_GROUP, "virtual_network_name": "vnet-1"},
    )
    payload = json.loads(result.content[0].text)

    assert payload["success"] is True
    assert payload["tool"] == EXPORT_TOOL_NAME
    assert payload["subscription_id"] == SUBSCRIPTION_ID
    assert payload["data"]["scope"]["subscription_id"] == SUBSCRIPTION_ID
    assert payload["data"]["scope"]["resource_group"] == RESOURCE_GROUP
    assert payload["data"]["scope"]["location"] == "eastus"
    node = next(n for n in payload["data"]["nodes"] if n["native_id"] == VNET_ID)
    assert node["urn"].startswith("urn:mcnet:v1:azure:")
    assert node["kind"] == "resource"


@pytest.mark.asyncio
async def test_export_normalized_topology_error_envelope_matches_existing_shape(
    mcp_settings: Settings, patched_clients: None, mock_network_client: MagicMock
) -> None:
    mock_network_client.virtual_networks.list.return_value = make_pageable([])

    server = build_server(mcp_settings)
    result = await server.call_tool(
        EXPORT_TOOL_NAME,
        {"resource_group": RESOURCE_GROUP, "virtual_network_name": "does-not-exist"},
    )
    payload = json.loads(result.content[0].text)

    assert payload["success"] is False
    assert payload["error"]["type"] == "RESOURCE_NOT_FOUND"
    assert payload["data"] is None
