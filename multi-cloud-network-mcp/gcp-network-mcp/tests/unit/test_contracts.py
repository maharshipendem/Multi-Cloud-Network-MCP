"""Tests for the Milestone 9 multicloud-network-mcp adapter tools:
``gcp_get_contract_capabilities`` and ``gcp_export_normalized_topology``.

Mirrors ``test_tools_registration.py``'s pattern (mocked GCP clients,
calling the real registered MCP tool) plus direct unit coverage of the
node/edge/URN mapping logic against real ``VpcTopology`` output, the same
way ``test_topology.py`` exercises ``get_vpc_topology`` itself.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager, make_pager

from gcp_network_mcp.config import Settings
from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.topology import get_vpc_topology
from gcp_network_mcp.server import build_server
from gcp_network_mcp.tools.contracts import _capability_manifest, _to_topology_graph

NETWORK_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
)
SUBNET_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "subnetworks/subnet-1"
)
OTHER_PROJECT_NETWORK = (
    "https://www.googleapis.com/compute/v1/projects/other-proj/global/networks/vpc-x"
)


def _empty_aggregated(items_field: str) -> object:
    return make_aggregated_pager({}, items_field=items_field)


def _stub_clean_topology(client_factory) -> None:
    client_factory.networks().list.return_value = make_pager([])
    client_factory.subnetworks().aggregated_list.return_value = _empty_aggregated("subnetworks")
    client_factory.instances().aggregated_list.return_value = _empty_aggregated("instances")
    client_factory.routers().aggregated_list.return_value = _empty_aggregated("routers")


# --- local fixtures for exercising the tools through the real MCP server --
#
# Mirrors test_tools_registration.py's `_fake_adc`/`all_clients_mocked`/
# `server` fixtures (kept local here rather than promoted to conftest.py,
# since only these two tools' call-through tests need them).


@pytest.fixture(autouse=True)
def _fake_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("google.auth.default", MagicMock(return_value=(MagicMock(), "adc-project")))


@pytest.fixture
def all_clients_mocked(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Every client `gcp_export_normalized_topology`'s underlying
    `get_vpc_topology` can reach returns the same MagicMock, whose
    `list`/`aggregated_list` calls default to an empty pager -- enough for
    both new tools to succeed against an empty (but valid) topology."""
    shared_mock = MagicMock()
    shared_mock.list.return_value = make_pager([])
    shared_mock.aggregated_list.return_value = make_aggregated_pager({}, items_field="items")
    monkeypatch.setattr(ClientFactory, "_client", lambda self, client_cls: shared_mock)
    return shared_mock


@pytest.fixture
def server(all_clients_mocked: MagicMock):
    return build_server(Settings(_env_file=None, gcp_default_project_id=PROJECT_ID))


# --- gcp_get_contract_capabilities --------------------------------------


def test_capability_manifest_shape() -> None:
    manifest = _capability_manifest()

    assert manifest["provider"] == "gcp"
    assert manifest["adapter_package"] == "gcp-network-mcp"
    assert manifest["contract_version"] == "1.0.0"
    assert manifest["min_supported_contract_version"] == "1.0.0"
    assert manifest["urn_grammar_version"] == 1
    assert manifest["supports_topology"] is True
    assert manifest["supports_diagnostics"] is False
    assert manifest["supports_observability"] is False
    assert manifest["generated_at"]  # a real timestamp, not empty


def test_capability_manifest_lists_expected_resource_types_and_omits_gcp_gaps() -> None:
    manifest = _capability_manifest()
    resource_types = {entry["resource_type"] for entry in manifest["supported_resource_types"]}

    expected = {
        "network",
        "subnet",
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
        "load-balancer",
        "endpoint",
        "address",
    }
    assert expected <= resource_types

    # GCP genuinely has no equivalent of these three -- never claimed.
    assert "route-table" not in resource_types
    assert "dns-resolver" not in resource_types
    assert "dns-rule" not in resource_types

    for entry in manifest["supported_resource_types"]:
        assert entry["export_tool"] == "gcp_export_normalized_topology"
        assert isinstance(entry["exact_mapping"], bool)
        if not entry["exact_mapping"]:
            assert entry["notes"], (
                f"{entry['resource_type']} claims a non-exact mapping with no notes"
            )


async def test_gcp_get_contract_capabilities_tool_call_succeeds(all_clients_mocked, server) -> None:
    result = await server.call_tool("gcp_get_contract_capabilities", {})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload
    assert payload["data"]["provider"] == "gcp"


# --- gcp_export_normalized_topology --------------------------------------


def test_export_normalized_topology_maps_nodes_and_edges(client_factory) -> None:
    network = compute_v1.Network(
        name="vpc-1", self_link=NETWORK_SELF_LINK, auto_create_subnetworks=True
    )
    subnet = compute_v1.Subnetwork(
        name="subnet-1",
        self_link=SUBNET_SELF_LINK,
        network=NETWORK_SELF_LINK,
        ip_cidr_range="10.0.0.0/24",
    )
    client_factory.networks().list.return_value = make_pager([network])
    client_factory.subnetworks().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [subnet]}, items_field="subnetworks"
    )
    client_factory.instances().aggregated_list.return_value = _empty_aggregated("instances")
    client_factory.routers().aggregated_list.return_value = _empty_aggregated("routers")

    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)
    graph = _to_topology_graph(topology, project_id=PROJECT_ID)

    assert graph["scope"] == {
        "provider": "gcp",
        "tenant_id": None,
        "account_id": None,
        "subscription_id": None,
        "project_id": PROJECT_ID,
        "resource_group": None,
        "region": None,
        "location": None,
        "zone": None,
        "collected_at": topology.observed_at,
    }
    assert graph["completeness"] == "complete"
    assert graph["api_call_count"] == topology.api_call_count

    urns_by_native_id = {node["native_id"]: node["urn"] for node in graph["nodes"]}
    network_urn = urns_by_native_id[NETWORK_SELF_LINK]
    subnet_urn = urns_by_native_id[SUBNET_SELF_LINK]

    assert network_urn.startswith("urn:mcnet:v1:gcp:")
    assert f"project_id={PROJECT_ID}" in network_urn
    assert network_urn.endswith(f":network:{quote_check(NETWORK_SELF_LINK)}")
    assert subnet_urn.endswith(f":subnet:{quote_check(SUBNET_SELF_LINK)}")
    assert "region=us-central1" in subnet_urn

    network_node = next(n for n in graph["nodes"] if n["native_id"] == NETWORK_SELF_LINK)
    assert network_node["kind"] == "resource"
    assert network_node["resource_type"] == "network"
    assert network_node["extensions"] == {"gcp": {"node_type": "network"}}

    edge = next(e for e in graph["edges"] if e["relationship"] == "belongs_to_network")
    assert edge["source_urn"] == subnet_urn
    assert edge["target_urn"] == network_urn
    assert edge["evidence"] == [
        {
            "source": "belongs_to_network",
            "detail": f"subnetwork subnet-1.network={NETWORK_SELF_LINK}",
        }
    ]


def quote_check(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="/-._~")


def test_export_normalized_topology_marks_unresolved_targets_and_external_nodes(
    client_factory,
) -> None:
    network = compute_v1.Network(
        name="vpc-1",
        self_link=NETWORK_SELF_LINK,
        peerings=[
            compute_v1.NetworkPeering(name="peer-1", network=OTHER_PROJECT_NETWORK, state="ACTIVE")
        ],
    )
    client_factory.networks().list.return_value = make_pager([network])
    client_factory.subnetworks().aggregated_list.return_value = _empty_aggregated("subnetworks")
    client_factory.instances().aggregated_list.return_value = _empty_aggregated("instances")
    client_factory.routers().aggregated_list.return_value = _empty_aggregated("routers")

    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)
    graph = _to_topology_graph(topology, project_id=PROJECT_ID)

    assert graph["completeness"] == "partial"
    assert graph["warnings"]
    for warning in graph["warnings"]:
        assert warning["scope"] is None
        assert warning["code"] == "OUT_OF_SCOPE_TARGET"

    external_node = next(n for n in graph["nodes"] if n["native_id"] == OTHER_PROJECT_NETWORK)
    assert external_node["kind"] == "external"
    assert external_node["resource_type"] == "network"
    assert external_node["scope"] is None

    peering_edge = next(e for e in graph["edges"] if e["relationship"] == "peered_with")
    assert peering_edge["target_urn"] == external_node["urn"]


def test_export_normalized_topology_empty_graph(client_factory) -> None:
    _stub_clean_topology(client_factory)
    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)
    graph = _to_topology_graph(topology, project_id=PROJECT_ID)
    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["warnings"] == []
    assert graph["completeness"] == "complete"


async def test_gcp_export_normalized_topology_tool_call_succeeds(
    all_clients_mocked, server
) -> None:
    result = await server.call_tool("gcp_export_normalized_topology", {})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload
    assert payload["data"]["scope"]["provider"] == "gcp"
    assert payload["data"]["scope"]["project_id"] == PROJECT_ID
