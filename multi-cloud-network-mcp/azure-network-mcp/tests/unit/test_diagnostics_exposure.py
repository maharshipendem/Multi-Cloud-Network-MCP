from __future__ import annotations

from azure_network_mcp.diagnostics.exposure import find_exposed_network_interfaces
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from azure_network_mcp.models.network_resources import (
    NetworkInterface,
    NetworkInterfaceIpConfiguration,
    NetworkSecurityGroup,
    PublicIpAddress,
    SecurityRule,
)

SUB = "11111111-1111-1111-1111-111111111111"
RG = "rg-test"
BASE = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network"


def _base_snapshot(**overrides: object) -> HybridNetworkSnapshot:
    defaults: dict[str, object] = {
        "subscription_id": SUB,
        "resource_group": RG,
        "observed_at": "now",
    }
    defaults.update(overrides)
    return HybridNetworkSnapshot(**defaults)  # type: ignore[arg-type]


def _nic(with_public_ip: bool, nsg_id: str | None) -> NetworkInterface:
    return NetworkInterface(
        resource_id=f"{BASE}/networkInterfaces/nic-1",
        name="nic-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        ip_configurations=[
            NetworkInterfaceIpConfiguration(
                name="ipconfig1",
                private_ip_address="10.0.1.4",
                subnet_id=f"{BASE}/virtualNetworks/vnet-1/subnets/subnet-1",
                public_ip_address_id=(
                    f"{BASE}/publicIPAddresses/pip-1" if with_public_ip else None
                ),
                primary=True,
            )
        ],
        network_security_group_id=nsg_id,
    )


def _pip() -> PublicIpAddress:
    return PublicIpAddress(
        resource_id=f"{BASE}/publicIPAddresses/pip-1",
        name="pip-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        ip_address="20.1.2.3",
        associated_resource_id=f"{BASE}/networkInterfaces/nic-1/ipConfigurations/ipconfig1",
    )


def _nsg(rules: list[SecurityRule]) -> NetworkSecurityGroup:
    return NetworkSecurityGroup(
        resource_id=f"{BASE}/networkSecurityGroups/nsg-1",
        name="nsg-1",
        subscription_id=SUB,
        resource_group=RG,
        observed_at="now",
        security_rules=rules,
    )


def _wildcard_rule(*, port: str = "22") -> SecurityRule:
    return SecurityRule(
        resource_id=f"{BASE}/networkSecurityGroups/nsg-1/securityRules/AllowAny",
        name="AllowAny",
        subscription_id=SUB,
        observed_at="now",
        direction="Inbound",
        access="Allow",
        priority=100,
        protocol="Tcp",
        source_address_prefix="*",
        destination_port_range=port,
    )


def test_nic_with_public_ip_and_wildcard_nsg_rule_is_flagged() -> None:
    nsg = _nsg([_wildcard_rule(port="22")])
    snapshot = _base_snapshot(
        network_interfaces=[_nic(with_public_ip=True, nsg_id=nsg.resource_id)],
        public_ip_addresses=[_pip()],
        network_security_groups=[nsg],
    )

    findings = find_exposed_network_interfaces(snapshot)

    assert len(findings) == 1
    assert findings[0].severity == "high"  # port 22 is sensitive


def test_nic_with_public_ip_and_restricted_nsg_is_not_flagged() -> None:
    restricted_rule = SecurityRule(
        resource_id=f"{BASE}/networkSecurityGroups/nsg-1/securityRules/AllowOffice",
        name="AllowOffice",
        subscription_id=SUB,
        observed_at="now",
        direction="Inbound",
        access="Allow",
        priority=100,
        protocol="Tcp",
        source_address_prefix="203.0.113.0/24",
        destination_port_range="443",
    )
    nsg = _nsg([restricted_rule])
    snapshot = _base_snapshot(
        network_interfaces=[_nic(with_public_ip=True, nsg_id=nsg.resource_id)],
        public_ip_addresses=[_pip()],
        network_security_groups=[nsg],
    )

    findings = find_exposed_network_interfaces(snapshot)

    assert findings == []


def test_nic_without_public_ip_is_never_flagged() -> None:
    nsg = _nsg([_wildcard_rule()])
    snapshot = _base_snapshot(
        network_interfaces=[_nic(with_public_ip=False, nsg_id=nsg.resource_id)],
        public_ip_addresses=[],
        network_security_groups=[nsg],
    )

    findings = find_exposed_network_interfaces(snapshot)

    assert findings == []


def test_nic_with_public_ip_and_no_nsg_found_is_indeterminate() -> None:
    snapshot = _base_snapshot(
        network_interfaces=[_nic(with_public_ip=True, nsg_id=None)],
        public_ip_addresses=[_pip()],
        network_security_groups=[],
    )

    findings = find_exposed_network_interfaces(snapshot)

    assert len(findings) == 1
    assert findings[0].confidence == "indeterminate"


def test_wildcard_on_non_sensitive_port_is_medium_severity() -> None:
    nsg = _nsg([_wildcard_rule(port="8080")])
    snapshot = _base_snapshot(
        network_interfaces=[_nic(with_public_ip=True, nsg_id=nsg.resource_id)],
        public_ip_addresses=[_pip()],
        network_security_groups=[nsg],
    )

    findings = find_exposed_network_interfaces(snapshot)

    assert findings[0].severity == "medium"
