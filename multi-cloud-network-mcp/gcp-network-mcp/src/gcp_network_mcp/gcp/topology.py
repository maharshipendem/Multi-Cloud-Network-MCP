"""``gcp_get_vpc_topology`` graph assembly.

Joins every other resource type this milestone covers into one typed
node/edge graph scoped to a single project. Raw collection (each
``list_*`` call) stays fully separate from normalization (each service
module above) and from graph assembly (this module) -- this module never
talks to the GCP client libraries directly, it only calls the other
service-layer functions and shapes their already-normalized output into
nodes and edges, mirroring this project's AWS/Azure siblings' topology-
construction discipline.

A reference to a resource this project's IAM bindings can't see, or that
lives in a different project (e.g. a peer network, or a Shared VPC host's
network referenced from a service project's subnet) still produces an
edge -- with no matching node -- flagged with an ``OUT_OF_SCOPE_TARGET``
warning rather than silently dropped; resolving across projects would
make this tool's cost unbounded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gcp_network_mcp.gcp.collection import now_iso, track_calls
from gcp_network_mcp.gcp.instances import list_instances
from gcp_network_mcp.gcp.nat import list_routers
from gcp_network_mcp.gcp.networking import extract_peerings, list_networks, list_subnetworks
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.models.common import CollectionWarning
from gcp_network_mcp.models.topology import TopologyEdge, TopologyNode, VpcTopology

if TYPE_CHECKING:
    from gcp_network_mcp.gcp.client_factory import ClientFactory


def get_vpc_topology(client_factory: ClientFactory, *, project_id: str) -> VpcTopology:
    """Assemble the joined topology graph for one project's VPC networking."""
    warnings: list[CollectionWarning] = []
    nodes: dict[str, TopologyNode] = {}
    edges: list[TopologyEdge] = []

    def add_node(node: TopologyNode) -> None:
        nodes.setdefault(node.node_id, node)

    def node_exists(node_id: str) -> bool:
        return node_id in nodes

    with track_calls() as counter:
        networks = list_networks(client_factory, project_id=project_id)
        for network in networks:
            add_node(
                TopologyNode(
                    node_id=network.self_link or network.name,
                    node_type="network",
                    label=network.name,
                    project_id=project_id,
                )
            )

        subnet_result = list_subnetworks(client_factory, project_id=project_id)
        warnings.extend(subnet_result.warnings)
        for subnetwork in subnet_result.data:
            subnet_node_id = subnetwork.self_link or f"{project_id}/{subnetwork.name}"
            add_node(
                TopologyNode(
                    node_id=subnet_node_id,
                    node_type="subnetwork",
                    label=subnetwork.name,
                    project_id=project_id,
                    region=subnetwork.region,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=subnet_node_id,
                    target_id=subnetwork.network_self_link,
                    relationship="belongs_to_network",
                    evidence=f"subnetwork {subnetwork.name}.network={subnetwork.network_self_link}",
                )
            )
            if not node_exists(subnetwork.network_self_link):
                warnings.append(
                    CollectionWarning(
                        resource_type="network",
                        code="OUT_OF_SCOPE_TARGET",
                        message=(
                            f"Subnetwork {subnetwork.name} references network "
                            f"{subnetwork.network_self_link}, which was not found among this "
                            "project's networks -- no node exists for it."
                        ),
                        project_id=project_id,
                    )
                )

        instance_result = list_instances(client_factory, project_id=project_id)
        warnings.extend(instance_result.warnings)
        for instance in instance_result.data:
            instance_node_id = instance.self_link or f"{project_id}/{instance.name}"
            has_interface = False
            for interface in instance.network_interfaces:
                if not interface.subnetwork_self_link:
                    continue
                has_interface = True
                edges.append(
                    TopologyEdge(
                        source_id=instance_node_id,
                        target_id=interface.subnetwork_self_link,
                        relationship="has_interface_in",
                        evidence=(
                            f"instance {instance.name} networkInterfaces[{interface.name}]"
                            f".subnetwork={interface.subnetwork_self_link}"
                        ),
                    )
                )
                if not node_exists(interface.subnetwork_self_link):
                    warnings.append(
                        CollectionWarning(
                            resource_type="subnetwork",
                            code="OUT_OF_SCOPE_TARGET",
                            message=(
                                f"Instance {instance.name} references subnetwork "
                                f"{interface.subnetwork_self_link}, which was not found among "
                                "this project's subnetworks -- no node exists for it."
                            ),
                            project_id=project_id,
                        )
                    )
            if has_interface:
                add_node(
                    TopologyNode(
                        node_id=instance_node_id,
                        node_type="instance",
                        label=instance.name,
                        project_id=project_id,
                        zone=instance.zone,
                    )
                )

        router_result = list_routers(client_factory, project_id=project_id)
        warnings.extend(router_result.warnings)
        for router in router_result.data:
            router_node_id = router.self_link or f"{project_id}/{router.name}"
            add_node(
                TopologyNode(
                    node_id=router_node_id,
                    node_type="router",
                    label=router.name,
                    project_id=project_id,
                    region=router.region,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=router_node_id,
                    target_id=router.network_self_link,
                    relationship="attached_to_network",
                    evidence=f"router {router.name}.network={router.network_self_link}",
                )
            )
            if not node_exists(router.network_self_link):
                warnings.append(
                    CollectionWarning(
                        resource_type="network",
                        code="OUT_OF_SCOPE_TARGET",
                        message=(
                            f"Router {router.name} references network "
                            f"{router.network_self_link}, which was not found among this "
                            "project's networks -- no node exists for it."
                        ),
                        project_id=project_id,
                    )
                )

        raw_networks = paginate(
            client_factory.networks(),
            "list",
            resource_type="network",
            project_id=project_id,
            project=project_id,
        )
        for raw_network in raw_networks:
            for peering in extract_peerings(raw_network):
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
                            node_id=peering.network,
                            node_type="external_network",
                            label=peering.network,
                        )
                    )
                    warnings.append(
                        CollectionWarning(
                            resource_type="network",
                            code="OUT_OF_SCOPE_TARGET",
                            message=(
                                f"Peering {peering.name} references peer network "
                                f"{peering.network}, outside this topology's single-project "
                                "scope -- represented as an external node with no further detail."
                            ),
                            project_id=project_id,
                        )
                    )

    edges.sort(key=lambda e: (e.source_id, e.target_id, e.relationship))
    sorted_nodes = sorted(nodes.values(), key=lambda n: (n.node_type, n.node_id))
    completeness = "partial" if warnings else "complete"

    return VpcTopology(
        project_id=project_id,
        observed_at=now_iso(),
        completeness=completeness,
        nodes=sorted_nodes,
        edges=edges,
        warnings=warnings,
        api_call_count=counter.count,
    )


__all__ = ["get_vpc_topology"]
