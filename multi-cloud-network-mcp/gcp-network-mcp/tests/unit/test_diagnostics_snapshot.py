"""Unit tests for ``diagnostics.snapshot`` -- ``HybridNetworkSnapshot`` and
``collect_hybrid_snapshot()``.

The single most important behavior under test here is ``_collect()``'s
partial-failure resilience: a single resource family's underlying GCP
client call raising must degrade to an empty list plus a
``CollectionWarning`` for *that family only*, never abort the whole
snapshot or leak into any other family's result.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from google.api_core import exceptions as gax
from google.cloud import compute_v1, dns
from google.cloud import networkconnectivity_v1 as ncc
from tests.conftest import PROJECT_ID, FakeLegacyPager, FakePager, make_aggregated_pager, make_pager

from gcp_network_mcp.diagnostics.snapshot import (
    HybridNetworkSnapshot,
    _peerings_via_raw_networks,
    collect_hybrid_snapshot,
)

NETWORK_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
)
OTHER_PROJECT_NETWORK = (
    "https://www.googleapis.com/compute/v1/projects/other-proj/global/networks/vpc-x"
)
SUBNET_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "subnetworks/subnet-1"
)
ROUTE_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/routes/route-1"
)
FIREWALL_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/firewalls/allow-ssh"
)
FORWARDING_RULE_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "forwardingRules/fr-1"
)
ROUTER_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "routers/router-1"
)
VPN_GATEWAY_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "vpnGateways/vpn-gw-1"
)
VPN_TUNNEL_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "vpnTunnels/vpn-tunnel-1"
)
INTERCONNECT_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/interconnects/ic-1"
)
ATTACHMENT_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
    "interconnectAttachments/attach-1"
)
HUB_NAME = f"projects/{PROJECT_ID}/locations/global/hubs/hub-1"
SPOKE_NAME = f"projects/{PROJECT_ID}/locations/us-central1/spokes/spoke-1"
ROUTE_TABLE_NAME = f"{HUB_NAME}/routeTables/rt-1"


def _unreachable_pager(
    items: list[Any], *, items_field: str, unreachable: list[str] | None = None
) -> FakePager:
    """Build a fake pager matching ``paginate_with_unreachable``'s expected
    page shape (each NCC list call reads a different, call-specific items
    field), mirroring ``tests/unit/test_connectivity_center.py``'s own
    helper of the same shape."""
    page = SimpleNamespace(**{items_field: items}, unreachable=unreachable or [])
    return FakePager([page])


def _stub_full_snapshot(client_factory: Any) -> None:
    """Wire every resource family ``collect_hybrid_snapshot`` touches to
    return one real, successfully-collected item -- the "everything
    succeeds" control fixture that both the happy-path test and every
    partial-failure test (via one single override) start from."""
    network = compute_v1.Network(
        name="vpc-1",
        self_link=NETWORK_SELF_LINK,
        auto_create_subnetworks=True,
        peerings=[
            compute_v1.NetworkPeering(
                name="peer-1",
                network=OTHER_PROJECT_NETWORK,
                state="ACTIVE",
                exchange_subnet_routes=True,
            )
        ],
    )
    client_factory.networks().list.return_value = make_pager([network])

    subnet = compute_v1.Subnetwork(
        name="subnet-1",
        self_link=SUBNET_SELF_LINK,
        network=NETWORK_SELF_LINK,
        ip_cidr_range="10.0.0.0/24",
    )
    client_factory.subnetworks().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [subnet]}, items_field="subnetworks"
    )

    route = compute_v1.Route(
        name="route-1",
        self_link=ROUTE_SELF_LINK,
        network=NETWORK_SELF_LINK,
        dest_range="10.0.0.0/24",
        priority=1000,
        next_hop_gateway=(
            f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/gateways/"
            "default-internet-gateway"
        ),
    )
    client_factory.routes().list.return_value = make_pager([route])

    firewall_rule = compute_v1.Firewall(
        name="allow-ssh",
        self_link=FIREWALL_SELF_LINK,
        network=NETWORK_SELF_LINK,
        direction="INGRESS",
        priority=1000,
        disabled=False,
        allowed=[compute_v1.Allowed(I_p_protocol="tcp", ports=["22"])],
        source_ranges=["0.0.0.0/0"],
    )
    client_factory.firewalls().list.return_value = make_pager([firewall_rule])
    client_factory.network_firewall_policies().list.return_value = make_pager([])

    forwarding_rule = compute_v1.ForwardingRule(
        name="fr-1",
        self_link=FORWARDING_RULE_SELF_LINK,
        I_p_address="10.0.0.5",
        I_p_protocol="TCP",
        network=NETWORK_SELF_LINK,
    )
    client_factory.forwarding_rules().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [forwarding_rule]}, items_field="forwarding_rules"
    )

    router = compute_v1.Router(
        name="router-1", self_link=ROUTER_SELF_LINK, network=NETWORK_SELF_LINK
    )
    client_factory.routers().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [router]}, items_field="routers"
    )
    client_factory.routers().get_router_status.return_value = compute_v1.RouterStatusResponse(
        result=compute_v1.RouterStatus(
            network=NETWORK_SELF_LINK,
            bgp_peer_status=[
                compute_v1.RouterStatusBgpPeerStatus(
                    name="peer1",
                    ip_address="169.254.0.1",
                    peer_ip_address="169.254.0.2",
                    state="Established",
                    status="UP",
                )
            ],
        )
    )

    hub = ncc.Hub(
        name=HUB_NAME,
        state=ncc.State.ACTIVE,
        policy_mode=ncc.PolicyMode.PRESET,
        preset_topology=ncc.PresetTopology.MESH,
    )
    client_factory.ncc_hub_service().list_hubs.return_value = _unreachable_pager(
        [hub], items_field="hubs"
    )
    spoke = ncc.Spoke(
        name=SPOKE_NAME,
        hub=HUB_NAME,
        state=ncc.State.ACTIVE,
        spoke_type=ncc.SpokeType.VPC_NETWORK,
        linked_vpc_network=ncc.LinkedVpcNetwork(uri=NETWORK_SELF_LINK),
    )
    client_factory.ncc_hub_service().list_spokes.return_value = _unreachable_pager(
        [spoke], items_field="spokes"
    )
    route_table = ncc.RouteTable(name=ROUTE_TABLE_NAME, state=ncc.State.ACTIVE)
    client_factory.ncc_hub_service().list_route_tables.return_value = _unreachable_pager(
        [route_table], items_field="route_tables"
    )
    ncc_route = ncc.Route(
        name=f"{ROUTE_TABLE_NAME}/routes/route-1",
        ip_cidr_range="10.0.0.0/24",
        type_=ncc.RouteType.VPC_PRIMARY_SUBNET,
        state=ncc.State.ACTIVE,
        next_hop_vpc_network=ncc.NextHopVpcNetwork(uri=NETWORK_SELF_LINK),
    )
    client_factory.ncc_hub_service().list_routes.return_value = _unreachable_pager(
        [ncc_route], items_field="routes"
    )

    vpn_gateway = compute_v1.VpnGateway(
        name="vpn-gw-1", self_link=VPN_GATEWAY_SELF_LINK, network=NETWORK_SELF_LINK
    )
    client_factory.vpn_gateways().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [vpn_gateway]}, items_field="vpn_gateways"
    )
    client_factory.vpn_gateways().get_status.return_value = compute_v1.VpnGatewaysGetStatusResponse(
        result=compute_v1.VpnGatewayStatus(
            vpn_connections=[
                compute_v1.VpnGatewayStatusVpnConnection(
                    peer_gcp_gateway="peer-gw",
                    state=compute_v1.VpnGatewayStatusHighAvailabilityRequirementState(
                        state="CONNECTION_REDUNDANCY_MET"
                    ),
                )
            ]
        )
    )

    vpn_tunnel = compute_v1.VpnTunnel(
        name="vpn-tunnel-1",
        self_link=VPN_TUNNEL_SELF_LINK,
        vpn_gateway=VPN_GATEWAY_SELF_LINK,
        peer_ip="203.0.113.1",
        router=ROUTER_SELF_LINK,
        status="ESTABLISHED",
    )
    client_factory.vpn_tunnels().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [vpn_tunnel]}, items_field="vpn_tunnels"
    )

    interconnect = compute_v1.Interconnect(
        name="ic-1",
        self_link=INTERCONNECT_SELF_LINK,
        interconnect_type="DEDICATED",
        admin_enabled=True,
    )
    client_factory.interconnects().list.return_value = make_pager([interconnect])
    client_factory.interconnects().get_diagnostics.return_value = (
        compute_v1.InterconnectsGetDiagnosticsResponse(
            result=compute_v1.InterconnectDiagnostics(
                mac_address="00:00:00:00:00:00",
                bundle_operational_status="UP",
                links=[
                    compute_v1.InterconnectDiagnosticsLinkStatus(
                        circuit_id="c1", operational_status="UP"
                    )
                ],
            )
        )
    )

    attachment = compute_v1.InterconnectAttachment(
        name="attach-1",
        self_link=ATTACHMENT_SELF_LINK,
        interconnect=INTERCONNECT_SELF_LINK,
        router=ROUTER_SELF_LINK,
        type_="DEDICATED",
    )
    client_factory.interconnect_attachments().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [attachment]}, items_field="interconnect_attachments"
    )

    client_factory.compute_projects().get_xpn_host.return_value = compute_v1.Project(
        xpn_project_status="HOST"
    )

    zone = dns.ManagedZone("zone-1", dns_name="example.com.", client=None)
    zone._properties["nameServers"] = ["ns-cloud-a1.googledomains.com."]
    client_factory.dns_client(PROJECT_ID).list_zones.return_value = FakeLegacyPager([[zone]])


def _assert_every_other_family_intact(
    snapshot: HybridNetworkSnapshot, *, skip: str, also_skip: tuple[str, ...] = ()
) -> None:
    """Assert every resource family besides ``skip``/``also_skip`` is
    populated exactly as ``_stub_full_snapshot`` wires it -- proof a
    failure in one family never silently empties (or otherwise disturbs)
    any other. ``also_skip`` covers a family that is a *downstream
    consequence* of ``skip`` failing (e.g. ``vpn_gateway_statuses`` when
    ``vpn_gateways`` itself failed) -- the caller asserts that one
    separately."""
    skipped = {skip, *also_skip}
    expectations = {
        "networks": 1,
        "subnetworks": 1,
        "routes": 1,
        "peerings": 1,
        "firewall_rules": 3,  # 1 real rule + 2 implied (allow-egress/deny-ingress)
        "forwarding_rules": 1,
        "routers": 1,
        "router_statuses": 1,
        "ncc_hubs": 1,
        "ncc_spokes": 1,
        "ncc_route_tables": 1,
        "ncc_routes": 1,
        "vpn_gateways": 1,
        "vpn_gateway_statuses": 1,
        "vpn_tunnels": 1,
        "interconnects": 1,
        "interconnect_diagnostics": 1,
        "interconnect_attachments": 1,
        "dns_zones": 1,
    }
    for field, expected_len in expectations.items():
        if field in skipped:
            continue
        actual = getattr(snapshot, field)
        assert len(actual) == expected_len, (
            f"{field} should still have {expected_len} entr(y/ies) after an unrelated "
            f"family's collection failed, got {len(actual)}"
        )
    if skip != "shared_vpc_host_status":
        assert snapshot.shared_vpc_host_status is not None
        assert snapshot.shared_vpc_host_status.xpn_project_status == "HOST"


def test_collect_hybrid_snapshot_happy_path_populates_every_family_with_no_warnings(
    client_factory: Any,
) -> None:
    """Control test: when every underlying GCP call succeeds, the
    snapshot carries zero warnings and every resource family is
    populated from its own mocked data -- the baseline every
    partial-failure test below is compared against."""
    _stub_full_snapshot(client_factory)

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.warnings == []
    assert snapshot.project_id == PROJECT_ID
    assert snapshot.observed_at
    _assert_every_other_family_intact(snapshot, skip="")


def test_collect_hybrid_snapshot_isolates_subnetwork_collection_failure(
    client_factory: Any,
) -> None:
    """Regression test for the ``_collect()`` partial-failure fix: a
    ``Forbidden`` raised by the underlying ``SubnetworksClient.aggregated_list``
    gapic call (simulating a disabled API / missing IAM permission) must
    not raise out of ``collect_hybrid_snapshot`` -- it must degrade to an
    empty ``subnetworks`` list plus a ``COLLECTION_FAILED`` warning, while
    every other resource family collects normally."""
    _stub_full_snapshot(client_factory)
    client_factory.subnetworks().aggregated_list.side_effect = gax.Forbidden(
        "Access Not Configured. Compute Engine API has not been used in project"
    )

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.subnetworks == []
    matching_warnings = [w for w in snapshot.warnings if w.resource_type == "subnetwork"]
    assert len(matching_warnings) == 1
    assert matching_warnings[0].code == "COLLECTION_FAILED"
    assert "subnetwork" in matching_warnings[0].message
    _assert_every_other_family_intact(snapshot, skip="subnetworks")


def test_collect_hybrid_snapshot_isolates_forwarding_rule_collection_failure(
    client_factory: Any,
) -> None:
    """Same regression, for ``forwarding_rules`` (``ForwardingRulesClient.
    aggregated_list``) via a different underlying exception type
    (``PermissionDenied``, a ``Forbidden`` subclass) -- proving ``_collect()``
    isn't accidentally coupled to one specific exception class."""
    _stub_full_snapshot(client_factory)
    client_factory.forwarding_rules().aggregated_list.side_effect = gax.PermissionDenied(
        "The caller does not have permission"
    )

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.forwarding_rules == []
    matching_warnings = [w for w in snapshot.warnings if w.resource_type == "forwarding_rule"]
    assert len(matching_warnings) == 1
    assert matching_warnings[0].code == "COLLECTION_FAILED"
    _assert_every_other_family_intact(snapshot, skip="forwarding_rules")


def test_collect_hybrid_snapshot_isolates_ncc_hub_collection_failure(
    client_factory: Any,
) -> None:
    """Same regression, for ``ncc_hubs`` (``HubServiceClient.list_hubs``,
    reached via ``paginate_with_unreachable`` -- a different pagination
    helper than the ``aggregated_list`` families above). Also proves the
    downstream ``ncc_route_tables``/``ncc_routes`` fan-out is a *consequence*
    of the same failure, not a second independent one -- that loop is
    seeded by iterating the (now-empty) ``ncc_hubs`` list, so it never
    runs and contributes no warning of its own. ``ncc_spokes`` is listed
    via its own independent client call, unrelated to ``ncc_hubs``, and
    must still collect normally."""
    _stub_full_snapshot(client_factory)
    client_factory.ncc_hub_service().list_hubs.side_effect = gax.Forbidden(
        "Network Connectivity API has not been used in project"
    )

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.ncc_hubs == []
    assert snapshot.ncc_route_tables == []
    assert snapshot.ncc_routes == []
    matching_warnings = [w for w in snapshot.warnings if w.resource_type == "ncc_hub"]
    assert len(matching_warnings) == 1
    assert matching_warnings[0].code == "COLLECTION_FAILED"
    assert not any(w.resource_type == "ncc_route_table" for w in snapshot.warnings)
    _assert_every_other_family_intact(
        snapshot, skip="ncc_hubs", also_skip=("ncc_route_tables", "ncc_routes")
    )


def test_collect_hybrid_snapshot_isolates_vpn_gateway_collection_failure(
    client_factory: Any,
) -> None:
    """Same regression, for ``vpn_gateways`` (``VpnGatewaysClient.
    aggregated_list``) via a ``NotFound`` (a distinct ``GoogleAPICallError``
    subclass from the ``Forbidden``/``PermissionDenied`` used above) --
    ``_collect()``'s ``except Exception`` is deliberately broad, not
    narrowed to 403-shaped errors. A failed ``vpn_gateways`` collection
    also means the gateway-status fan-out loop never runs (there are no
    gateways to iterate), so ``vpn_gateway_statuses`` is empty too --
    that's an expected *consequence* of the same failure, not a second
    independent failure."""
    _stub_full_snapshot(client_factory)
    client_factory.vpn_gateways().aggregated_list.side_effect = gax.NotFound(
        "requested entity was not found"
    )

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.vpn_gateways == []
    assert snapshot.vpn_gateway_statuses == []
    matching_warnings = [w for w in snapshot.warnings if w.resource_type == "vpn_gateway"]
    assert len(matching_warnings) == 1
    assert matching_warnings[0].code == "COLLECTION_FAILED"
    # vpn_gateway_status itself never even attempted a call -- no second warning for it.
    assert not any(w.resource_type == "vpn_gateway_status" for w in snapshot.warnings)
    _assert_every_other_family_intact(
        snapshot, skip="vpn_gateways", also_skip=("vpn_gateway_statuses",)
    )


def test_collect_hybrid_snapshot_isolates_shared_vpc_host_status_collection_failure(
    client_factory: Any,
) -> None:
    """Same regression, for the single (non-paginated) ``shared_vpc_host_status``
    call (``ProjectsClient.get_xpn_host``) -- proves ``_collect()`` handles
    a plain single-result lambda wrapper the same way it handles a
    paginated list call."""
    _stub_full_snapshot(client_factory)
    client_factory.compute_projects().get_xpn_host.side_effect = gax.Forbidden(
        "Access Not Configured."
    )

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.shared_vpc_host_status is None
    matching_warnings = [
        w for w in snapshot.warnings if w.resource_type == "shared_vpc_host_status"
    ]
    assert len(matching_warnings) == 1
    assert matching_warnings[0].code == "COLLECTION_FAILED"
    _assert_every_other_family_intact(snapshot, skip="shared_vpc_host_status")


def test_collect_hybrid_snapshot_isolates_dns_zone_collection_failure(client_factory: Any) -> None:
    """Same regression, for ``dns_zones`` (``google.cloud.dns.Client.list_zones``
    -- the one client in this codebase that isn't gapic-generated, cached
    per-project rather than reused from ``ClientFactory._clients``).
    Proves ``_collect()`` degrades this legacy-client family the same way
    as every gapic-backed one."""
    _stub_full_snapshot(client_factory)
    client_factory.dns_client(PROJECT_ID).list_zones.side_effect = gax.Forbidden(
        "Cloud DNS API has not been used in project"
    )

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.dns_zones == []
    matching_warnings = [w for w in snapshot.warnings if w.resource_type == "dns_zone"]
    assert len(matching_warnings) == 1
    assert matching_warnings[0].code == "COLLECTION_FAILED"
    _assert_every_other_family_intact(snapshot, skip="dns_zones")


def test_collect_hybrid_snapshot_skips_hierarchical_policies_without_parent_id(
    client_factory: Any,
) -> None:
    """``hierarchical_firewall_parent_id`` is optional; when omitted, the
    hierarchical Firewall Policy collection is never attempted at all --
    no call, no warning, just an empty list (distinct from a collection
    failure)."""
    _stub_full_snapshot(client_factory)

    snapshot = collect_hybrid_snapshot(client_factory, project_id=PROJECT_ID)

    assert snapshot.hierarchical_firewall_policies == []
    client_factory.firewall_policies().list.assert_not_called()
    assert not any(w.resource_type == "firewall_policy" for w in snapshot.warnings)


def test_peerings_via_raw_networks_extracts_embedded_peerings(client_factory: Any) -> None:
    """``_peerings_via_raw_networks`` re-derives peerings from a fresh raw
    ``NetworksClient.list`` call (since ``list_networks`` doesn't retain
    the raw ``compute_v1.Network`` post-normalization) -- verify it
    extracts exactly the peerings embedded on each returned network,
    matching ``gcp.networking.extract_peerings``'s own behavior."""
    network = compute_v1.Network(
        name="vpc-1",
        self_link=NETWORK_SELF_LINK,
        peerings=[
            compute_v1.NetworkPeering(name="peer-1", network=OTHER_PROJECT_NETWORK, state="ACTIVE")
        ],
    )
    client_factory.networks().list.return_value = make_pager([network])

    peerings = _peerings_via_raw_networks(client_factory, project_id=PROJECT_ID)

    assert len(peerings) == 1
    assert peerings[0].name == "peer-1"
    assert peerings[0].owning_network_self_link == NETWORK_SELF_LINK
    assert peerings[0].network == OTHER_PROJECT_NETWORK
    assert peerings[0].state == "ACTIVE"


def test_peerings_via_raw_networks_returns_empty_for_no_networks(client_factory: Any) -> None:
    client_factory.networks().list.return_value = make_pager([])
    assert _peerings_via_raw_networks(client_factory, project_id=PROJECT_ID) == []
