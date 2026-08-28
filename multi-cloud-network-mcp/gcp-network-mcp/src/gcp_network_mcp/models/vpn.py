"""Normalized models for HA/Classic Cloud VPN: gateways, tunnels,
external VPN gateways, and operational status.

``VpnTunnel``'s underlying SDK type carries two flattened secret-shaped
fields (``shared_secret``, ``shared_secret_hash`` -- the IKE pre-shared
key and its hash) that no normalizer in ``gcp/vpn.py`` ever reads. This
is redaction *by omission*, the same pattern the Azure sibling's VPN
pre-shared-key handling established: a field that is never read cannot
leak regardless of what the raw SDK response contains. ``VpnTunnel`` is
stamped ``redacted: bool = True`` so a client can tell the record is
intentionally incomplete rather than assume it saw everything.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class VpnGatewayInterface(BaseModel):
    id: int | None = None
    ip_address: str | None = None
    interconnect_attachment: str | None = None


class VpnGateway(GcpResource):
    """Normalized entry from ``VpnGatewaysClient.list``/``aggregated_list``/``get``.
    An HA VPN gateway (a Classic VPN target uses ``TargetVpnGateway``,
    out of this milestone's scope -- HA VPN is GCP's current, recommended
    VPN gateway type)."""

    network_self_link: str
    stack_type: str | None = None
    gateway_ip_version: str | None = None
    interfaces: list[VpnGatewayInterface] = Field(default_factory=list)


class VpnGatewayConnectionTunnel(BaseModel):
    tunnel_url: str | None = None
    local_gateway_interface: int | None = None
    peer_gateway_interface: int | None = None


class VpnGatewayConnectionStatus(BaseModel):
    """One VPN connection (a peer gateway pair) from ``VpnGatewaysClient.get_status``
    -- the read-only computed HA-redundancy view, distinct from the
    gateway's own static configuration. ``ha_requirement_state``/
    ``ha_unsatisfied_reason`` report whether this connection actually
    meets GCP's HA redundancy requirement (e.g. two active tunnels across
    both interfaces), not merely whether tunnels exist."""

    peer_external_gateway: str | None = None
    peer_gcp_gateway: str | None = None
    ha_requirement_state: str | None = None
    ha_unsatisfied_reason: str | None = None
    tunnels: list[VpnGatewayConnectionTunnel] = Field(default_factory=list)


class VpnGatewayStatus(BaseModel):
    vpn_gateway_self_link: str
    connections: list[VpnGatewayConnectionStatus] = Field(default_factory=list)
    observed_at: str
    source_api: str = "VpnGatewaysClient.get_status"


class VpnTunnel(GcpResource):
    """Normalized entry from ``VpnTunnelsClient.list``/``aggregated_list``/``get``.
    Never carries ``shared_secret``/``shared_secret_hash`` -- see module docstring."""

    redacted: bool = True
    vpn_gateway_self_link: str | None = None
    vpn_gateway_interface: int | None = None
    peer_ip: str | None = None
    peer_gcp_gateway: str | None = None
    peer_external_gateway: str | None = None
    peer_external_gateway_interface: int | None = None
    router_self_link: str | None = None
    ike_version: int | None = None
    status: str | None = None
    detailed_status: str | None = None
    local_traffic_selector: list[str] = Field(default_factory=list)
    remote_traffic_selector: list[str] = Field(default_factory=list)


class ExternalVpnGatewayInterface(BaseModel):
    id: int | None = None
    ip_address: str | None = None


class ExternalVpnGateway(GcpResource):
    """Normalized entry from ``ExternalVpnGatewaysClient.list``/``get``
    -- a customer's on-premises/other-cloud VPN device, as GCP sees it."""

    redundancy_type: str | None = None
    interfaces: list[ExternalVpnGatewayInterface] = Field(default_factory=list)


__all__ = [
    "ExternalVpnGateway",
    "ExternalVpnGatewayInterface",
    "VpnGateway",
    "VpnGatewayConnectionStatus",
    "VpnGatewayConnectionTunnel",
    "VpnGatewayInterface",
    "VpnGatewayStatus",
    "VpnTunnel",
]
