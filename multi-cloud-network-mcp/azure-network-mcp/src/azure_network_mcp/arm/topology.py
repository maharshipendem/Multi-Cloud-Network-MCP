"""ARM service layer: ``azure_get_vnet_topology`` graph assembly.

Joins every other resource type this milestone covers into one typed
node/edge graph scoped to a single VNet. Raw collection (each
``list_*``/``get`` call) stays fully separate from normalization (each
service module above) and from graph assembly (this module) -- this
module never talks to the Azure SDK directly, it only calls the other
service-layer functions and shapes their already-normalized output into
nodes and edges, mirroring this project's AWS sibling's topology-
construction discipline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import track_calls
from azure_network_mcp.arm.nat_gateways import list_nat_gateways
from azure_network_mcp.arm.network_interfaces import list_network_interfaces
from azure_network_mcp.arm.network_security_groups import list_network_security_groups
from azure_network_mcp.arm.networking import list_subnets, list_virtual_networks
from azure_network_mcp.arm.peerings import list_virtual_network_peerings
from azure_network_mcp.arm.public_ips import list_public_ip_addresses
from azure_network_mcp.arm.route_tables import list_route_tables
from azure_network_mcp.exceptions import ResourceNotFoundError
from azure_network_mcp.models.common import CollectionWarning, normalize_resource_id
from azure_network_mcp.models.topology import TopologyEdge, TopologyNode, VnetTopology

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory

# Resource types this milestone collects (and therefore has a node for)
# when they live in the same resource group as the VNet being mapped.
# A subnet reference to a resource in a *different* resource group still
# produces an edge -- with no matching node -- flagged with a warning
# rather than silently dropped; joining across resource groups would
# make this tool's cost unbounded.


def get_vnet_topology(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_network_name: str,
) -> VnetTopology:
    """Assemble the joined topology graph for one VNet."""
    warnings: list[CollectionWarning] = []
    nodes: dict[str, TopologyNode] = {}
    edges: list[TopologyEdge] = []

    def add_node(node: TopologyNode) -> None:
        nodes.setdefault(normalize_resource_id(node.node_id), node)

    def node_exists(resource_id: str) -> bool:
        return normalize_resource_id(resource_id) in nodes

    with track_calls() as counter:
        vnets = list_virtual_networks(
            client_factory, subscription_id=subscription_id, resource_group=resource_group
        )
        vnet = next((v for v in vnets if v.name == virtual_network_name), None)
        if vnet is None:
            raise ResourceNotFoundError(
                f"Virtual network '{virtual_network_name}' was not found in resource group "
                f"'{resource_group}' (subscription '{subscription_id}')."
            )

        add_node(
            TopologyNode(
                node_id=vnet.resource_id,
                node_type="virtual_network",
                label=vnet.tags.get("Name", vnet.name),
                virtual_network_name=vnet.name,
                resource_group=resource_group,
                tags=vnet.tags,
            )
        )

        # Pre-fetch the resource-group-scoped resources subnets can reference,
        # so subnet -> NSG/route-table/NAT-gateway edges resolve to real nodes
        # without a per-subnet API call.
        nsgs = {
            normalize_resource_id(n.resource_id): n
            for n in list_network_security_groups(
                client_factory, subscription_id=subscription_id, resource_group=resource_group
            )
        }
        route_tables = {
            normalize_resource_id(r.resource_id): r
            for r in list_route_tables(
                client_factory, subscription_id=subscription_id, resource_group=resource_group
            )
        }
        nat_gateways = {
            normalize_resource_id(g.resource_id): g
            for g in list_nat_gateways(
                client_factory, subscription_id=subscription_id, resource_group=resource_group
            )
        }
        nics = list_network_interfaces(
            client_factory, subscription_id=subscription_id, resource_group=resource_group
        )
        public_ips = {
            normalize_resource_id(p.resource_id): p
            for p in list_public_ip_addresses(
                client_factory, subscription_id=subscription_id, resource_group=resource_group
            )
        }

        subnets = list_subnets(
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            virtual_network_name=virtual_network_name,
        )
        for subnet in subnets:
            add_node(
                TopologyNode(
                    node_id=subnet.resource_id,
                    node_type="subnet",
                    label=subnet.name,
                    virtual_network_name=virtual_network_name,
                    resource_group=resource_group,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=vnet.resource_id,
                    target_id=subnet.resource_id,
                    relationship="contains",
                    evidence=f"subnet {subnet.name} is listed under VNet {virtual_network_name}",
                )
            )

            for ref_id, rel, kind, registry in (
                (subnet.network_security_group_id, "protected_by", "NetworkSecurityGroup.id", nsgs),
                (subnet.route_table_id, "routed_by", "RouteTable.id", route_tables),
                (subnet.nat_gateway_id, "uses_nat_gateway", "NatGateway.id", nat_gateways),
            ):
                if not ref_id:
                    continue
                edges.append(
                    TopologyEdge(
                        source_id=subnet.resource_id,
                        target_id=ref_id,
                        relationship=rel,
                        evidence=f"subnet {subnet.name} {kind}={ref_id}",
                    )
                )
                target = registry.get(normalize_resource_id(ref_id))
                if target is not None:
                    add_node(
                        TopologyNode(
                            node_id=target.resource_id,
                            node_type={
                                "protected_by": "network_security_group",
                                "routed_by": "route_table",
                                "uses_nat_gateway": "nat_gateway",
                            }[rel],
                            label=target.name,
                            resource_group=resource_group,
                            tags=target.tags,
                        )
                    )
                elif not node_exists(ref_id):
                    warnings.append(
                        CollectionWarning(
                            resource_type=kind.split(".")[0],
                            code="OUT_OF_SCOPE_TARGET",
                            message=(
                                f"Subnet {subnet.name} references {ref_id}, which is outside "
                                f"resource group '{resource_group}' -- no node exists for it."
                            ),
                        )
                    )

        for nic in nics:
            nic_subnet_id = next(
                (
                    normalize_resource_id(ipc.subnet_id)
                    for ipc in nic.ip_configurations
                    if ipc.subnet_id
                ),
                None,
            )
            if nic_subnet_id is None or nic_subnet_id not in nodes:
                continue  # NIC isn't in one of this VNet's subnets
            add_node(
                TopologyNode(
                    node_id=nic.resource_id,
                    node_type="network_interface",
                    label=nic.name,
                    resource_group=resource_group,
                    tags=nic.tags,
                )
            )
            nic_subnet_ref = nic.ip_configurations[0].subnet_id or ""
            edges.append(
                TopologyEdge(
                    source_id=nic.resource_id,
                    target_id=nic_subnet_ref,
                    relationship="resides_in",
                    evidence=f"NIC {nic.name} ip_configuration subnet={nic_subnet_ref}",
                )
            )
            for ipc in nic.ip_configurations:
                if not ipc.public_ip_address_id:
                    continue
                pip = public_ips.get(normalize_resource_id(ipc.public_ip_address_id))
                edges.append(
                    TopologyEdge(
                        source_id=nic.resource_id,
                        target_id=ipc.public_ip_address_id,
                        relationship="has_public_ip",
                        evidence=(
                            f"NIC {nic.name} ip_configuration "
                            f"public_ip_address={ipc.public_ip_address_id}"
                        ),
                    )
                )
                if pip is not None:
                    add_node(
                        TopologyNode(
                            node_id=pip.resource_id,
                            node_type="public_ip_address",
                            label=pip.ip_address or pip.name,
                            resource_group=resource_group,
                            tags=pip.tags,
                        )
                    )

        for peering in list_virtual_network_peerings(
            client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            virtual_network_name=virtual_network_name,
        ):
            add_node(
                TopologyNode(
                    node_id=peering.resource_id,
                    node_type="virtual_network_peering",
                    label=peering.name,
                    virtual_network_name=virtual_network_name,
                    resource_group=resource_group,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=vnet.resource_id,
                    target_id=peering.resource_id,
                    relationship="peered_with",
                    evidence=f"peering {peering.name} PeeringState={peering.peering_state}",
                )
            )
            if peering.remote_virtual_network_id and not node_exists(
                peering.remote_virtual_network_id
            ):
                edges.append(
                    TopologyEdge(
                        source_id=peering.resource_id,
                        target_id=peering.remote_virtual_network_id,
                        relationship="peers_with_vnet",
                        evidence=(
                            f"peering {peering.name} remote_virtual_network="
                            f"{peering.remote_virtual_network_id}"
                        ),
                    )
                )
                warnings.append(
                    CollectionWarning(
                        resource_type="virtual_network_peering",
                        code="OUT_OF_SCOPE_TARGET",
                        message=(
                            f"Peering {peering.name} references remote VNet "
                            f"{peering.remote_virtual_network_id}, outside this topology's "
                            "single-VNet scope -- no node exists for it."
                        ),
                    )
                )

    edges.sort(key=lambda e: (e.source_id, e.target_id, e.relationship))
    sorted_nodes = sorted(nodes.values(), key=lambda n: (n.node_type, n.node_id))

    return VnetTopology(
        virtual_network_name=virtual_network_name,
        resource_group=resource_group,
        subscription_id=subscription_id,
        nodes=sorted_nodes,
        edges=edges,
        warnings=warnings,
        api_call_count=counter.count,
    )


__all__ = ["get_vnet_topology"]
