from __future__ import annotations

from aws_cloudops_mcp.diagnostics.routing import resolve_path
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import Route, RouteTable, RouteTableAssociation, Subnet, Vpc
from aws_cloudops_mcp.models.network_resources import (
    ManagedPrefixList,
    ManagedPrefixListEntry,
    NatGateway,
    VpcPeeringConnection,
    VpcPeeringPeer,
)
from aws_cloudops_mcp.models.transit_gateway import (
    TransitGatewayRoute,
    TransitGatewayRouteAttachment,
)

_COMMON = {
    "account_id": "123456789012",
    "region": "us-east-1",
    "observed_at": "2026-08-27T00:00:00Z",
}


def _vpc(vpc_id: str, cidr: str) -> Vpc:
    return Vpc(
        **_COMMON,
        vpc_id=vpc_id,
        cidr_block=cidr,
        state="available",
        is_default=False,
    )


def _subnet(subnet_id: str, vpc_id: str, cidr: str, az: str = "us-east-1a") -> Subnet:
    return Subnet(
        **_COMMON,
        subnet_id=subnet_id,
        vpc_id=vpc_id,
        cidr_block=cidr,
        availability_zone=az,
        available_ip_address_count=250,
        map_public_ip_on_launch=False,
    )


def _route_table(
    rt_id: str,
    vpc_id: str,
    routes: list[Route],
    subnet_ids: list[str] | None = None,
    main: bool = False,
) -> RouteTable:
    associations = [RouteTableAssociation(subnet_id=sid, main=False) for sid in (subnet_ids or [])]
    if main:
        associations.append(RouteTableAssociation(main=True))
    return RouteTable(
        **_COMMON, route_table_id=rt_id, vpc_id=vpc_id, routes=routes, associations=associations
    )


def test_same_vpc_allowed_traffic_resolves_to_local_route() -> None:
    """Scenario: allowed same-VPC traffic."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[
            _subnet("subnet-a", "vpc-1", "10.0.1.0/24"),
            _subnet("subnet-b", "vpc-1", "10.0.2.0/24"),
        ],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.0.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    )
                ],
                subnet_ids=["subnet-a", "subnet-b"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="10.0.2.5")
    assert result.verdict == "routable"
    assert result.finding.confidence == "high"
    assert "local" in result.finding.summary.lower()
    assert result.hops[0].target_type == "local"


def test_blocked_same_vpc_traffic_no_route_to_destination() -> None:
    """Scenario: blocked same-VPC traffic (destination CIDR not covered)."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table("rtb-1", "vpc-1", [], subnet_ids=["subnet-a"]),
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="203.0.113.5")
    assert result.verdict == "blocked_at_routing"
    assert result.finding.confidence == "high"
    assert result.finding.remediation is not None


def test_nat_egress_walks_from_private_subnet_through_nat_to_internet() -> None:
    """Scenario: NAT egress -- private subnet routes 0.0.0.0/0 to a NAT
    gateway hosted in a public subnet, which itself routes to an IGW."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[
            _subnet("subnet-private", "vpc-1", "10.0.1.0/24"),
            _subnet("subnet-public", "vpc-1", "10.0.2.0/24"),
        ],
        route_tables=[
            _route_table(
                "rtb-private",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.0.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    ),
                    Route(
                        destination_cidr_block="0.0.0.0/0",
                        target="nat-1",
                        target_type="nat_gateway",
                        state="active",
                        origin="CreateRoute",
                    ),
                ],
                subnet_ids=["subnet-private"],
            ),
            _route_table(
                "rtb-public",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.0.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    ),
                    Route(
                        destination_cidr_block="0.0.0.0/0",
                        target="igw-1",
                        target_type="gateway",
                        state="active",
                        origin="CreateRoute",
                    ),
                ],
                subnet_ids=["subnet-public"],
            ),
        ],
        nat_gateways=[
            NatGateway(
                **_COMMON,
                nat_gateway_id="nat-1",
                vpc_id="vpc-1",
                subnet_id="subnet-public",
                state="available",
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-private", destination="203.0.113.5")
    assert result.verdict == "routable"
    assert len(result.hops) == 2
    assert result.hops[0].target_type == "nat_gateway"
    assert result.hops[1].target_type == "gateway"


def test_blackhole_route_is_deterministically_blocked() -> None:
    """Scenario: blackhole routes."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="0.0.0.0/0",
                        target="pcx-deleted",
                        target_type="vpc_peering_connection",
                        state="blackhole",
                        origin="CreateRoute",
                    ),
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="203.0.113.5")
    assert result.verdict == "blocked_at_routing"
    assert result.finding.confidence == "high"
    assert "blackhole" in result.finding.summary.lower()


def test_unknown_target_type_is_indeterminate_not_silently_allowed_or_blocked() -> None:
    """Scenario: unknown target types."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="192.168.0.0/16",
                        target="vgw-1",
                        target_type="virtual_private_gateway",
                        state="active",
                        origin="EnableVgwRoutePropagation",
                        is_propagated=True,
                    ),
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="192.168.1.5")
    assert result.verdict == "unresolved_target"
    assert result.finding.confidence == "indeterminate"
    assert result.finding.limitations


def test_peering_without_return_route_leaves_analyzed_scope() -> None:
    """Scenario: peering without return route -- the peer VPC isn't in
    the collected snapshot at all, so resolution cannot claim reachability
    either way."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.9.0.0/16",
                        target="pcx-1",
                        target_type="vpc_peering_connection",
                        state="active",
                        origin="CreateRoute",
                    ),
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="10.9.0.5")
    assert result.verdict == "left_analyzed_scope"
    assert result.finding.confidence == "indeterminate"


def test_unresolvable_source_is_indeterminate() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1", account_id="123456789012", collected_at="2026-08-27T00:00:00Z"
    )
    result = resolve_path(
        snapshot, source_subnet_id="subnet-does-not-exist", destination="10.0.0.1"
    )
    assert result.verdict == "indeterminate"
    assert result.finding.confidence == "indeterminate"
    assert result.finding.limitations


def test_invalid_destination_is_indeterminate() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="not-an-ip")
    assert result.verdict == "indeterminate"


def test_finding_freshness_matches_snapshot_collected_at() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-20T12:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[_route_table("rtb-1", "vpc-1", [], subnet_ids=["subnet-a"])],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="1.2.3.4")
    assert result.finding.freshness == "2026-08-20T12:00:00Z"


def test_source_resolved_by_ip_within_vpc() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[
            _subnet("subnet-a", "vpc-1", "10.0.1.0/24"),
            _subnet("subnet-b", "vpc-1", "10.0.2.0/24"),
        ],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.0.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    )
                ],
                subnet_ids=["subnet-a", "subnet-b"],
            )
        ],
    )
    result = resolve_path(snapshot, source_ip="10.0.1.5", vpc_id="vpc-1", destination="10.0.2.5")
    assert result.verdict == "routable"
    assert result.hops[0].location_id == "subnet-a"


def test_source_ip_not_in_any_subnet_is_indeterminate() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
    )
    result = resolve_path(snapshot, source_ip="192.168.5.5", vpc_id="vpc-1", destination="10.0.1.5")
    assert result.verdict == "indeterminate"


def test_gateway_endpoint_route_via_resolved_prefix_list() -> None:
    """A Gateway VPC endpoint route (destination_prefix_list_id, target
    type vpc_endpoint) resolves cleanly when the prefix list's entries
    are present in the snapshot."""
    pl = ManagedPrefixList(
        **_COMMON,
        prefix_list_id="pl-1",
        prefix_list_name="com.amazonaws.us-east-1.s3",
        entries=[ManagedPrefixListEntry(cidr="52.216.0.0/15")],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        managed_prefix_lists=[pl],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_prefix_list_id="pl-1",
                        target="vpce-1",
                        target_type="vpc_endpoint",
                        state="active",
                        origin="CreateRoute",
                    )
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="52.216.1.1")
    assert result.verdict == "routable"
    assert result.finding.confidence == "high"


def test_prefix_list_route_unresolved_downgrades_confidence() -> None:
    """The prefix list is referenced by a route but not included in the
    snapshot (entries not fetched) -- resolution must not silently ignore
    this; it downgrades confidence and records a limitation."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.0.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    ),
                    Route(
                        destination_prefix_list_id="pl-1",
                        target="vpce-1",
                        target_type="vpc_endpoint",
                        state="active",
                        origin="CreateRoute",
                    ),
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="10.0.2.5")
    assert result.verdict == "routable"
    assert result.finding.confidence == "medium"
    assert result.finding.limitations


def test_static_route_wins_tie_over_propagated_route() -> None:
    """Same prefix length, one static one propagated -- AWS's documented
    precedence is static wins."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="192.168.0.0/16",
                        target="igw-static",
                        target_type="gateway",
                        state="active",
                        origin="CreateRoute",
                        is_propagated=False,
                    ),
                    Route(
                        destination_cidr_block="192.168.0.0/16",
                        target="tgw-propagated",
                        target_type="transit_gateway",
                        state="active",
                        origin="EnableVgwRoutePropagation",
                        is_propagated=True,
                    ),
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="192.168.1.1")
    assert result.hops[0].matched_route is not None
    assert result.hops[0].matched_route.target == "igw-static"


def test_peering_resolves_fully_when_peer_vpc_in_snapshot() -> None:
    """When the peer VPC's own subnets/route tables are included in the
    snapshot, resolution continues into it rather than stopping at
    left_analyzed_scope."""
    pcx = VpcPeeringConnection(
        **_COMMON,
        vpc_peering_connection_id="pcx-1",
        status_code="active",
        requester=VpcPeeringPeer(vpc_id="vpc-1", cidr_blocks=["10.0.0.0/16"]),
        accepter=VpcPeeringPeer(vpc_id="vpc-2", cidr_blocks=["10.9.0.0/16"]),
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16"), _vpc("vpc-2", "10.9.0.0/16")],
        subnets=[
            _subnet("subnet-a", "vpc-1", "10.0.1.0/24"),
            _subnet("subnet-c", "vpc-2", "10.9.1.0/24"),
        ],
        vpc_peering_connections=[pcx],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.9.0.0/16",
                        target="pcx-1",
                        target_type="vpc_peering_connection",
                        state="active",
                        origin="CreateRoute",
                    )
                ],
                subnet_ids=["subnet-a"],
            ),
            _route_table(
                "rtb-2",
                "vpc-2",
                [
                    Route(
                        destination_cidr_block="10.9.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    )
                ],
                subnet_ids=["subnet-c"],
            ),
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="10.9.1.5")
    assert result.verdict == "routable"
    assert len(result.hops) == 2
    assert result.hops[0].target_type == "vpc_peering_connection"
    assert result.hops[1].vpc_id == "vpc-2"


def test_transit_gateway_resolves_to_peer_vpc_in_snapshot() -> None:
    """Scenario: TGW propagation gaps' opposite case -- a fully-working
    TGW hop resolves into a peer VPC already collected in the snapshot."""
    tgw_route = TransitGatewayRoute(
        destination_cidr_block="10.9.0.0/16",
        route_type="static",
        state="active",
        attachments=[
            TransitGatewayRouteAttachment(
                transit_gateway_attachment_id="tgw-attach-2",
                resource_type="vpc",
                resource_id="vpc-2",
            )
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16"), _vpc("vpc-2", "10.9.0.0/16")],
        subnets=[
            _subnet("subnet-a", "vpc-1", "10.0.1.0/24"),
            _subnet("subnet-c", "vpc-2", "10.9.1.0/24"),
        ],
        transit_gateway_routes=[tgw_route],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.9.0.0/16",
                        target="tgw-1",
                        target_type="transit_gateway",
                        state="active",
                        origin="CreateRoute",
                    )
                ],
                subnet_ids=["subnet-a"],
            ),
            _route_table(
                "rtb-2",
                "vpc-2",
                [
                    Route(
                        destination_cidr_block="10.9.0.0/16",
                        target="local",
                        target_type="local",
                        state="active",
                        origin="CreateRouteTable",
                    )
                ],
                subnet_ids=["subnet-c"],
            ),
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="10.9.1.5")
    assert result.verdict == "routable"
    assert result.hops[0].target_type == "transit_gateway"
    assert result.hops[1].vpc_id == "vpc-2"


def test_transit_gateway_with_no_matching_route_leaves_scope() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_cidr_block="10.9.0.0/16",
                        target="tgw-1",
                        target_type="transit_gateway",
                        state="active",
                        origin="CreateRoute",
                    )
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="10.9.1.5")
    assert result.verdict == "left_analyzed_scope"


def test_ipv6_egress_via_egress_only_internet_gateway() -> None:
    """Scenario: IPv6 egress -- a subnet with an IPv6 default route to an
    egress-only internet gateway (outbound-only, no inbound)."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[
            _route_table(
                "rtb-1",
                "vpc-1",
                [
                    Route(
                        destination_ipv6_cidr_block="::/0",
                        target="eigw-1",
                        target_type="egress_only_internet_gateway",
                        state="active",
                        origin="CreateRoute",
                    )
                ],
                subnet_ids=["subnet-a"],
            )
        ],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="2001:db8::1")
    assert result.verdict == "routable"
    assert result.hops[0].target_type == "egress_only_internet_gateway"


def test_ipv6_no_matching_route_is_blocked() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16")],
        subnets=[_subnet("subnet-a", "vpc-1", "10.0.1.0/24")],
        route_tables=[_route_table("rtb-1", "vpc-1", [], subnet_ids=["subnet-a"])],
    )
    result = resolve_path(snapshot, source_subnet_id="subnet-a", destination="2001:db8::1")
    assert result.verdict == "blocked_at_routing"


def test_neither_source_specifier_given_is_indeterminate() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1", account_id="123456789012", collected_at="2026-08-27T00:00:00Z"
    )
    result = resolve_path(snapshot, destination="10.0.0.1")
    assert result.verdict == "indeterminate"
