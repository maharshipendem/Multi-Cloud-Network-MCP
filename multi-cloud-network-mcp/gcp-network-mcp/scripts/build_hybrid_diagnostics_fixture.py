"""Regenerates ``fixtures/hybrid_diagnostics_scenarios.json``.

Builds a single sanitized ``HybridNetworkSnapshot`` packing one instance
of every Milestone 8 scenario category (NCC propagation, HA VPN
redundancy, BGP route preference/degradation, Interconnect states,
Shared VPC, hierarchical Firewall Policy visibility gap, VPC peering
route import/export limitations, Cloud NAT egress, an unknown-next-hop
route, overlapping CIDR routes, public forwarding rule exposure,
split-horizon DNS, and partial-IAM/API-disabled/throttling/stale-
monitoring-data collection warnings) by constructing real GCP SDK
objects and running them through the real ``gcp/*.py`` normalizers --
never hand-authored JSON that could drift from the actual model shapes.

Run from the ``gcp-network-mcp/`` package root:

    python scripts/build_hybrid_diagnostics_fixture.py

See ``fixtures/README.md`` for what each scenario maps to, and
``tests/unit/test_diagnostics_offline.py``'s golden test for the exact
findings this fixture is expected to produce.
"""

from __future__ import annotations

import json

from google.cloud import compute_v1
from google.cloud import networkconnectivity_v1 as ncc

from gcp_network_mcp.diagnostics.health import get_network_health
from gcp_network_mcp.diagnostics.hybrid_topology import build_hybrid_topology
from gcp_network_mcp.diagnostics.risks import find_network_risks
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from gcp_network_mcp.gcp.connectivity_center import normalize_hub, normalize_spoke
from gcp_network_mcp.gcp.dns import _normalize_zone
from gcp_network_mcp.gcp.firewall import normalize_firewall_rule
from gcp_network_mcp.gcp.interconnect import (
    normalize_interconnect,
    normalize_interconnect_attachment,
)
from gcp_network_mcp.gcp.load_balancing import normalize_forwarding_rule
from gcp_network_mcp.gcp.nat import normalize_router
from gcp_network_mcp.gcp.networking import normalize_network, normalize_subnetwork
from gcp_network_mcp.gcp.routes import normalize_route
from gcp_network_mcp.gcp.vpn import normalize_vpn_gateway, normalize_vpn_tunnel
from gcp_network_mcp.models.bgp import RouterBgpPeerStatus, RouterStatusSummary
from gcp_network_mcp.models.common import CollectionWarning
from gcp_network_mcp.models.firewall import implied_firewall_rules
from gcp_network_mcp.models.interconnect import (
    InterconnectDiagnostics,
    InterconnectDiagnosticsLinkStatus,
)
from gcp_network_mcp.models.peering import NetworkPeering
from gcp_network_mcp.models.shared_vpc import SharedVpcHostStatus
from gcp_network_mcp.models.vpn import (
    VpnGatewayConnectionStatus,
    VpnGatewayConnectionTunnel,
    VpnGatewayStatus,
)

PROJECT_ID = "scenario-net-project"
OBSERVED_AT = "2026-08-27T12:00:00+00:00"


class _RawDnsZone:
    """A stand-in for ``google.cloud.dns.ManagedZone`` carrying exactly
    the attributes ``gcp.dns._normalize_zone`` reads -- avoids this
    script needing a real (per-project, network-touching) DNS client."""

    def __init__(self, *, name, dns_name, description, zone_id, name_servers, name_server_set):
        self.name = name
        self.dns_name = dns_name
        self.description = description
        self.zone_id = zone_id
        self.name_servers = name_servers
        self.name_server_set = name_server_set


def _link(kind: str, name: str, *, region: str | None = None) -> str:
    base = f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}"
    if region:
        return f"{base}/regions/{region}/{kind}/{name}"
    return f"{base}/global/{kind}/{name}"


def build_snapshot() -> HybridNetworkSnapshot:
    # --- Networks / Shared VPC (scenario: Shared VPC) ----------------------
    net_a_link = _link("networks", "vpc-a")
    net_b_link = _link("networks", "vpc-b")

    network_a = normalize_network(
        compute_v1.Network(
            name="vpc-a",
            self_link=net_a_link,
            auto_create_subnetworks=False,
            peerings=[
                compute_v1.NetworkPeering(
                    name="a-to-b", network=net_b_link, state="ACTIVE", exchange_subnet_routes=True
                )
            ],
        ),
        project_id=PROJECT_ID,
    )
    network_b = normalize_network(
        compute_v1.Network(name="vpc-b", self_link=net_b_link, auto_create_subnetworks=False),
        project_id=PROJECT_ID,
    )
    # scenario: peering route import/export limitation (PEER-001) -- the
    # normalized NetworkPeering is constructed directly (mirroring
    # gcp.peering.list_network_peerings' own approach of reading it off
    # the owning Network's embedded `peerings` field) rather than via a
    # normalizer, since PEER-001's flags aren't on the raw peering above.
    peering = NetworkPeering(
        name="a-to-b",
        owning_network_self_link=net_a_link,
        network=net_b_link,
        state="ACTIVE",
        exchange_subnet_routes=False,
        export_custom_routes=False,
        import_custom_routes=False,
    )
    shared_vpc_status = SharedVpcHostStatus(project_id=PROJECT_ID, xpn_project_status="HOST")

    subnet = normalize_subnetwork(
        compute_v1.Subnetwork(
            name="subnet-a-central1",
            self_link=_link("subnetworks", "subnet-a-central1", region="us-central1"),
            network=net_a_link,
            ip_cidr_range="10.10.0.0/20",
            region=(
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1"
            ),
        ),
        project_id=PROJECT_ID,
    )

    # --- Routes (scenarios: CIDR overlap, unknown next hop) ----------------
    default_route = normalize_route(
        compute_v1.Route(
            name="default-route",
            self_link=_link("routes", "default-route"),
            network=net_a_link,
            dest_range="0.0.0.0/0",
            priority=1000,
            next_hop_gateway=_link("gateways", "default-internet-gateway"),
        ),
        project_id=PROJECT_ID,
    )
    overlap_route_a = normalize_route(
        compute_v1.Route(
            name="static-a",
            self_link=_link("routes", "static-a"),
            network=net_a_link,
            dest_range="10.20.0.0/16",
            priority=1000,
            next_hop_ip="10.10.0.5",
        ),
        project_id=PROJECT_ID,
    )
    overlap_route_b = normalize_route(
        compute_v1.Route(
            name="static-b",
            self_link=_link("routes", "static-b"),
            network=net_a_link,
            dest_range="10.20.4.0/24",  # overlaps static-a -- ROUTE-002
            priority=900,
            next_hop_ip="10.10.0.6",
        ),
        project_id=PROJECT_ID,
    )
    # scenario: unknown next hop -- no next_hop_* field set at all.
    unknown_next_hop_route = normalize_route(
        compute_v1.Route(
            name="mystery-route",
            self_link=_link("routes", "mystery-route"),
            network=net_a_link,
            dest_range="192.168.100.0/24",
            priority=1000,
        ),
        project_id=PROJECT_ID,
    )

    # --- Firewall (scenario: hierarchical firewall policy visibility gap) --
    explicit_allow = normalize_firewall_rule(
        compute_v1.Firewall(
            name="allow-ssh-internal",
            self_link=_link("firewalls", "allow-ssh-internal"),
            network=net_a_link,
            direction="INGRESS",
            priority=1000,
            disabled=False,
            allowed=[compute_v1.Allowed(I_p_protocol="tcp", ports=["22"])],
            source_ranges=["10.0.0.0/8"],
        ),
        project_id=PROJECT_ID,
    )
    firewall_rules = [
        explicit_allow,
        *implied_firewall_rules(network_self_link=net_a_link, network_name="vpc-a"),
    ]

    # --- Cloud Router / Cloud NAT (scenario: Cloud NAT egress blocked) -----
    router = normalize_router(
        compute_v1.Router(
            name="router-a",
            self_link=_link("routers", "router-a", region="us-central1"),
            network=net_a_link,
            region=(
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1"
            ),
            nats=[
                compute_v1.RouterNat(
                    name="nat-a",
                    nat_ip_allocate_option="MANUAL_ONLY",
                    nat_ips=[],  # NAT-001 critical: manual allocation, zero IPs
                    min_ports_per_vm=32,  # also triggers the low-port-allocation branch
                )
            ],
            bgp_peers=[
                compute_v1.RouterBgpPeer(
                    name="peer-onprem",
                    interface_name="if-0",
                    peer_ip_address="169.254.1.2",
                    peer_asn=65001,
                )
            ],
        ),
        project_id=PROJECT_ID,
    )

    # --- BGP status (scenario: BGP route preference / degraded session) ----
    router_status = RouterStatusSummary(
        router_self_link=router.self_link,
        network_self_link=net_a_link,
        bgp_peer_status=[
            RouterBgpPeerStatus(
                name="peer-onprem",
                ip_address="169.254.1.1",
                peer_ip_address="169.254.1.2",
                state="Established",
                status="UP",
                num_learned_routes=12,
            ),
            RouterBgpPeerStatus(
                name="peer-secondary",
                ip_address="169.254.2.1",
                peer_ip_address="169.254.2.2",
                state="Established",
                status="UP",
                num_learned_routes=0,  # HYBRID-003 medium: UP but zero learned routes
            ),
        ],
        observed_at=OBSERVED_AT,
    )

    # --- NCC (scenario: NCC propagation) ------------------------------------
    hub_name = f"projects/{PROJECT_ID}/locations/global/hubs/hub-1"
    hub = normalize_hub(
        ncc.Hub(
            name=hub_name,
            state=ncc.State.ACTIVE,
            policy_mode=ncc.PolicyMode.PRESET,
            preset_topology=ncc.PresetTopology.MESH,
            spoke_summary=ncc.SpokeSummary(
                spoke_state_counts=[
                    ncc.SpokeSummary.SpokeStateCount(state=ncc.State.ACTIVE, count=1),
                    ncc.SpokeSummary.SpokeStateCount(state=ncc.State.INACTIVE, count=1),
                ]
            ),
        ),
        project_id=PROJECT_ID,
    )
    spoke_active = normalize_spoke(
        ncc.Spoke(
            name=f"projects/{PROJECT_ID}/locations/us-central1/spokes/spoke-a",
            hub=hub_name,
            state=ncc.State.ACTIVE,
            spoke_type=ncc.SpokeType.VPC_NETWORK,
            linked_vpc_network=ncc.LinkedVpcNetwork(uri=net_a_link),
        ),
        project_id=PROJECT_ID,
    )
    spoke_inactive = normalize_spoke(
        ncc.Spoke(
            name=f"projects/{PROJECT_ID}/locations/us-central1/spokes/spoke-b",
            hub=hub_name,
            state=ncc.State.INACTIVE,
            spoke_type=ncc.SpokeType.VPC_NETWORK,
            linked_vpc_network=ncc.LinkedVpcNetwork(uri=net_b_link),
            reasons=[
                ncc.Spoke.StateReason(
                    code=ncc.Spoke.StateReason.Code.PENDING_REVIEW,
                    message="Awaiting hub administrator review.",
                )
            ],
        ),
        project_id=PROJECT_ID,
    )

    # --- VPN (scenario: HA VPN redundancy) ----------------------------------
    vpn_gateway_link = _link("vpnGateways", "ha-vpn-1", region="us-central1")
    vpn_gateway = normalize_vpn_gateway(
        compute_v1.VpnGateway(
            name="ha-vpn-1",
            self_link=vpn_gateway_link,
            network=net_a_link,
            region=(
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1"
            ),
            vpn_interfaces=[
                compute_v1.VpnGatewayVpnGatewayInterface(id=0, ip_address="203.0.113.10"),
                compute_v1.VpnGatewayVpnGatewayInterface(id=1, ip_address="203.0.113.11"),
            ],
        ),
        project_id=PROJECT_ID,
    )
    vpn_gateway_status = VpnGatewayStatus(
        vpn_gateway_self_link=vpn_gateway_link,
        connections=[
            VpnGatewayConnectionStatus(
                peer_external_gateway=None,
                peer_gcp_gateway=None,
                # scenario: HA redundancy requirement not met (HYBRID-001)
                ha_requirement_state="CONNECTION_REDUNDANCY_NOT_MET",
                ha_unsatisfied_reason="Only one of two tunnels is established.",
                tunnels=[
                    VpnGatewayConnectionTunnel(
                        tunnel_url=_link("vpnTunnels", "tunnel-1", region="us-central1"),
                        local_gateway_interface=0,
                        peer_gateway_interface=0,
                    )
                ],
            )
        ],
        observed_at=OBSERVED_AT,
    )
    vpn_tunnel_established = normalize_vpn_tunnel(
        compute_v1.VpnTunnel(
            name="tunnel-1",
            self_link=_link("vpnTunnels", "tunnel-1", region="us-central1"),
            vpn_gateway=vpn_gateway_link,
            peer_ip="198.51.100.10",
            status="ESTABLISHED",
            shared_secret="never-returned",  # proves redaction end-to-end
        ),
        project_id=PROJECT_ID,
    )
    vpn_tunnel_down = normalize_vpn_tunnel(
        compute_v1.VpnTunnel(
            name="tunnel-2",
            self_link=_link("vpnTunnels", "tunnel-2", region="us-central1"),
            vpn_gateway=vpn_gateway_link,
            peer_ip="198.51.100.11",
            status="FAILED",  # HYBRID-001: not ESTABLISHED
        ),
        project_id=PROJECT_ID,
    )

    # --- Interconnect (scenario: Interconnect states) -----------------------
    ic_healthy_link = _link("interconnects", "ic-primary")
    ic_healthy = normalize_interconnect(
        compute_v1.Interconnect(
            name="ic-primary",
            self_link=ic_healthy_link,
            interconnect_type="DEDICATED",
            admin_enabled=True,
            operational_status="OS_ACTIVE",
        ),
        project_id=PROJECT_ID,
    )
    ic_degraded_link = _link("interconnects", "ic-secondary")
    ic_degraded = normalize_interconnect(
        compute_v1.Interconnect(
            name="ic-secondary",
            self_link=ic_degraded_link,
            interconnect_type="DEDICATED",
            admin_enabled=True,
            operational_status="OS_UNPROVISIONED",  # HYBRID-002: not operationally up
        ),
        project_id=PROJECT_ID,
    )
    ic_diagnostics_degraded = InterconnectDiagnostics(
        interconnect_self_link=ic_degraded_link,
        mac_address="00:1a:2b:3c:4d:5e",
        bundle_operational_status="DOWN",
        links=[
            InterconnectDiagnosticsLinkStatus(circuit_id="circuit-1", operational_status="DOWN")
        ],
        observed_at=OBSERVED_AT,
    )
    attachment = normalize_interconnect_attachment(
        compute_v1.InterconnectAttachment(
            name="attach-primary",
            self_link=_link("interconnectAttachments", "attach-primary", region="us-central1"),
            interconnect=ic_healthy_link,
            router=router.self_link,
            type_="DEDICATED",
            state="ACTIVE",
            pairing_key="never-returned-either",  # proves redaction end-to-end
        ),
        project_id=PROJECT_ID,
    )

    # --- Forwarding rule (scenario: public exposure) ------------------------
    public_forwarding_rule = normalize_forwarding_rule(
        compute_v1.ForwardingRule(
            name="public-lb",
            self_link=_link("forwardingRules", "public-lb", region="us-central1"),
            I_p_address="203.0.113.50",
            I_p_protocol="TCP",
            port_range="443-443",
            load_balancing_scheme="EXTERNAL",
            network=net_a_link,
            region=(
                f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1"
            ),
        ),
        project_id=PROJECT_ID,
    )

    # --- DNS (scenario: split-horizon DNS, evaluated as indeterminate) -----
    dns_zone_with_ns = _normalize_zone(
        _RawDnsZone(
            name="prod-zone",
            dns_name="prod.example.internal.",
            description="Internal split-horizon zone",
            zone_id="1122334455",
            name_servers=["ns-cloud-a1.googledomains.com.", "ns-cloud-a2.googledomains.com."],
            name_server_set=None,
        ),
        project_id=PROJECT_ID,
    )
    dns_zone_no_ns = _normalize_zone(
        _RawDnsZone(
            name="orphaned-zone",
            dns_name="orphaned.example.internal.",
            description=None,
            zone_id="9988776655",
            name_servers=[],  # DNS-001 high confidence: no name servers assigned
            name_server_set=None,
        ),
        project_id=PROJECT_ID,
    )

    # --- Collection warnings (scenarios: partial IAM, API-disabled, --------
    # throttling, stale monitoring data) -- representative of what a real
    # degraded collection looks like, authored directly since they
    # describe collection-time conditions rather than normalizer output.
    warnings = [
        CollectionWarning(
            resource_type="service_attachment",
            code="COLLECTION_FAILED",
            message=(
                "Could not collect service_attachment: 403 Compute Engine API has not been "
                "used in project 'scenario-net-project' before or it is disabled."
            ),
            project_id=PROJECT_ID,
        ),
        CollectionWarning(
            resource_type="interconnect_attachment",
            code="PERMISSION_DENIED",
            message=(
                "The caller does not have permission to list interconnectAttachments in "
                "region us-east1 (partial IAM grant -- only us-central1 was authorized)."
            ),
            project_id=PROJECT_ID,
            scope="regions/us-east1",
        ),
        CollectionWarning(
            resource_type="time_series",
            code="RESOURCE_EXHAUSTED",
            message=(
                "Cloud Monitoring API request was throttled (quota exceeded); metric data "
                "for this window may be incomplete."
            ),
            project_id=PROJECT_ID,
        ),
        CollectionWarning(
            resource_type="log_entry",
            code="STALE_DATA",
            message=(
                "Cloud Logging returned entries with a maximum timestamp more than 15 "
                "minutes older than the query time -- log ingestion may be delayed."
            ),
            project_id=PROJECT_ID,
        ),
    ]

    return HybridNetworkSnapshot(
        project_id=PROJECT_ID,
        observed_at=OBSERVED_AT,
        networks=[network_a, network_b],
        subnetworks=[subnet],
        routes=[default_route, overlap_route_a, overlap_route_b, unknown_next_hop_route],
        peerings=[peering],
        firewall_rules=firewall_rules,
        network_firewall_policies=[],
        hierarchical_firewall_policies=[],  # deliberately empty: FW-002 indeterminate advisory
        forwarding_rules=[public_forwarding_rule],
        routers=[router],
        router_statuses=[router_status],
        ncc_hubs=[hub],
        ncc_spokes=[spoke_active, spoke_inactive],
        ncc_route_tables=[],
        ncc_routes=[],
        vpn_gateways=[vpn_gateway],
        vpn_gateway_statuses=[vpn_gateway_status],
        vpn_tunnels=[vpn_tunnel_established, vpn_tunnel_down],
        interconnects=[ic_healthy, ic_degraded],
        interconnect_attachments=[attachment],
        interconnect_diagnostics=[ic_diagnostics_degraded],
        shared_vpc_host_status=shared_vpc_status,
        dns_zones=[dns_zone_with_ns, dns_zone_no_ns],
        warnings=warnings,
    )


def main() -> None:
    snapshot = build_snapshot()

    out_path = "fixtures/hybrid_diagnostics_scenarios.json"
    with open(out_path, "w") as f:
        json.dump(snapshot.model_dump(mode="json"), f, indent=2)
        f.write("\n")
    print(f"wrote {out_path}")

    findings = find_network_risks(snapshot)
    print(f"{len(findings)} findings, rule_ids={sorted({f.rule_id for f in findings})}")
    topology = build_hybrid_topology(snapshot)
    print(
        f"topology: {len(topology.nodes)} nodes, {len(topology.edges)} edges, "
        f"completeness={topology.completeness}"
    )
    health = get_network_health(snapshot)
    print(
        f"health: overall_status={health.overall_status}, "
        f"counts={health.finding_counts_by_severity}"
    )


if __name__ == "__main__":
    main()
