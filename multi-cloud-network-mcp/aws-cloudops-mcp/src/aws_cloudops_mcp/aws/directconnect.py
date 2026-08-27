"""AWS service layer: Direct Connect connections, LAGs, VIFs, and gateways.

SECURITY: ``directconnect:DescribeVirtualInterfaces`` returns an ``authKey``
field (the BGP MD5 authentication key) at both the virtual interface level
and per-BGP-peer -- this module never reads that key from the raw
response, and ``models.directconnect.VirtualInterfaceBgpPeer`` has no
field that could hold it. ``customerRouterConfig`` (a generated router
config snippet that can embed the same key) is likewise never mapped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.directconnect import (
    DirectConnectConnection,
    DirectConnectGateway,
    DirectConnectGatewayAssociation,
    Lag,
    VirtualInterface,
    VirtualInterfaceBgpPeer,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _stringify(value: object) -> str | None:
    """AWS documents ``hasLogicalRedundancy`` as a string enum
    ("yes"/"no"/"unknown"); coerce defensively since some SDK mocks
    (moto) return a Python bool instead."""
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def list_direct_connect_connections(
    client_factory: ClientFactory, *, region: str, connection_id: str | None = None
) -> list[DirectConnectConnection]:
    """Call directconnect:DescribeConnections and return the normalized list.

    Hosted connections are included here: a connection this account
    received from a Direct Connect Partner appears in this same call from
    the customer's (this account's) perspective, distinguished by
    ``partner_name``/``lag_id`` on the record.
    """
    validate_region_format(region)
    client = client_factory.get_client("directconnect", region=region)
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {"connectionId": connection_id} if connection_id else {}
    response = call_readonly(client, "describe_connections", **kwargs)
    return [
        DirectConnectConnection(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="directconnect:DescribeConnections",
            connection_id=c["connectionId"],
            connection_name=c.get("connectionName"),
            connection_state=c.get("connectionState", ""),
            location=c.get("location"),
            bandwidth=c.get("bandwidth"),
            vlan=c.get("vlan"),
            partner_name=c.get("partnerName"),
            lag_id=c.get("lagId"),
            aws_device=c.get("awsDeviceV2") or c.get("awsDevice"),
            has_logical_redundancy=_stringify(c.get("hasLogicalRedundancy")),
            tags=normalize_tags(c.get("tags")),
        )
        for c in response.get("connections", [])
    ]


def list_direct_connect_lags(
    client_factory: ClientFactory, *, region: str, lag_id: str | None = None
) -> list[Lag]:
    """Call directconnect:DescribeLags and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("directconnect", region=region)
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {"lagId": lag_id} if lag_id else {}
    response = call_readonly(client, "describe_lags", **kwargs)
    return [
        Lag(
            account_id=account_id,
            region=region,
            observed_at=observed_at,
            source_api="directconnect:DescribeLags",
            lag_id=lag["lagId"],
            lag_name=lag.get("lagName"),
            lag_state=lag.get("lagState", ""),
            location=lag.get("location"),
            number_of_connections=lag.get("numberOfConnections"),
            minimum_links=lag.get("minimumLinks"),
            connections_bandwidth=lag.get("connectionsBandwidth"),
            has_logical_redundancy=_stringify(lag.get("hasLogicalRedundancy")),
            tags=normalize_tags(lag.get("tags")),
        )
        for lag in response.get("lags", [])
    ]


def list_direct_connect_virtual_interfaces(
    client_factory: ClientFactory,
    *,
    region: str,
    connection_id: str | None = None,
    virtual_interface_id: str | None = None,
) -> list[VirtualInterface]:
    """Call directconnect:DescribeVirtualInterfaces and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("directconnect", region=region)
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {}
    if connection_id:
        kwargs["connectionId"] = connection_id
    if virtual_interface_id:
        kwargs["virtualInterfaceId"] = virtual_interface_id

    response = call_readonly(client, "describe_virtual_interfaces", **kwargs)
    result = []
    for vif in response.get("virtualInterfaces", []):
        result.append(
            VirtualInterface(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                source_api="directconnect:DescribeVirtualInterfaces",
                redacted=True,
                virtual_interface_id=vif["virtualInterfaceId"],
                virtual_interface_name=vif.get("virtualInterfaceName"),
                virtual_interface_type=vif.get("virtualInterfaceType"),
                virtual_interface_state=vif.get("virtualInterfaceState", ""),
                connection_id=vif.get("connectionId"),
                direct_connect_gateway_id=vif.get("directConnectGatewayId"),
                vlan=vif.get("vlan"),
                asn=vif.get("asn"),
                amazon_address=vif.get("amazonAddress"),
                customer_address=vif.get("customerAddress"),
                address_family=vif.get("addressFamily"),
                route_filter_prefixes=[
                    p.get("cidr", "") for p in vif.get("routeFilterPrefixes", [])
                ],
                bgp_peers=[
                    VirtualInterfaceBgpPeer(
                        bgp_peer_id=p.get("bgpPeerId"),
                        asn=p.get("asn"),
                        address_family=p.get("addressFamily"),
                        bgp_peer_state=p.get("bgpPeerState"),
                        bgp_status=p.get("bgpStatus"),
                    )
                    for p in vif.get("bgpPeers", [])
                ],
                tags=normalize_tags(vif.get("tags")),
            )
        )
    return result


def list_direct_connect_gateways(
    client_factory: ClientFactory,
    *,
    region: str,
    direct_connect_gateway_id: str | None = None,
    include_associations: bool = False,
) -> list[DirectConnectGateway]:
    """Call directconnect:DescribeDirectConnectGateways and return the normalized list.

    ``include_associations`` opts into one extra
    ``DescribeDirectConnectGatewayAssociations`` call per gateway (bounded
    by ``Settings.max_fanout_calls``), since DX Gateways are a global-scope
    resource but attach to per-region VGWs/TGWs.
    """
    validate_region_format(region)
    client = client_factory.get_client("directconnect", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = (
        {"directConnectGatewayId": direct_connect_gateway_id} if direct_connect_gateway_id else {}
    )
    response = call_readonly(client, "describe_direct_connect_gateways", **kwargs)

    fanout_budget = settings.max_fanout_calls
    gateways = []
    for gw in response.get("directConnectGateways", []):
        associations = []
        if include_associations and fanout_budget > 0:
            assoc_response = call_readonly(
                client,
                "describe_direct_connect_gateway_associations",
                directConnectGatewayId=gw["directConnectGatewayId"],
            )
            associations = [
                DirectConnectGatewayAssociation(
                    association_id=a.get("associationId"),
                    direct_connect_gateway_id=a.get("directConnectGatewayId"),
                    associated_gateway_id=(a.get("associatedGateway") or {}).get("id"),
                    associated_gateway_type=(a.get("associatedGateway") or {}).get("type"),
                    association_state=a.get("associationState"),
                    allowed_prefixes=[
                        p.get("cidr", "")
                        for p in a.get("allowedPrefixesToDirectConnectGateway", [])
                    ],
                )
                for a in assoc_response.get("directConnectGatewayAssociations", [])
            ]
            fanout_budget -= 1

        gateways.append(
            DirectConnectGateway(
                account_id=account_id,
                region=region,
                scope="global",
                observed_at=observed_at,
                source_api="directconnect:DescribeDirectConnectGateways",
                direct_connect_gateway_id=gw["directConnectGatewayId"],
                direct_connect_gateway_name=gw.get("directConnectGatewayName"),
                direct_connect_gateway_state=gw.get("directConnectGatewayState", ""),
                amazon_side_asn=gw.get("amazonSideAsn"),
                owner_account=gw.get("ownerAccount"),
                associations=associations,
            )
        )
    return gateways
