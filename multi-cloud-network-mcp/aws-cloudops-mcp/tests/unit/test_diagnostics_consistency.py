from __future__ import annotations

from aws_cloudops_mcp.diagnostics.consistency import (
    check_asymmetric_peering_routes,
    check_cidr_overlap,
    check_degraded_resource_states,
    check_orphaned_tgw_attachments,
)
from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot
from aws_cloudops_mcp.models.common import Route, RouteTable, Vpc
from aws_cloudops_mcp.models.network_resources import (
    NatGateway,
    VpcPeeringConnection,
    VpcPeeringPeer,
)
from aws_cloudops_mcp.models.transit_gateway import (
    TransitGatewayAttachment,
    TransitGatewayRouteTable,
    TransitGatewayRouteTableAssociation,
    TransitGatewayRouteTablePropagation,
)
from aws_cloudops_mcp.models.vpn import VpnConnection, VpnTunnel

_COMMON = {
    "account_id": "123456789012",
    "region": "us-east-1",
    "observed_at": "2026-08-27T00:00:00Z",
}


def _vpc(vpc_id: str, cidr: str) -> Vpc:
    return Vpc(**_COMMON, vpc_id=vpc_id, cidr_block=cidr, state="available", is_default=False)


def test_overlapping_vpc_cidrs_flagged() -> None:
    """Scenario: overlapping CIDRs."""
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16"), _vpc("vpc-2", "10.0.8.0/20")],
    )
    findings = check_cidr_overlap(snapshot)
    assert len(findings) == 1
    assert findings[0].confidence == "high"
    assert "vpc-1" in findings[0].affected_resources
    assert "vpc-2" in findings[0].affected_resources


def test_non_overlapping_vpc_cidrs_not_flagged() -> None:
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpcs=[_vpc("vpc-1", "10.0.0.0/16"), _vpc("vpc-2", "10.1.0.0/16")],
    )
    assert check_cidr_overlap(snapshot) == []


def test_orphaned_attachment_no_association_flagged() -> None:
    """Scenario: TGW propagation gaps (orphaned side)."""
    att = TransitGatewayAttachment(
        **_COMMON,
        transit_gateway_attachment_id="tgw-attach-1",
        transit_gateway_id="tgw-1",
        resource_type="vpc",
        resource_id="vpc-1",
        state="available",
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        transit_gateway_attachments=[att],
    )
    findings = check_orphaned_tgw_attachments(snapshot)
    assert len(findings) == 1
    assert findings[0].rule_id == "CONSIST-002"


def test_associated_but_not_propagated_attachment_flagged() -> None:
    """Scenario: TGW propagation gaps (associated, not propagated)."""
    att = TransitGatewayAttachment(
        **_COMMON,
        transit_gateway_attachment_id="tgw-attach-1",
        transit_gateway_id="tgw-1",
        resource_type="vpc",
        resource_id="vpc-1",
        state="available",
    )
    rt = TransitGatewayRouteTable(
        **_COMMON,
        transit_gateway_route_table_id="tgw-rtb-1",
        transit_gateway_id="tgw-1",
        state="available",
        associations=[
            TransitGatewayRouteTableAssociation(
                transit_gateway_attachment_id="tgw-attach-1", state="associated"
            )
        ],
        propagations=[],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        transit_gateway_attachments=[att],
        transit_gateway_route_tables=[rt],
    )
    findings = check_orphaned_tgw_attachments(snapshot)
    assert len(findings) == 1
    assert findings[0].rule_id == "CONSIST-003"


def test_fully_wired_attachment_not_flagged() -> None:
    att = TransitGatewayAttachment(
        **_COMMON,
        transit_gateway_attachment_id="tgw-attach-1",
        transit_gateway_id="tgw-1",
        resource_type="vpc",
        resource_id="vpc-1",
        state="available",
    )
    rt = TransitGatewayRouteTable(
        **_COMMON,
        transit_gateway_route_table_id="tgw-rtb-1",
        transit_gateway_id="tgw-1",
        state="available",
        associations=[
            TransitGatewayRouteTableAssociation(
                transit_gateway_attachment_id="tgw-attach-1", state="associated"
            )
        ],
        propagations=[
            TransitGatewayRouteTablePropagation(
                transit_gateway_attachment_id="tgw-attach-1", state="enabled"
            )
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        transit_gateway_attachments=[att],
        transit_gateway_route_tables=[rt],
    )
    assert check_orphaned_tgw_attachments(snapshot) == []


def test_peering_without_return_route_flagged() -> None:
    """Scenario: peering without return route."""
    pcx = VpcPeeringConnection(
        **_COMMON,
        vpc_peering_connection_id="pcx-1",
        status_code="active",
        requester=VpcPeeringPeer(vpc_id="vpc-1", cidr_blocks=["10.0.0.0/16"]),
        accepter=VpcPeeringPeer(vpc_id="vpc-2", cidr_blocks=["10.9.0.0/16"]),
    )
    rt = RouteTable(
        **_COMMON,
        route_table_id="rtb-1",
        vpc_id="vpc-1",
        routes=[
            Route(
                destination_cidr_block="10.9.0.0/16",
                target="pcx-1",
                target_type="vpc_peering_connection",
                state="active",
                origin="CreateRoute",
            ),
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpc_peering_connections=[pcx],
        route_tables=[rt],
    )
    findings = check_asymmetric_peering_routes(snapshot)
    assert len(findings) == 1
    assert "vpc-2 has no return route" in findings[0].summary


def test_peering_with_symmetric_routes_not_flagged() -> None:
    pcx = VpcPeeringConnection(
        **_COMMON,
        vpc_peering_connection_id="pcx-1",
        status_code="active",
        requester=VpcPeeringPeer(vpc_id="vpc-1", cidr_blocks=["10.0.0.0/16"]),
        accepter=VpcPeeringPeer(vpc_id="vpc-2", cidr_blocks=["10.9.0.0/16"]),
    )
    rt1 = RouteTable(
        **_COMMON,
        route_table_id="rtb-1",
        vpc_id="vpc-1",
        routes=[
            Route(
                destination_cidr_block="10.9.0.0/16",
                target="pcx-1",
                target_type="vpc_peering_connection",
                state="active",
                origin="CreateRoute",
            )
        ],
    )
    rt2 = RouteTable(
        **_COMMON,
        route_table_id="rtb-2",
        vpc_id="vpc-2",
        routes=[
            Route(
                destination_cidr_block="10.0.0.0/16",
                target="pcx-1",
                target_type="vpc_peering_connection",
                state="active",
                origin="CreateRoute",
            )
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpc_peering_connections=[pcx],
        route_tables=[rt1, rt2],
    )
    assert check_asymmetric_peering_routes(snapshot) == []


def test_failed_nat_gateway_flagged() -> None:
    nat = NatGateway(
        **_COMMON,
        nat_gateway_id="nat-1",
        vpc_id="vpc-1",
        subnet_id="subnet-a",
        state="failed",
        failure_message="Insufficient capacity",
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        nat_gateways=[nat],
    )
    findings = check_degraded_resource_states(snapshot)
    assert len(findings) == 1
    assert "Insufficient capacity" in findings[0].summary


def test_healthy_nat_gateway_not_flagged() -> None:
    nat = NatGateway(
        **_COMMON, nat_gateway_id="nat-1", vpc_id="vpc-1", subnet_id="subnet-a", state="available"
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        nat_gateways=[nat],
    )
    assert check_degraded_resource_states(snapshot) == []


def test_down_vpn_tunnel_flagged() -> None:
    vpn = VpnConnection(
        **_COMMON,
        vpn_connection_id="vpn-1",
        state="available",
        tunnels=[
            VpnTunnel(
                outside_ip_address="203.0.113.9",
                status="DOWN",
                status_message="IKE negotiation failed",
            )
        ],
    )
    snapshot = NetworkSnapshot(
        region="us-east-1",
        account_id="123456789012",
        collected_at="2026-08-27T00:00:00Z",
        vpn_connections=[vpn],
    )
    findings = check_degraded_resource_states(snapshot)
    assert len(findings) == 1
    assert "IKE negotiation failed" in findings[0].summary
