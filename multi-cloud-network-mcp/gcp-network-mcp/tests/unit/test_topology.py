from __future__ import annotations

from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager, make_pager

from gcp_network_mcp.gcp.topology import get_vpc_topology

NETWORK_SELF_LINK = (
    f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/networks/vpc-1"
)
SUBNET_SELF_LINK = f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/subnetworks/subnet-1"
OTHER_PROJECT_NETWORK = (
    "https://www.googleapis.com/compute/v1/projects/other-proj/global/networks/vpc-x"
)


def _empty_aggregated(items_field: str) -> object:
    return make_aggregated_pager({}, items_field=items_field)


def _stub_clean_topology(client_factory) -> None:
    """Wires every collection call to return an empty (but successful)
    result, so a test can override just the pieces it cares about."""
    client_factory.networks().list.return_value = make_pager([])
    client_factory.subnetworks().aggregated_list.return_value = _empty_aggregated("subnetworks")
    client_factory.instances().aggregated_list.return_value = _empty_aggregated("instances")
    client_factory.routers().aggregated_list.return_value = _empty_aggregated("routers")


def test_topology_is_complete_and_empty_with_no_resources(client_factory) -> None:
    _stub_clean_topology(client_factory)
    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)
    assert topology.completeness == "complete"
    assert topology.nodes == []
    assert topology.edges == []
    assert topology.warnings == []
    assert topology.project_id == PROJECT_ID


def test_topology_joins_network_subnetwork_instance_and_router(client_factory) -> None:
    network = compute_v1.Network(
        name="vpc-1", self_link=NETWORK_SELF_LINK, auto_create_subnetworks=True
    )
    subnet = compute_v1.Subnetwork(
        name="subnet-1",
        self_link=SUBNET_SELF_LINK,
        network=NETWORK_SELF_LINK,
        ip_cidr_range="10.0.0.0/24",
    )
    instance = compute_v1.Instance(
        name="vm-1",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/zones/us-central1-a/instances/vm-1",
        network_interfaces=[
            compute_v1.NetworkInterface(
                name="nic0", network=NETWORK_SELF_LINK, subnetwork=SUBNET_SELF_LINK
            )
        ],
    )
    router = compute_v1.Router(
        name="router-1",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/routers/router-1",
        network=NETWORK_SELF_LINK,
    )

    client_factory.networks().list.return_value = make_pager([network])
    client_factory.subnetworks().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [subnet]}, items_field="subnetworks"
    )
    client_factory.instances().aggregated_list.return_value = make_aggregated_pager(
        {"zones/us-central1-a": [instance]}, items_field="instances"
    )
    client_factory.routers().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [router]}, items_field="routers"
    )

    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)

    assert topology.completeness == "complete"
    node_types = {n.node_type for n in topology.nodes}
    assert node_types == {"network", "subnetwork", "instance", "router"}
    relationships = {e.relationship for e in topology.edges}
    assert relationships == {"belongs_to_network", "has_interface_in", "attached_to_network"}
    assert topology.api_call_count > 0

    # deterministic ordering: nodes sorted by (node_type, node_id)
    assert [n.node_type for n in topology.nodes] == sorted(n.node_type for n in topology.nodes)


def test_topology_flags_subnetwork_referencing_missing_network_as_partial(client_factory) -> None:
    orphan_subnet_link = (
        f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/regions/us-central1/"
        "subnetworks/orphan-subnet"
    )
    subnet = compute_v1.Subnetwork(
        name="orphan-subnet", self_link=orphan_subnet_link, network=OTHER_PROJECT_NETWORK
    )
    client_factory.networks().list.return_value = make_pager([])
    client_factory.subnetworks().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": [subnet]}, items_field="subnetworks"
    )
    client_factory.instances().aggregated_list.return_value = _empty_aggregated("instances")
    client_factory.routers().aggregated_list.return_value = _empty_aggregated("routers")

    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)

    assert topology.completeness == "partial"
    assert any(w.code == "OUT_OF_SCOPE_TARGET" for w in topology.warnings)
    # the edge to the unresolved network still exists
    assert any(e.target_id == OTHER_PROJECT_NETWORK for e in topology.edges)
    # ...but no node was fabricated for it (unlike the peering case below)
    assert not any(n.node_id == OTHER_PROJECT_NETWORK for n in topology.nodes)


def test_topology_peering_to_unresolvable_network_adds_external_node(client_factory) -> None:
    network = compute_v1.Network(
        name="vpc-1",
        self_link=NETWORK_SELF_LINK,
        peerings=[
            compute_v1.NetworkPeering(name="peer-1", network=OTHER_PROJECT_NETWORK, state="ACTIVE")
        ],
    )
    client_factory.networks().list.return_value = make_pager([network])
    client_factory.subnetworks().aggregated_list.return_value = _empty_aggregated("subnetworks")
    client_factory.instances().aggregated_list.return_value = _empty_aggregated("instances")
    client_factory.routers().aggregated_list.return_value = _empty_aggregated("routers")

    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)

    assert topology.completeness == "partial"
    external_node = next(n for n in topology.nodes if n.node_type == "external_network")
    assert external_node.node_id == OTHER_PROJECT_NETWORK
    assert any(
        e.relationship == "peered_with" and e.target_id == OTHER_PROJECT_NETWORK
        for e in topology.edges
    )


def test_topology_instance_with_no_subnetworked_interface_gets_no_node(client_factory) -> None:
    instance = compute_v1.Instance(
        name="vm-no-subnet",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/zones/us-central1-a/instances/vm-no-subnet",
        network_interfaces=[compute_v1.NetworkInterface(name="nic0")],
    )
    _stub_clean_topology(client_factory)
    client_factory.instances().aggregated_list.return_value = make_aggregated_pager(
        {"zones/us-central1-a": [instance]}, items_field="instances"
    )

    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)
    assert topology.nodes == []
    assert topology.edges == []


def test_topology_aggregates_warnings_from_joined_collections(client_factory) -> None:
    client_factory.networks().list.return_value = make_pager([])
    client_factory.subnetworks().aggregated_list.return_value = make_aggregated_pager(
        {"regions/us-central1": []},
        items_field="subnetworks",
        scope_warnings={"regions/us-central1": ("UNREACHABLE", "degraded")},
    )
    client_factory.instances().aggregated_list.return_value = _empty_aggregated("instances")
    client_factory.routers().aggregated_list.return_value = _empty_aggregated("routers")

    topology = get_vpc_topology(client_factory, project_id=PROJECT_ID)
    assert topology.completeness == "partial"
    assert any(w.code == "UNREACHABLE" for w in topology.warnings)
