from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.topology import get_vnet_topology
from azure_network_mcp.exceptions import ResourceNotFoundError

BASE = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.Network"
)
VNET_ID = f"{BASE}/virtualNetworks/vnet-1"
SUBNET_ID = f"{VNET_ID}/subnets/subnet-a"
NSG_ID = f"{BASE}/networkSecurityGroups/nsg-1"
RT_ID = f"{BASE}/routeTables/rt-1"
NAT_ID = f"{BASE}/natGateways/nat-1"
NIC_ID = f"{BASE}/networkInterfaces/nic-1"
PIP_ID = f"{BASE}/publicIPAddresses/pip-1"
OUT_OF_SCOPE_NSG_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/rg-other/providers/"
    "Microsoft.Network/networkSecurityGroups/nsg-external"
)
REMOTE_VNET_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/rg-other/providers/"
    "Microsoft.Network/virtualNetworks/vnet-remote"
)


def _vnet(*, subnet_id: str = SUBNET_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=VNET_ID,
        name="vnet-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        address_space=SimpleNamespace(address_prefixes=["10.0.0.0/16"]),
        dhcp_options=None,
        subnets=[SimpleNamespace(id=subnet_id)],
        virtual_network_peerings=[],
        enable_ddos_protection=False,
    )


def _subnet(*, nsg_id: str | None = NSG_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=SUBNET_ID,
        name="subnet-a",
        provisioning_state="Succeeded",
        address_prefix="10.0.1.0/24",
        address_prefixes=None,
        network_security_group=SimpleNamespace(id=nsg_id) if nsg_id else None,
        route_table=SimpleNamespace(id=RT_ID),
        nat_gateway=SimpleNamespace(id=NAT_ID),
        service_endpoints=[],
        delegations=[],
    )


def _nsg() -> SimpleNamespace:
    return SimpleNamespace(
        id=NSG_ID,
        name="nsg-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        security_rules=[],
        default_security_rules=[],
        network_interfaces=[],
        subnets=[],
    )


def _route_table() -> SimpleNamespace:
    return SimpleNamespace(
        id=RT_ID,
        name="rt-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        routes=[],
        subnets=[],
        disable_bgp_route_propagation=False,
    )


def _nat_gateway() -> SimpleNamespace:
    return SimpleNamespace(
        id=NAT_ID,
        name="nat-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        sku=SimpleNamespace(name="Standard"),
        idle_timeout_in_minutes=4,
        public_ip_addresses=[],
        subnets=[],
    )


def _nic() -> SimpleNamespace:
    return SimpleNamespace(
        id=NIC_ID,
        name="nic-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        ip_configurations=[
            SimpleNamespace(
                name="ipconfig1",
                private_ip_address="10.0.1.4",
                private_ip_allocation_method="Dynamic",
                subnet=SimpleNamespace(id=SUBNET_ID),
                public_ip_address=SimpleNamespace(id=PIP_ID),
                primary=True,
            )
        ],
        network_security_group=None,
        mac_address=None,
        primary=True,
        enable_ip_forwarding=False,
        enable_accelerated_networking=False,
        virtual_machine=None,
    )


def _pip() -> SimpleNamespace:
    return SimpleNamespace(
        id=PIP_ID,
        name="pip-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        ip_address="20.1.2.3",
        public_ip_allocation_method="Static",
        public_ip_address_version="IPv4",
        sku=SimpleNamespace(name="Standard"),
        idle_timeout_in_minutes=4,
        ip_configuration=SimpleNamespace(id=f"{NIC_ID}/ipConfigurations/ipconfig1"),
    )


def _wire_full_topology(network_client: MagicMock) -> None:
    network_client.virtual_networks.list.return_value = make_pageable([_vnet()])
    network_client.network_security_groups.list.return_value = make_pageable([_nsg()])
    network_client.route_tables.list.return_value = make_pageable([_route_table()])
    network_client.nat_gateways.list.return_value = make_pageable([_nat_gateway()])
    network_client.network_interfaces.list.return_value = make_pageable([_nic()])
    network_client.public_ip_addresses.list.return_value = make_pageable([_pip()])
    network_client.subnets.list.return_value = make_pageable([_subnet()])
    network_client.virtual_network_peerings.list.return_value = make_pageable([])


def test_get_vnet_topology_builds_expected_nodes_and_edges(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_full_topology(network_client)

    topology = get_vnet_topology(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    node_ids = {n.node_id for n in topology.nodes}
    assert VNET_ID in node_ids
    assert SUBNET_ID in node_ids
    assert NSG_ID in node_ids
    assert RT_ID in node_ids
    assert NAT_ID in node_ids
    assert NIC_ID in node_ids
    assert PIP_ID in node_ids

    relationships = {(e.source_id, e.target_id, e.relationship) for e in topology.edges}
    assert (VNET_ID, SUBNET_ID, "contains") in relationships
    assert (SUBNET_ID, NSG_ID, "protected_by") in relationships
    assert (SUBNET_ID, RT_ID, "routed_by") in relationships
    assert (SUBNET_ID, NAT_ID, "uses_nat_gateway") in relationships
    assert (NIC_ID, SUBNET_ID, "resides_in") in relationships
    assert (NIC_ID, PIP_ID, "has_public_ip") in relationships
    assert topology.warnings == []


def test_get_vnet_topology_raises_when_vnet_not_found(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_networks.list.return_value = make_pageable([])

    with pytest.raises(ResourceNotFoundError):
        get_vnet_topology(
            client_factory,
            subscription_id=SUBSCRIPTION_ID,
            resource_group=RESOURCE_GROUP,
            virtual_network_name="does-not-exist",
        )


def test_get_vnet_topology_flags_out_of_scope_subnet_reference(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_networks.list.return_value = make_pageable([_vnet()])
    network_client.network_security_groups.list.return_value = make_pageable([])  # empty RG scope
    network_client.route_tables.list.return_value = make_pageable([])
    network_client.nat_gateways.list.return_value = make_pageable([])
    network_client.network_interfaces.list.return_value = make_pageable([])
    network_client.public_ip_addresses.list.return_value = make_pageable([])
    network_client.subnets.list.return_value = make_pageable([_subnet(nsg_id=OUT_OF_SCOPE_NSG_ID)])
    network_client.virtual_network_peerings.list.return_value = make_pageable([])

    topology = get_vnet_topology(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    node_ids = {n.node_id for n in topology.nodes}
    assert OUT_OF_SCOPE_NSG_ID not in node_ids
    edge_targets = {(e.source_id, e.target_id) for e in topology.edges}
    assert (SUBNET_ID, OUT_OF_SCOPE_NSG_ID) in edge_targets
    assert any(w.code == "OUT_OF_SCOPE_TARGET" for w in topology.warnings)


def test_get_vnet_topology_flags_orphan_peering_to_remote_vnet(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.virtual_networks.list.return_value = make_pageable([_vnet()])
    network_client.network_security_groups.list.return_value = make_pageable([])
    network_client.route_tables.list.return_value = make_pageable([])
    network_client.nat_gateways.list.return_value = make_pageable([])
    network_client.network_interfaces.list.return_value = make_pageable([])
    network_client.public_ip_addresses.list.return_value = make_pageable([])
    network_client.subnets.list.return_value = make_pageable([_subnet(nsg_id=None)])
    network_client.virtual_network_peerings.list.return_value = make_pageable(
        [
            SimpleNamespace(
                id=f"{VNET_ID}/virtualNetworkPeerings/peer-1",
                name="peer-1",
                provisioning_state="Succeeded",
                remote_virtual_network=SimpleNamespace(id=REMOTE_VNET_ID),
                remote_address_space=SimpleNamespace(address_prefixes=[]),
                peering_state="Connected",
                peering_sync_level="FullyInSync",
                allow_virtual_network_access=True,
                allow_forwarded_traffic=False,
                allow_gateway_transit=False,
                use_remote_gateways=False,
            )
        ]
    )

    topology = get_vnet_topology(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    node_ids = {n.node_id for n in topology.nodes}
    assert REMOTE_VNET_ID not in node_ids
    edge_relationships = {(e.source_id, e.relationship) for e in topology.edges}
    assert any(rel == "peers_with_vnet" for (_, rel) in edge_relationships)
    assert any(w.code == "OUT_OF_SCOPE_TARGET" for w in topology.warnings)


def test_get_vnet_topology_node_and_edge_ordering_is_deterministic(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_full_topology(network_client)

    first = get_vnet_topology(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )
    second = get_vnet_topology(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    assert [n.node_id for n in first.nodes] == [n.node_id for n in second.nodes]
    assert [(e.source_id, e.target_id, e.relationship) for e in first.edges] == [
        (e.source_id, e.target_id, e.relationship) for e in second.edges
    ]
    node_types = [n.node_type for n in first.nodes]
    assert node_types == sorted(node_types)


def test_get_vnet_topology_records_api_call_count(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    _wire_full_topology(network_client)

    topology = get_vnet_topology(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        virtual_network_name="vnet-1",
    )

    assert topology.api_call_count > 0
