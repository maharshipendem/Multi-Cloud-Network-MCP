"""AWS service layer: Site-to-Site VPN connections, customer gateways, and VPN gateways.

SECURITY: see ``models/vpn.py``'s module docstring. This module never
reads ``CustomerGatewayConfiguration`` from a raw ``describe_vpn_connections``
response -- the dict key is never even accessed, so there is no code path
by which it could leak into a normalized record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.vpn import (
    CustomerGateway,
    VpnConnection,
    VpnConnectionOptions,
    VpnGateway,
    VpnGatewayVpcAttachment,
    VpnStaticRoute,
    VpnTunnel,
    VpnTunnelOptions,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _normalize_tunnel(raw: dict[str, Any]) -> VpnTunnel:
    tunnel_options_raw = raw.get("TunnelOptions") or {}
    return VpnTunnel(
        outside_ip_address=raw.get("OutsideIpAddress"),
        status=raw.get("Status"),
        status_message=raw.get("StatusMessage"),
        last_status_change=str(raw.get("LastStatusChange"))
        if raw.get("LastStatusChange")
        else None,
        accepted_route_count=raw.get("AcceptedRouteCount"),
        options=VpnTunnelOptions(
            tunnel_inside_cidr=tunnel_options_raw.get("TunnelInsideCidr"),
            dpd_timeout_seconds=tunnel_options_raw.get("DpdTimeoutSeconds"),
            ike_versions=[
                v.get("Value", "") for v in tunnel_options_raw.get("IkeVersions", []) if v
            ],
        )
        if tunnel_options_raw
        else None,
    )


def list_vpn_connections(
    client_factory: ClientFactory,
    *,
    region: str,
    vpn_connection_ids: list[str] | None = None,
    transit_gateway_id: str | None = None,
) -> list[VpnConnection]:
    """Call ec2:DescribeVpnConnections and return the normalized list.

    Not paginated by AWS (returns everything in one call); still routed
    through the standard client/guardrail path.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if vpn_connection_ids:
        kwargs["VpnConnectionIds"] = vpn_connection_ids
    if transit_gateway_id:
        kwargs["Filters"] = [{"Name": "transit-gateway-id", "Values": [transit_gateway_id]}]

    response = call_readonly(client, "describe_vpn_connections", **kwargs)
    result = []
    for raw in response.get("VpnConnections", []):
        opts = raw.get("Options") or {}
        result.append(
            VpnConnection(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                source_api="ec2:DescribeVpnConnections",
                redacted=True,
                vpn_connection_id=raw["VpnConnectionId"],
                state=raw.get("State", ""),
                vpn_type=raw.get("Type"),
                category=raw.get("Category"),
                customer_gateway_id=raw.get("CustomerGatewayId"),
                vpn_gateway_id=raw.get("VpnGatewayId"),
                transit_gateway_id=raw.get("TransitGatewayId"),
                gateway_association_state=raw.get("GatewayAssociationState"),
                options=VpnConnectionOptions(
                    static_routes_only=opts.get("StaticRoutesOnly"),
                    tunnel_inside_ip_version=opts.get("TunnelInsideIpVersion"),
                    enable_acceleration=opts.get("EnableAcceleration"),
                    local_ipv4_network_cidr=opts.get("LocalIpv4NetworkCidr"),
                    remote_ipv4_network_cidr=opts.get("RemoteIpv4NetworkCidr"),
                ),
                static_routes=[
                    VpnStaticRoute(
                        destination_cidr_block=r.get("DestinationCidrBlock"),
                        state=r.get("State"),
                        source=r.get("Source"),
                    )
                    for r in raw.get("Routes", [])
                ],
                tunnels=[_normalize_tunnel(t) for t in raw.get("VgwTelemetry", [])],
                tags=normalize_tags(raw.get("Tags")),
            )
        )
    return result


def list_customer_gateways(
    client_factory: ClientFactory, *, region: str, customer_gateway_ids: list[str] | None = None
) -> list[CustomerGateway]:
    """Call ec2:DescribeCustomerGateways and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {"CustomerGatewayIds": customer_gateway_ids} if customer_gateway_ids else {}
    response = call_readonly(client, "describe_customer_gateways", **kwargs)
    return [
        CustomerGateway(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:DescribeCustomerGateways",
            customer_gateway_id=cgw["CustomerGatewayId"],
            state=cgw.get("State", ""),
            gateway_type=cgw.get("Type"),
            ip_address=cgw.get("IpAddress"),
            bgp_asn=cgw.get("BgpAsn"),
            device_name=cgw.get("DeviceName"),
            tags=normalize_tags(cgw.get("Tags")),
        )
        for cgw in response.get("CustomerGateways", [])
    ]


def list_vpn_gateways(
    client_factory: ClientFactory, *, region: str, vpn_gateway_ids: list[str] | None = None
) -> list[VpnGateway]:
    """Call ec2:DescribeVpnGateways and return the normalized list.

    These are virtual private gateways -- the AWS side of a classic
    Site-to-Site VPN, distinct from a Transit Gateway.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {"VpnGatewayIds": vpn_gateway_ids} if vpn_gateway_ids else {}
    response = call_readonly(client, "describe_vpn_gateways", **kwargs)
    return [
        VpnGateway(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="ec2:DescribeVpnGateways",
            vpn_gateway_id=vgw["VpnGatewayId"],
            state=vgw.get("State", ""),
            gateway_type=vgw.get("Type"),
            amazon_side_asn=vgw.get("AmazonSideAsn"),
            vpc_attachments=[
                VpnGatewayVpcAttachment(vpc_id=a.get("VpcId"), state=a.get("State"))
                for a in vgw.get("VpcAttachments", [])
            ],
            tags=normalize_tags(vgw.get("Tags")),
        )
        for vgw in response.get("VpnGateways", [])
    ]
