"""``azure_get_hybrid_topology``'s graph-assembly logic: joins a whole
resource group's ``HybridNetworkSnapshot`` into one typed node/edge graph
spanning VNets, Virtual Hubs, VPN gateways/connections, and ExpressRoute
circuits/gateways/connections.

A pure function of ``HybridNetworkSnapshot`` -- no Azure SDK calls happen
here, mirroring ``arm.topology.get_vnet_topology``'s collection/assembly
separation, just at resource-group rather than single-VNet scope.
"""

from __future__ import annotations

from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.common import CollectionWarning, normalize_resource_id
from azure_network_mcp.models.topology import HybridTopology, TopologyEdge, TopologyNode


def build_hybrid_topology(snapshot: HybridNetworkSnapshot) -> HybridTopology:
    nodes: dict[str, TopologyNode] = {}
    edges: list[TopologyEdge] = []
    warnings: list[CollectionWarning] = list(snapshot.warnings)

    def add_node(node: TopologyNode) -> None:
        nodes.setdefault(normalize_resource_id(node.node_id), node)

    def node_exists(resource_id: str) -> bool:
        return normalize_resource_id(resource_id) in nodes

    for vnet in snapshot.virtual_networks:
        add_node(
            TopologyNode(
                node_id=vnet.resource_id,
                node_type="virtual_network",
                label=vnet.name,
                resource_group=snapshot.resource_group,
                tags=vnet.tags,
            )
        )

    # Subnets are added as nodes too (unlike the rest of this graph, which
    # treats a VNet as one opaque node) specifically so a Private Endpoint
    # can be joined to the subnet it actually lives in -- the association
    # that matters for reasoning about Private DNS zone resolution.
    for subnet in snapshot.subnets:
        add_node(
            TopologyNode(
                node_id=subnet.resource_id,
                node_type="subnet",
                label=subnet.name,
                virtual_network_name=subnet.virtual_network_name,
                resource_group=snapshot.resource_group,
            )
        )
        if subnet.virtual_network_name:
            vnet_match = next(
                (v for v in snapshot.virtual_networks if v.name == subnet.virtual_network_name),
                None,
            )
            if vnet_match is not None:
                edges.append(
                    TopologyEdge(
                        source_id=vnet_match.resource_id,
                        target_id=subnet.resource_id,
                        relationship="contains",
                        evidence=(
                            f"subnet {subnet.name} is listed under VNet "
                            f"{subnet.virtual_network_name}"
                        ),
                    )
                )

    for hub in snapshot.virtual_hubs:
        add_node(
            TopologyNode(
                node_id=hub.resource_id,
                node_type="route_server" if hub.is_route_server else "virtual_hub",
                label=hub.name,
                resource_group=snapshot.resource_group,
                tags=hub.tags,
            )
        )

    for hub_conn in snapshot.hub_virtual_network_connections:
        matched_hub = next(
            (h for h in snapshot.virtual_hubs if h.name == hub_conn.virtual_hub_name), None
        )
        if matched_hub is None or not hub_conn.remote_virtual_network_id:
            continue
        edges.append(
            TopologyEdge(
                source_id=matched_hub.resource_id,
                target_id=hub_conn.remote_virtual_network_id,
                relationship="connected_to_vnet",
                evidence=(
                    f"hub connection {hub_conn.name} "
                    f"remoteVirtualNetwork={hub_conn.remote_virtual_network_id}"
                ),
            )
        )
        if not node_exists(hub_conn.remote_virtual_network_id):
            warnings.append(
                CollectionWarning(
                    resource_type="virtual_network",
                    code="OUT_OF_SCOPE_TARGET",
                    message=(
                        f"Hub connection {hub_conn.name} references VNet "
                        f"{hub_conn.remote_virtual_network_id}, outside this resource "
                        "group's scope -- no node exists for it."
                    ),
                )
            )

    for vpn_gw in snapshot.vpn_gateways:
        add_node(
            TopologyNode(
                node_id=vpn_gw.resource_id,
                node_type="vpn_gateway",
                label=vpn_gw.name,
                resource_group=snapshot.resource_group,
                tags=vpn_gw.tags,
            )
        )
        if vpn_gw.virtual_hub_id:
            edges.append(
                TopologyEdge(
                    source_id=vpn_gw.virtual_hub_id,
                    target_id=vpn_gw.resource_id,
                    relationship="hub_has_vpn_gateway",
                    evidence=f"VPN gateway {vpn_gw.name} virtualHub={vpn_gw.virtual_hub_id}",
                )
            )

    for vpn_conn in snapshot.vpn_connections:
        matched_vpn_gw = next(
            (g for g in snapshot.vpn_gateways if g.name == vpn_conn.vpn_gateway_name), None
        )
        if matched_vpn_gw is None:
            continue
        add_node(
            TopologyNode(
                node_id=vpn_conn.resource_id,
                node_type="vpn_connection",
                label=vpn_conn.name,
                resource_group=snapshot.resource_group,
            )
        )
        edges.append(
            TopologyEdge(
                source_id=matched_vpn_gw.resource_id,
                target_id=vpn_conn.resource_id,
                relationship="has_connection",
                evidence=f"VPN connection {vpn_conn.name} status={vpn_conn.connection_status}",
            )
        )
        if vpn_conn.remote_vpn_site_id:
            edges.append(
                TopologyEdge(
                    source_id=vpn_conn.resource_id,
                    target_id=vpn_conn.remote_vpn_site_id,
                    relationship="connects_to_site",
                    evidence=(
                        f"VPN connection {vpn_conn.name} "
                        f"remoteVpnSite={vpn_conn.remote_vpn_site_id}"
                    ),
                )
            )
            if not node_exists(vpn_conn.remote_vpn_site_id):
                warnings.append(
                    CollectionWarning(
                        resource_type="vpn_site",
                        code="OUT_OF_SCOPE_TARGET",
                        message=(
                            f"VPN connection {vpn_conn.name} references site "
                            f"{vpn_conn.remote_vpn_site_id}, outside this resource "
                            "group's scope -- no node exists for it."
                        ),
                    )
                )

    for vng in snapshot.virtual_network_gateways:
        add_node(
            TopologyNode(
                node_id=vng.resource_id,
                node_type="virtual_network_gateway",
                label=vng.name,
                resource_group=snapshot.resource_group,
                tags=vng.tags,
            )
        )

    for vng_conn in snapshot.virtual_network_gateway_connections:
        add_node(
            TopologyNode(
                node_id=vng_conn.resource_id,
                node_type="virtual_network_gateway_connection",
                label=vng_conn.name,
                resource_group=snapshot.resource_group,
                tags=vng_conn.tags,
            )
        )
        for gw_id in (vng_conn.virtual_network_gateway1_id, vng_conn.virtual_network_gateway2_id):
            if gw_id and node_exists(gw_id):
                edges.append(
                    TopologyEdge(
                        source_id=gw_id,
                        target_id=vng_conn.resource_id,
                        relationship="has_connection",
                        evidence=f"connection {vng_conn.name} status={vng_conn.connection_status}",
                    )
                )
        if vng_conn.local_network_gateway2_id:
            edges.append(
                TopologyEdge(
                    source_id=vng_conn.resource_id,
                    target_id=vng_conn.local_network_gateway2_id,
                    relationship="connects_to_local_gateway",
                    evidence=(
                        f"connection {vng_conn.name} "
                        f"localNetworkGateway2={vng_conn.local_network_gateway2_id}"
                    ),
                )
            )

    for circuit in snapshot.express_route_circuits:
        add_node(
            TopologyNode(
                node_id=circuit.resource_id,
                node_type="express_route_circuit",
                label=circuit.name,
                resource_group=snapshot.resource_group,
                tags=circuit.tags,
            )
        )

    for er_gw in snapshot.express_route_gateways:
        add_node(
            TopologyNode(
                node_id=er_gw.resource_id,
                node_type="express_route_gateway",
                label=er_gw.name,
                resource_group=snapshot.resource_group,
                tags=er_gw.tags,
            )
        )
        if er_gw.virtual_hub_id and node_exists(er_gw.virtual_hub_id):
            edges.append(
                TopologyEdge(
                    source_id=er_gw.virtual_hub_id,
                    target_id=er_gw.resource_id,
                    relationship="hub_has_express_route_gateway",
                    evidence=f"ExpressRoute gateway {er_gw.name} virtualHub={er_gw.virtual_hub_id}",
                )
            )

    for er_conn in snapshot.express_route_connections:
        matched_er_gw = next(
            (
                g
                for g in snapshot.express_route_gateways
                if g.name == er_conn.express_route_gateway_name
            ),
            None,
        )
        if matched_er_gw is None:
            continue
        add_node(
            TopologyNode(
                node_id=er_conn.resource_id,
                node_type="express_route_connection",
                label=er_conn.name,
                resource_group=snapshot.resource_group,
            )
        )
        edges.append(
            TopologyEdge(
                source_id=matched_er_gw.resource_id,
                target_id=er_conn.resource_id,
                relationship="has_connection",
                evidence=f"ExpressRoute connection {er_conn.name}",
            )
        )
        if er_conn.express_route_circuit_peering_id:
            # A peering ID is a child of a circuit ID -- the circuit ID is
            # the peering ID minus its own /peerings/{name} suffix.
            circuit_id = er_conn.express_route_circuit_peering_id.split("/peerings/")[0]
            if node_exists(circuit_id):
                edges.append(
                    TopologyEdge(
                        source_id=er_conn.resource_id,
                        target_id=circuit_id,
                        relationship="connects_to_circuit",
                        evidence=(
                            f"connection {er_conn.name} "
                            f"peering={er_conn.express_route_circuit_peering_id}"
                        ),
                    )
                )

    for pe in snapshot.private_endpoints:
        add_node(
            TopologyNode(
                node_id=pe.resource_id,
                node_type="private_endpoint",
                label=pe.name,
                resource_group=snapshot.resource_group,
                tags=pe.tags,
            )
        )
        if pe.subnet_id:
            edges.append(
                TopologyEdge(
                    source_id=pe.resource_id,
                    target_id=pe.subnet_id,
                    relationship="resides_in",
                    evidence=f"private endpoint {pe.name} subnet={pe.subnet_id}",
                )
            )
            if not node_exists(pe.subnet_id):
                warnings.append(
                    CollectionWarning(
                        resource_type="subnet",
                        code="OUT_OF_SCOPE_TARGET",
                        message=(
                            f"Private endpoint {pe.name} references subnet "
                            f"{pe.subnet_id}, outside this resource group's scope -- "
                            "no node exists for it."
                        ),
                    )
                )

    edges.sort(key=lambda e: (e.source_id, e.target_id, e.relationship))
    sorted_nodes = sorted(nodes.values(), key=lambda n: (n.node_type, n.node_id))

    return HybridTopology(
        resource_group=snapshot.resource_group,
        subscription_id=snapshot.subscription_id,
        nodes=sorted_nodes,
        edges=edges,
        warnings=warnings,
    )


__all__ = ["build_hybrid_topology"]
