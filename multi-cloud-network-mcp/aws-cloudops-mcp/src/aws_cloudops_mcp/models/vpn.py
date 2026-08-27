"""Normalized models for Site-to-Site VPN resources.

SECURITY: ``ec2:DescribeVpnConnections`` returns a ``CustomerGatewayConfiguration``
field -- a vendor-specific XML/JSON blob that embeds the IKE pre-shared
key in plaintext. That field is never read into any model in this file,
and no other field that could carry a secret (a configured tunnel's
``PreSharedKey``, if AWS ever returns one) is mapped through either. This
is an intentional omission, not an attempted redaction: regex-stripping a
free-form vendor config blob cannot be *reliably* guaranteed secret-free,
so the only dependable guardrail is to never surface the field at all. See
docs/security.md#redaction-and-size-limits.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aws_cloudops_mcp.models.common import AwsResource


class VpnTunnelOptions(BaseModel):
    """Non-secret tunnel configuration. No pre-shared-key field exists here
    by design -- see module docstring."""

    tunnel_inside_cidr: str | None = None
    dpd_timeout_seconds: int | None = None
    ike_versions: list[str] = Field(default_factory=list)


class VpnTunnel(BaseModel):
    """A single tunnel's operational telemetry (from ``VgwTelemetry``),
    kept separate from ``VpnTunnelOptions`` configuration state."""

    outside_ip_address: str | None = None
    status: str | None = None  # "UP" | "DOWN"
    status_message: str | None = None
    last_status_change: str | None = None
    accepted_route_count: int | None = None
    options: VpnTunnelOptions | None = None


class VpnStaticRoute(BaseModel):
    destination_cidr_block: str | None = None
    state: str | None = None
    source: str | None = None  # "Static"


class VpnConnectionOptions(BaseModel):
    static_routes_only: bool | None = None
    tunnel_inside_ip_version: str | None = None
    enable_acceleration: bool | None = None
    local_ipv4_network_cidr: str | None = None
    remote_ipv4_network_cidr: str | None = None


class VpnConnection(AwsResource):
    """Normalized entry from ec2:DescribeVpnConnections.

    ``redacted`` is always ``True`` on this model -- AWS's raw response
    for this resource type carries the secret-bearing
    ``CustomerGatewayConfiguration`` field, which this normalizer never
    reads; the flag documents that omission explicitly rather than
    leaving a reader to assume the record is a complete passthrough.
    """

    vpn_connection_id: str
    state: str
    vpn_type: str | None = None
    category: str | None = None
    customer_gateway_id: str | None = None
    vpn_gateway_id: str | None = None
    transit_gateway_id: str | None = None
    gateway_association_state: str | None = None
    options: VpnConnectionOptions = Field(default_factory=VpnConnectionOptions)
    static_routes: list[VpnStaticRoute] = Field(default_factory=list)
    tunnels: list[VpnTunnel] = Field(default_factory=list)


class CustomerGateway(AwsResource):
    """Normalized entry from ec2:DescribeCustomerGateways (the on-premises
    side of a Site-to-Site VPN)."""

    customer_gateway_id: str
    state: str
    gateway_type: str | None = None
    ip_address: str | None = None
    bgp_asn: str | None = None
    device_name: str | None = None


class VpnGatewayVpcAttachment(BaseModel):
    vpc_id: str | None = None
    state: str | None = None


class VpnGateway(AwsResource):
    """Normalized entry from ec2:DescribeVpnGateways (a virtual private
    gateway -- the AWS side of a Site-to-Site VPN, distinct from a
    Transit Gateway)."""

    vpn_gateway_id: str
    state: str
    gateway_type: str | None = None
    amazon_side_asn: int | None = None
    vpc_attachments: list[VpnGatewayVpcAttachment] = Field(default_factory=list)


__all__ = [
    "CustomerGateway",
    "VpnConnection",
    "VpnConnectionOptions",
    "VpnGateway",
    "VpnGatewayVpcAttachment",
    "VpnStaticRoute",
    "VpnTunnel",
    "VpnTunnelOptions",
]
