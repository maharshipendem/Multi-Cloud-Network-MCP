"""Exercises every registered MCP tool through the real ``call_tool()``
path at least once, with every GCP client library method it might call
mocked to return an empty (but successful) result.

This is a structural/wiring test, not a behavioral one (the per-tool
behavior -- normalization, next-hop derivation, health fan-out, etc. -- is
covered by each ``gcp/*.py`` module's own unit tests): it exists to catch
a tool wired to the wrong service-layer function, a wrong parameter name,
or a response envelope that doesn't serialize, none of which the
service-layer tests above would catch since they call service functions
directly rather than going through ``MCPServer.call_tool()``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.conftest import PROJECT_ID, FakeLegacyPager, FakePager, make_aggregated_pager, make_pager

from gcp_network_mcp.config import Settings
from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.server import build_server


@pytest.fixture(autouse=True)
def _fake_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("google.auth.default", MagicMock(return_value=(MagicMock(), "adc-project")))


@pytest.fixture
def all_clients_mocked(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Every client every tool can reach returns the same MagicMock, whose
    ``list``/``aggregated_list``/``get_health``/... calls all default to
    an empty pager -- overridden per-test where a tool needs real data."""
    shared_mock = MagicMock()
    shared_mock.list.return_value = make_pager([])
    shared_mock.aggregated_list.return_value = make_aggregated_pager({}, items_field="items")
    # search_projects/get_xpn_resources responses use a field other than
    # the default "items" -- an empty page with no attribute at all would
    # raise AttributeError, so give it the right (empty) shape directly.
    shared_mock.search_projects.return_value = FakePager([SimpleNamespace(projects=[])])
    shared_mock.get_xpn_resources.return_value = FakePager([SimpleNamespace(resources=[])])
    # get_xpn_host returns a single Project (not a pager); Pydantic needs
    # a real string for xpn_project_status, not an auto-generated MagicMock.
    from google.cloud import compute_v1

    shared_mock.get_xpn_host.return_value = compute_v1.Project(
        xpn_project_status="UNSPECIFIED_XPN_PROJECT_STATUS"
    )
    # Milestone 8: paginate_with_unreachable()-shaped calls (NCC) each need
    # a page shaped for that specific call's items_field; the legacy DNS
    # client (a per-project cache separate from `_client()`) also needs to
    # route through this same shared mock so `.list_zones()`/`.zone()` are
    # configurable the same way as every other client's methods.
    shared_mock.list_hubs.return_value = FakePager([SimpleNamespace(hubs=[], unreachable=[])])
    shared_mock.list_spokes.return_value = FakePager([SimpleNamespace(spokes=[], unreachable=[])])
    shared_mock.list_groups.return_value = FakePager([SimpleNamespace(groups=[], unreachable=[])])
    shared_mock.list_route_tables.return_value = FakePager(
        [SimpleNamespace(route_tables=[], unreachable=[])]
    )
    shared_mock.list_routes.return_value = FakePager([SimpleNamespace(routes=[], unreachable=[])])
    shared_mock.get_hub_status.return_value = FakePager(
        [SimpleNamespace(hub_status_entries=[], unreachable=[])]
    )
    shared_mock.list_zones.return_value = FakeLegacyPager([])
    # Single-object `get_*_status`/`get_diagnostics` calls unwrap a real
    # response's `.result` field -- an auto-generated MagicMock attribute
    # fails Pydantic string-field validation, so these need real (if
    # empty) proto-plus objects, exactly like `get_xpn_host` above.
    from google.cloud import network_management_v1

    shared_mock.get_router_status.return_value = SimpleNamespace(result=compute_v1.RouterStatus())
    shared_mock.get_status.return_value = SimpleNamespace(result=compute_v1.VpnGatewayStatus())
    shared_mock.get_diagnostics.return_value = SimpleNamespace(
        result=compute_v1.InterconnectDiagnostics()
    )
    shared_mock.get_connectivity_test.return_value = network_management_v1.ConnectivityTest()
    monkeypatch.setattr(ClientFactory, "_client", lambda self, client_cls: shared_mock)
    monkeypatch.setattr(ClientFactory, "dns_client", lambda self, project_id: shared_mock)
    return shared_mock


@pytest.fixture
def server(all_clients_mocked: MagicMock):
    return build_server(Settings(_env_file=None, gcp_default_project_id=PROJECT_ID))


TOOLS_NEEDING_NO_ARGS = [
    "gcp_get_caller_identity",
    "gcp_list_permitted_projects",
    "gcp_list_networks",
    "gcp_list_subnetworks",
    "gcp_list_routes",
    "gcp_list_firewall_rules",
    "gcp_list_network_firewall_policies",
    "gcp_list_instance_network_interfaces",
    "gcp_list_addresses",
    "gcp_list_forwarding_rules",
    "gcp_list_target_proxies",
    "gcp_list_backend_services",
    "gcp_list_routers",
    "gcp_list_network_peerings",
    "gcp_get_shared_vpc_host_status",
    "gcp_list_shared_vpc_service_projects",
    "gcp_get_vpc_topology",
    # Milestone 8
    "gcp_list_ncc_hubs",
    "gcp_list_ncc_spokes",
    "gcp_list_vpn_gateways",
    "gcp_list_vpn_tunnels",
    "gcp_list_external_vpn_gateways",
    "gcp_list_interconnects",
    "gcp_list_interconnect_attachments",
    "gcp_list_interconnect_locations",
    "gcp_list_service_attachments",
    "gcp_list_psc_endpoints",
    "gcp_list_private_service_access_ranges",
    "gcp_list_dns_zones",
    "gcp_list_packet_mirroring_policies",
    "gcp_list_vpc_flow_logs_configs",
    "gcp_list_connectivity_tests",
    "gcp_get_hybrid_topology",
    "gcp_find_network_risks",
    "gcp_get_network_health",
]


@pytest.mark.parametrize("tool_name", TOOLS_NEEDING_NO_ARGS)
async def test_tool_call_succeeds_with_empty_data(server, tool_name: str) -> None:
    result = await server.call_tool(tool_name, {})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload


async def test_hierarchical_firewall_policies_tool_requires_parent_id(server) -> None:
    result = await server.call_tool(
        "gcp_list_hierarchical_firewall_policies", {"parent_id": "organizations/12345"}
    )
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True


async def test_list_backend_services_can_skip_health(all_clients_mocked: MagicMock, server) -> None:
    result = await server.call_tool("gcp_list_backend_services", {"include_health": False})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    all_clients_mocked.get_health.assert_not_called()


async def test_list_firewall_rules_can_exclude_implied(server) -> None:
    result = await server.call_tool("gcp_list_firewall_rules", {"include_implied": False})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert payload["data"] == []


# --- Milestone 8: tools requiring parameters beyond project_id -------------

TOOLS_NEEDING_ARGS = [
    ("gcp_get_router_bgp_status", {"region": "us-central1", "router_name": "r1"}),
    ("gcp_list_ncc_groups", {"hub_name": "projects/p/locations/global/hubs/h1"}),
    ("gcp_list_ncc_route_tables", {"hub_name": "projects/p/locations/global/hubs/h1"}),
    (
        "gcp_list_ncc_routes",
        {"route_table_name": "projects/p/locations/global/hubs/h1/routeTables/rt1"},
    ),
    ("gcp_get_ncc_hub_status", {"hub_name": "projects/p/locations/global/hubs/h1"}),
    ("gcp_get_vpn_gateway_status", {"region": "us-central1", "vpn_gateway_name": "vg1"}),
    ("gcp_get_interconnect_diagnostics", {"interconnect_name": "ic1"}),
    ("gcp_list_dns_zone_records", {"zone_name": "z1"}),
    ("gcp_get_connectivity_test", {"test_name": "t1"}),
    ("gcp_query_logs", {"filter_expr": 'resource.type="gce_subnetwork"'}),
    ("gcp_query_metrics", {"filter_expr": 'metric.type="compute.googleapis.com/x"'}),
    (
        "gcp_explain_network_path",
        {
            "network_self_link": (
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-a"
            ),
            "destination_ip": "10.0.0.5",
        },
    ),
]


@pytest.mark.parametrize("tool_name,args", TOOLS_NEEDING_ARGS)
async def test_tool_call_succeeds_with_required_args(server, tool_name: str, args: dict) -> None:
    result = await server.call_tool(tool_name, args)
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True, payload
