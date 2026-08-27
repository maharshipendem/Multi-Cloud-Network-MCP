"""AWS service layer: ``aws_get_hybrid_topology`` graph assembly.

Anchored on a single Transit Gateway -- the natural hub joining VPC, VPN,
Direct Connect, and (via peering) Cloud WAN attachments. DNS resources are
joined at the VPC level for every VPC found among the TGW's attachments
(hosted zones whose ``linked_vpc_ids`` include that VPC; Resolver
endpoints whose ``host_vpc_id`` matches). Classic Network Manager
(sites/devices/links/connections) is intentionally not joined here -- the
milestone's topology requirement names "VPC, TGW, VPN, DX, Cloud WAN, and
DNS" specifically; sites/devices/links have their own granular tools.

Like ``aws.topology`` (Milestone 2), raw collection stays fully separate
from graph assembly: this module never calls boto3 directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.collection import track_calls
from aws_cloudops_mcp.aws.dns import list_hosted_zones, list_resolver_endpoints
from aws_cloudops_mcp.aws.transit_gateway import (
    list_transit_gateway_attachments,
    list_transit_gateways,
)
from aws_cloudops_mcp.aws.vpn import list_customer_gateways, list_vpn_connections
from aws_cloudops_mcp.exceptions import ResourceNotFoundError
from aws_cloudops_mcp.models.common import CollectionWarning
from aws_cloudops_mcp.models.hybrid_topology import HybridTopology, TopologyEdge, TopologyNode

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

# TGW attachment resource types this milestone can resolve into their own
# node (beyond the attachment node itself). Anything else (a "connect" or
# "tgw-peering" attachment to a resource this call doesn't further
# resolve) still gets an attachment node -- just no deeper resolution.
_RESOLVABLE_ATTACHMENT_TYPES = {"vpc", "vpn", "direct-connect-gateway"}


def get_hybrid_topology(
    client_factory: ClientFactory, *, region: str, transit_gateway_id: str
) -> HybridTopology:
    """Assemble the joined hybrid-connectivity graph for one Transit Gateway."""
    warnings: list[CollectionWarning] = []
    nodes: dict[str, TopologyNode] = {}
    edges: list[TopologyEdge] = []

    def add_node(node: TopologyNode) -> None:
        nodes.setdefault(node.node_id, node)

    with track_calls() as counter:
        tgws = list_transit_gateways(
            client_factory, region=region, transit_gateway_ids=[transit_gateway_id]
        )
        if not tgws:
            raise ResourceNotFoundError(
                f"Transit Gateway '{transit_gateway_id}' was not found in region '{region}'."
            )
        tgw = tgws[0]
        account_id = tgw.account_id

        add_node(
            TopologyNode(
                node_id=tgw.transit_gateway_id,
                node_type="transit_gateway",
                label=tgw.tags.get("Name", tgw.transit_gateway_id),
                region=region,
                tags=tgw.tags,
            )
        )

        attachments = list_transit_gateway_attachments(
            client_factory, region=region, transit_gateway_id=transit_gateway_id
        )
        attached_vpc_ids: set[str] = set()

        for att in attachments:
            att_resource_label = att.resource_id or att.transit_gateway_attachment_id
            att_label = f"{att.resource_type}:{att_resource_label}"
            add_node(
                TopologyNode(
                    node_id=att.transit_gateway_attachment_id,
                    node_type="transit_gateway_attachment",
                    label=att_label,
                    region=region,
                    tags=att.tags,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=tgw.transit_gateway_id,
                    target_id=att.transit_gateway_attachment_id,
                    relationship="has_attachment",
                    evidence=(
                        f"attachment {att.transit_gateway_attachment_id} "
                        f"TransitGatewayId={tgw.transit_gateway_id}"
                    ),
                )
            )

            if att.resource_owner_id and att.resource_owner_id != account_id:
                warnings.append(
                    CollectionWarning(
                        resource_type="transit_gateway_attachment",
                        code="CROSS_ACCOUNT_ATTACHMENT",
                        message=(
                            f"Attachment {att.transit_gateway_attachment_id} is owned by "
                            f"account {att.resource_owner_id}, not the caller's account "
                            f"{account_id} -- only attachment-level metadata is visible."
                        ),
                    )
                )

            if att.resource_type not in _RESOLVABLE_ATTACHMENT_TYPES or not att.resource_id:
                if att.resource_type not in _RESOLVABLE_ATTACHMENT_TYPES:
                    warnings.append(
                        CollectionWarning(
                            resource_type="transit_gateway_attachment",
                            code="OUT_OF_SCOPE_TARGET",
                            message=(
                                f"Attachment {att.transit_gateway_attachment_id} has resource "
                                f"type '{att.resource_type}', which this milestone does not "
                                "resolve into its own node beyond the attachment itself."
                            ),
                        )
                    )
                continue

            if att.resource_type == "vpc":
                attached_vpc_ids.add(att.resource_id)
                add_node(
                    TopologyNode(
                        node_id=att.resource_id,
                        node_type="vpc",
                        label=att.resource_id,
                        vpc_id=att.resource_id,
                        region=region,
                        tags={},
                    )
                )
                edges.append(
                    TopologyEdge(
                        source_id=att.transit_gateway_attachment_id,
                        target_id=att.resource_id,
                        relationship="attaches",
                        evidence=(
                            f"attachment {att.transit_gateway_attachment_id} ResourceId="
                            f"{att.resource_id} ResourceType=vpc"
                        ),
                    )
                )
            elif att.resource_type == "vpn":
                _join_vpn_connection(
                    client_factory,
                    region=region,
                    attachment_id=att.transit_gateway_attachment_id,
                    vpn_connection_id=att.resource_id,
                    add_node=add_node,
                    edges=edges,
                    warnings=warnings,
                )
            elif att.resource_type == "direct-connect-gateway":
                add_node(
                    TopologyNode(
                        node_id=att.resource_id,
                        node_type="direct_connect_gateway",
                        label=att.resource_id,
                        region=region,
                        tags={},
                    )
                )
                edges.append(
                    TopologyEdge(
                        source_id=att.transit_gateway_attachment_id,
                        target_id=att.resource_id,
                        relationship="attaches",
                        evidence=(
                            f"attachment {att.transit_gateway_attachment_id} ResourceId="
                            f"{att.resource_id} ResourceType=direct-connect-gateway"
                        ),
                    )
                )

        _join_dns_resources(
            client_factory,
            region=region,
            attached_vpc_ids=attached_vpc_ids,
            add_node=add_node,
            edges=edges,
        )

    edges.sort(key=lambda e: (e.source_id, e.target_id, e.relationship))
    sorted_nodes = sorted(nodes.values(), key=lambda n: (n.node_type, n.node_id))

    return HybridTopology(
        transit_gateway_id=transit_gateway_id,
        region=region,
        nodes=sorted_nodes,
        edges=edges,
        warnings=warnings,
        api_call_count=counter.count,
    )


def _join_vpn_connection(
    client_factory: ClientFactory,
    *,
    region: str,
    attachment_id: str,
    vpn_connection_id: str,
    add_node: Callable[[TopologyNode], None],
    edges: list[TopologyEdge],
    warnings: list[CollectionWarning],
) -> None:
    connections = list_vpn_connections(
        client_factory, region=region, vpn_connection_ids=[vpn_connection_id]
    )
    if not connections:
        return
    conn = connections[0]
    add_node(
        TopologyNode(
            node_id=conn.vpn_connection_id,
            node_type="vpn_connection",
            label=conn.tags.get("Name", conn.vpn_connection_id),
            region=region,
            tags=conn.tags,
        )
    )
    evidence = f"attachment {attachment_id} ResourceId={conn.vpn_connection_id} ResourceType=vpn"
    edges.append(
        TopologyEdge(
            source_id=attachment_id,
            target_id=conn.vpn_connection_id,
            relationship="attaches",
            evidence=evidence,
        )
    )

    if not conn.customer_gateway_id:
        return
    cgws = list_customer_gateways(
        client_factory, region=region, customer_gateway_ids=[conn.customer_gateway_id]
    )
    if cgws:
        cgw = cgws[0]
        add_node(
            TopologyNode(
                node_id=cgw.customer_gateway_id,
                node_type="customer_gateway",
                label=cgw.customer_gateway_id,
                region=region,
                tags=cgw.tags,
            )
        )
        terminates_evidence = (
            f"vpn connection {conn.vpn_connection_id} CustomerGatewayId={cgw.customer_gateway_id}"
        )
        edges.append(
            TopologyEdge(
                source_id=conn.vpn_connection_id,
                target_id=cgw.customer_gateway_id,
                relationship="terminates_at",
                evidence=terminates_evidence,
            )
        )
        if cgw.ip_address:
            # The customer gateway's public IP is the actual on-premises
            # network boundary -- a genuinely external, unresolvable
            # endpoint, labeled explicitly rather than left implicit.
            external_id = f"external:{cgw.ip_address}"
            add_node(
                TopologyNode(
                    node_id=external_id,
                    node_type="external_endpoint",
                    label=cgw.ip_address,
                    region=region,
                    tags={},
                )
            )
            represents_evidence = (
                f"customer gateway {cgw.customer_gateway_id} IpAddress={cgw.ip_address}"
            )
            edges.append(
                TopologyEdge(
                    source_id=cgw.customer_gateway_id,
                    target_id=external_id,
                    relationship="represents",
                    evidence=represents_evidence,
                )
            )
    else:
        warnings.append(
            CollectionWarning(
                resource_type="customer_gateway",
                code="OUT_OF_SCOPE_TARGET",
                message=(
                    f"VPN connection {conn.vpn_connection_id} references customer gateway "
                    f"{conn.customer_gateway_id}, which could not be resolved."
                ),
            )
        )


def _join_dns_resources(
    client_factory: ClientFactory,
    *,
    region: str,
    attached_vpc_ids: set[str],
    add_node: Callable[[TopologyNode], None],
    edges: list[TopologyEdge],
) -> None:
    if not attached_vpc_ids:
        return

    for zone in list_hosted_zones(client_factory, region=region):
        matched = attached_vpc_ids & set(zone.linked_vpc_ids)
        if not matched:
            continue
        add_node(
            TopologyNode(
                node_id=zone.hosted_zone_id,
                node_type="hosted_zone",
                label=zone.name,
                region=region,
                tags=zone.tags,
            )
        )
        for vpc_id in sorted(matched):
            edges.append(
                TopologyEdge(
                    source_id=vpc_id,
                    target_id=zone.hosted_zone_id,
                    relationship="resolves_for",
                    evidence=f"hosted zone {zone.hosted_zone_id} linked_vpc_ids includes {vpc_id}",
                )
            )

    for endpoint in list_resolver_endpoints(client_factory, region=region):
        if endpoint.host_vpc_id not in attached_vpc_ids:
            continue
        add_node(
            TopologyNode(
                node_id=endpoint.resolver_endpoint_id,
                node_type="resolver_endpoint",
                label=endpoint.name or endpoint.resolver_endpoint_id,
                region=region,
                tags={},
            )
        )
        hosts_evidence = (
            f"resolver endpoint {endpoint.resolver_endpoint_id} HostVPCId={endpoint.host_vpc_id}"
        )
        edges.append(
            TopologyEdge(
                source_id=endpoint.host_vpc_id,
                target_id=endpoint.resolver_endpoint_id,
                relationship="hosts",
                evidence=hosts_evidence,
            )
        )


__all__ = ["get_hybrid_topology"]
