"""ARM service layer: network interfaces and their IP configurations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import (
    NetworkInterface,
    NetworkInterfaceIpConfiguration,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_network_interfaces(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[NetworkInterface]:
    """Call NetworkInterfacesOperations.list_all (whole subscription) or
    .list (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.network_interfaces,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.network_interfaces, "list_all", max_items=settings.max_page_results)

    result = []
    for nic in raw:
        parsed = parse_resource_id(nic.id)
        result.append(
            NetworkInterface(
                resource_id=nic.id,
                name=nic.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=nic.location,
                provisioning_state=getattr(nic, "provisioning_state", None),
                tags=normalize_tags(nic.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/networkInterfaces",
                ip_configurations=[
                    NetworkInterfaceIpConfiguration(
                        name=ipc.name,
                        private_ip_address=getattr(ipc, "private_ip_address", None),
                        private_ip_allocation_method=getattr(
                            ipc, "private_ip_allocation_method", None
                        ),
                        subnet_id=(ipc.subnet.id if ipc.subnet else None),
                        public_ip_address_id=(
                            ipc.public_ip_address.id if ipc.public_ip_address else None
                        ),
                        primary=getattr(ipc, "primary", None),
                    )
                    for ipc in (nic.ip_configurations or [])
                ],
                network_security_group_id=(
                    nic.network_security_group.id if nic.network_security_group else None
                ),
                mac_address=getattr(nic, "mac_address", None),
                primary=getattr(nic, "primary", None),
                enable_ip_forwarding=getattr(nic, "enable_ip_forwarding", None),
                enable_accelerated_networking=getattr(nic, "enable_accelerated_networking", None),
                virtual_machine_id=(nic.virtual_machine.id if nic.virtual_machine else None),
            )
        )
    return result


__all__ = ["list_network_interfaces"]
