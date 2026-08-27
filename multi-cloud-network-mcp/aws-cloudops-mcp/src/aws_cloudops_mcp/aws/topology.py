"""AWS service layer: ``aws_get_vpc_topology`` graph assembly.

Joins every other resource type in this milestone into one node/edge graph
scoped to a single VPC. Raw collection (each ``list_*`` call) stays fully
separate from normalization (each service module above) and from graph
assembly (this module) -- this module never talks to boto3 directly, it
only calls the other service-layer functions and shapes their already-
normalized output into nodes and edges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.collection import track_calls
from aws_cloudops_mcp.aws.endpoints import list_vpc_endpoints
from aws_cloudops_mcp.aws.enis import list_network_interfaces
from aws_cloudops_mcp.aws.gateways import (
    list_egress_only_internet_gateways,
    list_internet_gateways,
)
from aws_cloudops_mcp.aws.loadbalancers import list_load_balancers
from aws_cloudops_mcp.aws.nacls import list_network_acls
from aws_cloudops_mcp.aws.nat import list_nat_gateways
from aws_cloudops_mcp.aws.networking import list_route_tables, list_subnets, list_vpcs
from aws_cloudops_mcp.aws.peering import list_vpc_peering_connections
from aws_cloudops_mcp.aws.prefix_lists import list_managed_prefix_lists
from aws_cloudops_mcp.aws.security import list_security_groups
from aws_cloudops_mcp.exceptions import ResourceNotFoundError
from aws_cloudops_mcp.models.common import CollectionWarning
from aws_cloudops_mcp.models.topology import TopologyEdge, TopologyNode, VpcTopology

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

# Route target types this milestone has a resource collector (and therefore
# a node) for. Anything else (e.g. a virtual-private-gateway or transit-
# gateway target) is explicitly out of scope -- the edge is still recorded
# (with the raw target as an orphan reference) but flagged with a warning
# rather than silently dropped or crashed on.
_IN_SCOPE_ROUTE_TARGET_TYPES = {
    "gateway",
    "nat_gateway",
    "vpc_peering_connection",
    "network_interface",
    "egress_only_internet_gateway",
    "vpc_endpoint",
}


def get_vpc_topology(client_factory: ClientFactory, *, region: str, vpc_id: str) -> VpcTopology:
    """Assemble the joined topology graph for one VPC."""
    warnings: list[CollectionWarning] = []
    nodes: dict[str, TopologyNode] = {}
    edges: list[TopologyEdge] = []

    def add_node(node: TopologyNode) -> None:
        nodes.setdefault(node.node_id, node)

    with track_calls() as counter:
        vpc_result = list_vpcs(client_factory, region=region, vpc_ids=[vpc_id])
        warnings.extend(vpc_result.warnings)
        vpcs = vpc_result.data
        if not vpcs:
            raise ResourceNotFoundError(f"VPC '{vpc_id}' was not found in region '{region}'.")
        vpc = vpcs[0]

        add_node(
            TopologyNode(
                node_id=vpc.vpc_id,
                node_type="vpc",
                label=vpc.tags.get("Name", vpc.vpc_id),
                vpc_id=vpc.vpc_id,
                region=region,
                tags=vpc.tags,
            )
        )

        subnets = list_subnets(client_factory, region=region, vpc_id=vpc_id)
        for subnet in subnets:
            add_node(
                TopologyNode(
                    node_id=subnet.subnet_id,
                    node_type="subnet",
                    label=subnet.tags.get("Name", subnet.subnet_id),
                    vpc_id=vpc_id,
                    region=region,
                    tags=subnet.tags,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=vpc_id,
                    target_id=subnet.subnet_id,
                    relationship="contains",
                    evidence=f"subnet {subnet.subnet_id} VpcId={vpc_id}",
                )
            )

        route_tables = list_route_tables(client_factory, region=region, vpc_id=vpc_id)
        referenced_prefix_list_ids: set[str] = set()
        for rt in route_tables:
            add_node(
                TopologyNode(
                    node_id=rt.route_table_id,
                    node_type="route_table",
                    label=rt.tags.get("Name", rt.route_table_id),
                    vpc_id=vpc_id,
                    region=region,
                    tags=rt.tags,
                )
            )
            for assoc in rt.associations:
                if assoc.subnet_id:
                    edges.append(
                        TopologyEdge(
                            source_id=assoc.subnet_id,
                            target_id=rt.route_table_id,
                            relationship="associated_with",
                            evidence=(
                                f"route table {rt.route_table_id} association "
                                f"{assoc.route_table_association_id} SubnetId={assoc.subnet_id}"
                            ),
                        )
                    )
                elif assoc.main:
                    edges.append(
                        TopologyEdge(
                            source_id=vpc_id,
                            target_id=rt.route_table_id,
                            relationship="main_route_table",
                            evidence=f"route table {rt.route_table_id} association Main=true",
                        )
                    )

            for route in rt.routes:
                if route.destination_prefix_list_id:
                    referenced_prefix_list_ids.add(route.destination_prefix_list_id)
                if not route.target:
                    continue
                if route.target == "local":
                    edges.append(
                        TopologyEdge(
                            source_id=rt.route_table_id,
                            target_id=vpc_id,
                            relationship="local_route",
                            evidence=(
                                f"route in {rt.route_table_id}: "
                                f"{route.destination_cidr_block} -> local"
                            ),
                        )
                    )
                    continue

                evidence = (
                    f"route in {rt.route_table_id}: "
                    f"{route.destination_cidr_block or route.destination_prefix_list_id} "
                    f"-> {route.target_type}:{route.target} (state={route.state})"
                )
                edges.append(
                    TopologyEdge(
                        source_id=rt.route_table_id,
                        target_id=route.target,
                        relationship="routes_to",
                        evidence=evidence,
                    )
                )
                if route.target_type not in _IN_SCOPE_ROUTE_TARGET_TYPES:
                    warnings.append(
                        CollectionWarning(
                            resource_type="route_target",
                            code="OUT_OF_SCOPE_TARGET",
                            message=(
                                f"Route table {rt.route_table_id} routes to "
                                f"{route.target_type or 'unknown'}:{route.target}, a "
                                "resource type outside this milestone's coverage -- the "
                                "edge is recorded but no node exists for that target."
                            ),
                        )
                    )

        for igw in list_internet_gateways(client_factory, region=region, vpc_id=vpc_id):
            add_node(
                TopologyNode(
                    node_id=igw.internet_gateway_id,
                    node_type="internet_gateway",
                    label=igw.tags.get("Name", igw.internet_gateway_id),
                    vpc_id=vpc_id,
                    region=region,
                    tags=igw.tags,
                )
            )
            for att in igw.attachments:
                if att.vpc_id == vpc_id:
                    edges.append(
                        TopologyEdge(
                            source_id=vpc_id,
                            target_id=igw.internet_gateway_id,
                            relationship="attached_to",
                            evidence=(
                                f"internet gateway {igw.internet_gateway_id} attachment "
                                f"VpcId={vpc_id} State={att.state}"
                            ),
                        )
                    )

        for eigw in list_egress_only_internet_gateways(client_factory, region=region):
            if not any(a.vpc_id == vpc_id for a in eigw.attachments):
                continue
            add_node(
                TopologyNode(
                    node_id=eigw.egress_only_internet_gateway_id,
                    node_type="egress_only_internet_gateway",
                    label=eigw.egress_only_internet_gateway_id,
                    vpc_id=vpc_id,
                    region=region,
                    tags=eigw.tags,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=vpc_id,
                    target_id=eigw.egress_only_internet_gateway_id,
                    relationship="attached_to",
                    evidence=(
                        f"egress-only internet gateway "
                        f"{eigw.egress_only_internet_gateway_id} attachment VpcId={vpc_id}"
                    ),
                )
            )

        for nat in list_nat_gateways(client_factory, region=region, vpc_id=vpc_id):
            add_node(
                TopologyNode(
                    node_id=nat.nat_gateway_id,
                    node_type="nat_gateway",
                    label=nat.tags.get("Name", nat.nat_gateway_id),
                    vpc_id=vpc_id,
                    region=region,
                    tags=nat.tags,
                )
            )
            if nat.subnet_id:
                edges.append(
                    TopologyEdge(
                        source_id=nat.subnet_id,
                        target_id=nat.nat_gateway_id,
                        relationship="hosts",
                        evidence=f"nat gateway {nat.nat_gateway_id} SubnetId={nat.subnet_id}",
                    )
                )

        for sg in list_security_groups(client_factory, region=region, vpc_id=vpc_id):
            add_node(
                TopologyNode(
                    node_id=sg.group_id,
                    node_type="security_group",
                    label=sg.group_name or sg.group_id,
                    vpc_id=vpc_id,
                    region=region,
                    tags=sg.tags,
                )
            )

        for nacl in list_network_acls(client_factory, region=region, vpc_id=vpc_id):
            add_node(
                TopologyNode(
                    node_id=nacl.network_acl_id,
                    node_type="network_acl",
                    label=nacl.tags.get("Name", nacl.network_acl_id),
                    vpc_id=vpc_id,
                    region=region,
                    tags=nacl.tags,
                )
            )
            for nacl_assoc in nacl.associations:
                if nacl_assoc.subnet_id:
                    edges.append(
                        TopologyEdge(
                            source_id=nacl_assoc.subnet_id,
                            target_id=nacl.network_acl_id,
                            relationship="protected_by",
                            evidence=(
                                f"network acl {nacl.network_acl_id} association "
                                f"SubnetId={nacl_assoc.subnet_id}"
                            ),
                        )
                    )

        for eni in list_network_interfaces(client_factory, region=region, vpc_id=vpc_id):
            add_node(
                TopologyNode(
                    node_id=eni.network_interface_id,
                    node_type="network_interface",
                    label=eni.description or eni.network_interface_id,
                    vpc_id=vpc_id,
                    region=region,
                    tags=eni.tags,
                )
            )
            if eni.subnet_id:
                edges.append(
                    TopologyEdge(
                        source_id=eni.network_interface_id,
                        target_id=eni.subnet_id,
                        relationship="resides_in",
                        evidence=(f"eni {eni.network_interface_id} SubnetId={eni.subnet_id}"),
                    )
                )
            for sg_id in eni.security_group_ids:
                edges.append(
                    TopologyEdge(
                        source_id=eni.network_interface_id,
                        target_id=sg_id,
                        relationship="member_of",
                        evidence=f"eni {eni.network_interface_id} Groups includes {sg_id}",
                    )
                )

        for pcx in list_vpc_peering_connections(client_factory, region=region, vpc_id=vpc_id):
            add_node(
                TopologyNode(
                    node_id=pcx.vpc_peering_connection_id,
                    node_type="vpc_peering_connection",
                    label=pcx.tags.get("Name", pcx.vpc_peering_connection_id),
                    vpc_id=vpc_id,
                    region=region,
                    tags=pcx.tags,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=vpc_id,
                    target_id=pcx.vpc_peering_connection_id,
                    relationship="peered_with",
                    evidence=f"peering {pcx.vpc_peering_connection_id} connects {vpc_id}",
                )
            )
            other_vpc_id = (
                pcx.accepter.vpc_id if pcx.requester.vpc_id == vpc_id else pcx.requester.vpc_id
            )
            if other_vpc_id:
                edges.append(
                    TopologyEdge(
                        source_id=pcx.vpc_peering_connection_id,
                        target_id=other_vpc_id,
                        relationship="peers_with_vpc",
                        evidence=(
                            f"peering {pcx.vpc_peering_connection_id} peer VpcId={other_vpc_id}"
                        ),
                    )
                )
                if other_vpc_id not in nodes:
                    warnings.append(
                        CollectionWarning(
                            resource_type="vpc_peering_connection",
                            code="OUT_OF_SCOPE_TARGET",
                            message=(
                                f"Peering {pcx.vpc_peering_connection_id} references peer "
                                f"VPC {other_vpc_id}, which is outside this topology's "
                                "single-VPC scope -- no node exists for it."
                            ),
                        )
                    )

        for vpce in list_vpc_endpoints(client_factory, region=region, vpc_id=vpc_id):
            add_node(
                TopologyNode(
                    node_id=vpce.vpc_endpoint_id,
                    node_type="vpc_endpoint",
                    label=vpce.tags.get("Name", vpce.vpc_endpoint_id),
                    vpc_id=vpc_id,
                    region=region,
                    tags=vpce.tags,
                )
            )
            edges.append(
                TopologyEdge(
                    source_id=vpc_id,
                    target_id=vpce.vpc_endpoint_id,
                    relationship="has_endpoint",
                    evidence=f"endpoint {vpce.vpc_endpoint_id} VpcId={vpc_id}",
                )
            )
            for subnet_id in vpce.subnet_ids:
                edges.append(
                    TopologyEdge(
                        source_id=vpce.vpc_endpoint_id,
                        target_id=subnet_id,
                        relationship="deployed_in",
                        evidence=(
                            f"endpoint {vpce.vpc_endpoint_id} SubnetIds includes {subnet_id}"
                        ),
                    )
                )
            for rtb_id in vpce.route_table_ids:
                edges.append(
                    TopologyEdge(
                        source_id=rtb_id,
                        target_id=vpce.vpc_endpoint_id,
                        relationship="references",
                        evidence=(
                            f"endpoint {vpce.vpc_endpoint_id} RouteTableIds includes {rtb_id}"
                        ),
                    )
                )

        lb_result = list_load_balancers(client_factory, region=region, vpc_id=vpc_id)
        warnings.extend(lb_result.warnings)
        for lb in lb_result.data:
            add_node(
                TopologyNode(
                    node_id=lb.load_balancer_arn,
                    node_type="load_balancer",
                    label=lb.load_balancer_name,
                    vpc_id=vpc_id,
                    region=region,
                    tags=lb.tags,
                )
            )
            for az in lb.availability_zones:
                if az.subnet_id:
                    edges.append(
                        TopologyEdge(
                            source_id=lb.load_balancer_arn,
                            target_id=az.subnet_id,
                            relationship="deployed_in",
                            evidence=(
                                f"load balancer {lb.load_balancer_name} "
                                f"AvailabilityZones subnet {az.subnet_id}"
                            ),
                        )
                    )
            for tg in lb.target_groups:
                add_node(
                    TopologyNode(
                        node_id=tg.target_group_arn,
                        node_type="target_group",
                        label=tg.target_group_name,
                        vpc_id=vpc_id,
                        region=region,
                        tags=tg.tags,
                    )
                )
                edges.append(
                    TopologyEdge(
                        source_id=lb.load_balancer_arn,
                        target_id=tg.target_group_arn,
                        relationship="routes_to",
                        evidence=(
                            f"target group {tg.target_group_name} LoadBalancerArns "
                            f"includes {lb.load_balancer_arn}"
                        ),
                    )
                )

        if referenced_prefix_list_ids:
            pl_result = list_managed_prefix_lists(
                client_factory,
                region=region,
                prefix_list_ids=sorted(referenced_prefix_list_ids),
            )
            warnings.extend(pl_result.warnings)
            for pl in pl_result.data:
                add_node(
                    TopologyNode(
                        node_id=pl.prefix_list_id,
                        node_type="managed_prefix_list",
                        label=pl.prefix_list_name or pl.prefix_list_id,
                        vpc_id=vpc_id,
                        region=region,
                        tags=pl.tags,
                    )
                )

    edges.sort(key=lambda e: (e.source_id, e.target_id, e.relationship))
    sorted_nodes = sorted(nodes.values(), key=lambda n: (n.node_type, n.node_id))

    return VpcTopology(
        vpc_id=vpc_id,
        region=region,
        nodes=sorted_nodes,
        edges=edges,
        warnings=warnings,
        api_call_count=counter.count,
    )


__all__ = ["get_vpc_topology"]
