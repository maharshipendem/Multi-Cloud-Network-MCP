"""``gcp_get_hybrid_topology`` graph assembly -- joins every resource
family in a ``HybridNetworkSnapshot`` into one typed node/edge graph:
networks, subnetworks, Cloud Routers, VPN gateways/tunnels, Interconnect
attachments, and NCC hubs/spokes. Pure function of an already-collected
snapshot -- this module never talks to GCP directly."""

from __future__ import annotations

from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from gcp_network_mcp.models.common import CollectionWarning
from gcp_network_mcp.models.topology import HybridTopology, TopologyEdge, TopologyNode


def build_hybrid_topology(snapshot: HybridNetworkSnapshot) -> HybridTopology:
    nodes: dict[str, TopologyNode] = {}
    edges: list[TopologyEdge] = []
    warnings = list(snapshot.warnings)

    def add_node(node: TopologyNode) -> None:
        nodes.setdefault(node.node_id, node)

    def node_exists(node_id: str) -> bool:
        return node_id in nodes

    def flag_missing(resource_type: str, referrer: str, target: str) -> None:
        warnings.append(
            CollectionWarning(
                resource_type=resource_type,
                code="OUT_OF_SCOPE_TARGET",
                message=f"{referrer} references {target}, which was not found in this snapshot.",
                project_id=snapshot.project_id,
            )
        )

    for network in snapshot.networks:
        node_id = network.self_link or network.name
        add_node(
            TopologyNode(
                node_id=node_id,
                node_type="network",
                label=network.name,
                project_id=snapshot.project_id,
            )
        )

    for subnetwork in snapshot.subnetworks:
        node_id = subnetwork.self_link or f"{snapshot.project_id}/{subnetwork.name}"
        add_node(
            TopologyNode(
                node_id=node_id,
                node_type="subnetwork",
                label=subnetwork.name,
                project_id=snapshot.project_id,
                region=subnetwork.region,
            )
        )
        edges.append(
            TopologyEdge(
                source_id=node_id,
                target_id=subnetwork.network_self_link,
                relationship="belongs_to_network",
                evidence=f"subnetwork {subnetwork.name}.network={subnetwork.network_self_link}",
            )
        )
        if not node_exists(subnetwork.network_self_link):
            flag_missing("network", f"Subnetwork {subnetwork.name}", subnetwork.network_self_link)

    for router in snapshot.routers:
        node_id = router.self_link or f"{snapshot.project_id}/{router.name}"
        add_node(
            TopologyNode(
                node_id=node_id,
                node_type="router",
                label=router.name,
                project_id=snapshot.project_id,
                region=router.region,
            )
        )
        edges.append(
            TopologyEdge(
                source_id=node_id,
                target_id=router.network_self_link,
                relationship="attached_to_network",
                evidence=f"router {router.name}.network={router.network_self_link}",
            )
        )
        if not node_exists(router.network_self_link):
            flag_missing("network", f"Router {router.name}", router.network_self_link)

    for gateway in snapshot.vpn_gateways:
        node_id = gateway.self_link or f"{snapshot.project_id}/{gateway.name}"
        add_node(
            TopologyNode(
                node_id=node_id,
                node_type="vpn_gateway",
                label=gateway.name,
                project_id=snapshot.project_id,
                region=gateway.region,
            )
        )
        if gateway.network_self_link:
            edges.append(
                TopologyEdge(
                    source_id=node_id,
                    target_id=gateway.network_self_link,
                    relationship="attached_to_network",
                    evidence=f"vpn_gateway {gateway.name}.network={gateway.network_self_link}",
                )
            )
            if not node_exists(gateway.network_self_link):
                flag_missing("network", f"VPN gateway {gateway.name}", gateway.network_self_link)

    for tunnel in snapshot.vpn_tunnels:
        node_id = tunnel.self_link or f"{snapshot.project_id}/{tunnel.name}"
        add_node(
            TopologyNode(
                node_id=node_id,
                node_type="vpn_tunnel",
                label=tunnel.name,
                project_id=snapshot.project_id,
                region=tunnel.region,
            )
        )
        if tunnel.vpn_gateway_self_link:
            edges.append(
                TopologyEdge(
                    source_id=node_id,
                    target_id=tunnel.vpn_gateway_self_link,
                    relationship="terminates_on_gateway",
                    evidence=f"vpn_tunnel {tunnel.name}.vpn_gateway={tunnel.vpn_gateway_self_link}",
                )
            )
            if not node_exists(tunnel.vpn_gateway_self_link):
                flag_missing(
                    "vpn_gateway", f"VPN tunnel {tunnel.name}", tunnel.vpn_gateway_self_link
                )

    for attachment in snapshot.interconnect_attachments:
        node_id = attachment.self_link or f"{snapshot.project_id}/{attachment.name}"
        add_node(
            TopologyNode(
                node_id=node_id,
                node_type="interconnect_attachment",
                label=attachment.name,
                project_id=snapshot.project_id,
                region=attachment.region,
            )
        )
        if attachment.interconnect_self_link:
            edges.append(
                TopologyEdge(
                    source_id=node_id,
                    target_id=attachment.interconnect_self_link,
                    relationship="attached_to_interconnect",
                    evidence=(
                        f"interconnect_attachment {attachment.name}.interconnect="
                        f"{attachment.interconnect_self_link}"
                    ),
                )
            )
            if not node_exists(attachment.interconnect_self_link):
                flag_missing(
                    "interconnect",
                    f"Interconnect attachment {attachment.name}",
                    attachment.interconnect_self_link,
                )
        if attachment.router_self_link:
            edges.append(
                TopologyEdge(
                    source_id=node_id,
                    target_id=attachment.router_self_link,
                    relationship="attached_to_router",
                    evidence=(
                        f"interconnect_attachment {attachment.name}.router="
                        f"{attachment.router_self_link}"
                    ),
                )
            )
            if not node_exists(attachment.router_self_link):
                flag_missing(
                    "router",
                    f"Interconnect attachment {attachment.name}",
                    attachment.router_self_link,
                )

    for interconnect in snapshot.interconnects:
        node_id = interconnect.self_link or f"{snapshot.project_id}/{interconnect.name}"
        add_node(
            TopologyNode(
                node_id=node_id,
                node_type="interconnect",
                label=interconnect.name,
                project_id=snapshot.project_id,
            )
        )

    for hub in snapshot.ncc_hubs:
        add_node(
            TopologyNode(
                node_id=hub.name, node_type="ncc_hub", label=hub.name, project_id=hub.project_id
            )
        )

    for spoke in snapshot.ncc_spokes:
        add_node(
            TopologyNode(
                node_id=spoke.name,
                node_type="ncc_spoke",
                label=spoke.name,
                project_id=spoke.project_id,
                region=spoke.region,
            )
        )
        edges.append(
            TopologyEdge(
                source_id=spoke.name,
                target_id=spoke.hub,
                relationship="attached_to_hub",
                evidence=f"spoke {spoke.name}.hub={spoke.hub}",
            )
        )
        if not node_exists(spoke.hub):
            flag_missing("ncc_hub", f"NCC spoke {spoke.name}", spoke.hub)
        for resource_uri in spoke.linked_resource_uris:
            edges.append(
                TopologyEdge(
                    source_id=spoke.name,
                    target_id=resource_uri,
                    relationship=f"links_{spoke.spoke_type.lower()}",
                    evidence=f"spoke {spoke.name} linked resource={resource_uri}",
                )
            )

    for peering in snapshot.peerings:
        edges.append(
            TopologyEdge(
                source_id=peering.owning_network_self_link,
                target_id=peering.network,
                relationship="peered_with",
                evidence=f"peering {peering.name} state={peering.state}",
            )
        )
        if not node_exists(peering.network):
            add_node(
                TopologyNode(
                    node_id=peering.network, node_type="external_network", label=peering.network
                )
            )
            flag_missing("network", f"Peering {peering.name}", peering.network)

    edges.sort(key=lambda e: (e.source_id, e.target_id, e.relationship))
    sorted_nodes = sorted(nodes.values(), key=lambda n: (n.node_type, n.node_id))
    completeness = "partial" if warnings else "complete"

    return HybridTopology(
        project_id=snapshot.project_id,
        observed_at=snapshot.observed_at,
        completeness=completeness,
        nodes=sorted_nodes,
        edges=edges,
        warnings=warnings,
    )


__all__ = ["build_hybrid_topology"]
