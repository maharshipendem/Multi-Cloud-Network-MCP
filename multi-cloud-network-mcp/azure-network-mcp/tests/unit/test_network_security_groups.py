from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import RESOURCE_GROUP, SUBSCRIPTION_ID, make_pageable

from azure_network_mcp.arm.client_factory import ClientFactory
from azure_network_mcp.arm.network_security_groups import (
    get_effective_network_security_groups,
    list_network_security_groups,
    list_security_rules,
)

NSG_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/"
    "Microsoft.Network/networkSecurityGroups/nsg-1"
)


def _rule(
    name: str, priority: int, access: str, direction: str, rule_id: str | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        id=rule_id,
        name=name,
        provisioning_state="Succeeded",
        protocol="Tcp",
        source_port_range="*",
        source_port_ranges=[],
        destination_port_range="443",
        destination_port_ranges=[],
        source_address_prefix="*",
        source_address_prefixes=[],
        destination_address_prefix="*",
        destination_address_prefixes=[],
        access=access,
        priority=priority,
        direction=direction,
        description=None,
    )


def _nsg() -> SimpleNamespace:
    return SimpleNamespace(
        id=NSG_ID,
        name="nsg-1",
        location="eastus",
        provisioning_state="Succeeded",
        tags={},
        security_rules=[_rule("AllowHttps", 100, "Allow", "Inbound")],
        default_security_rules=[
            _rule("AllowVnetInBound", 65000, "Allow", "Inbound"),
            _rule("DenyAllInBound", 65500, "Deny", "Inbound"),
        ],
        network_interfaces=[],
        subnets=[],
    )


def test_list_network_security_groups_keeps_custom_and_default_rules_separate(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.network_security_groups.list_all.return_value = make_pageable([_nsg()])

    result = list_network_security_groups(client_factory, subscription_id=SUBSCRIPTION_ID)

    nsg = result[0]
    assert [r.name for r in nsg.security_rules] == ["AllowHttps"]
    assert [r.name for r in nsg.default_security_rules] == ["AllowVnetInBound", "DenyAllInBound"]
    assert nsg.security_rules[0].priority == 100
    assert nsg.default_security_rules[1].priority == 65500
    assert nsg.default_security_rules[1].access == "Deny"


def test_list_security_rules_returns_custom_rules_only(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    network_client.security_rules.list.return_value = make_pageable(
        [_rule("AllowHttps", 100, "Allow", "Inbound", rule_id=f"{NSG_ID}/securityRules/AllowHttps")]
    )

    result = list_security_rules(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_security_group_name="nsg-1",
    )

    assert result[0].name == "AllowHttps"
    assert result[0].resource_group == RESOURCE_GROUP


def test_get_effective_network_security_groups_expands_asg_prefixes(
    client_factory: ClientFactory, network_client: MagicMock
) -> None:
    poller = MagicMock()
    poller.result.return_value = SimpleNamespace(
        value=[
            SimpleNamespace(
                network_security_group=SimpleNamespace(id=NSG_ID),
                effective_security_rules=[
                    SimpleNamespace(
                        name="AllowHttps",
                        protocol="Tcp",
                        source_port_ranges=["*"],
                        destination_port_ranges=["443"],
                        source_address_prefixes=[],
                        destination_address_prefixes=[],
                        expanded_source_address_prefix=["10.0.0.0/24", "10.0.1.0/24"],
                        expanded_destination_address_prefix=["10.0.2.0/24"],
                        access="Allow",
                        priority=100,
                        direction="Inbound",
                    )
                ],
            )
        ]
    )
    network_client.network_interfaces.begin_list_effective_network_security_groups.return_value = (
        poller
    )

    result = get_effective_network_security_groups(
        client_factory,
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        network_interface_name="nic-1",
    )

    assert result[0].network_security_group_id == NSG_ID
    rule = result[0].effective_security_rules[0]
    assert rule.expanded_source_address_prefix == ["10.0.0.0/24", "10.0.1.0/24"]
    assert rule.expanded_destination_address_prefix == ["10.0.2.0/24"]
