"""ARM service layer: public IP addresses and their resource associations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import PublicIpAddress

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_public_ip_addresses(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[PublicIpAddress]:
    """Call PublicIPAddressesOperations.list_all (whole subscription) or
    .list (one resource group).

    ``associated_resource_id`` is the ``id`` of whatever the public IP's
    ``ip_configuration`` field points at -- a NIC's IP configuration, a
    load balancer frontend configuration, or similar; ``None`` for an
    unassociated (unattached) public IP.
    """
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.public_ip_addresses,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.public_ip_addresses, "list_all", max_items=settings.max_page_results)

    result = []
    for pip in raw:
        parsed = parse_resource_id(pip.id)
        result.append(
            PublicIpAddress(
                resource_id=pip.id,
                name=pip.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=pip.location,
                provisioning_state=getattr(pip, "provisioning_state", None),
                tags=normalize_tags(pip.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/publicIPAddresses",
                ip_address=getattr(pip, "ip_address", None),
                public_ip_allocation_method=getattr(pip, "public_ip_allocation_method", None),
                public_ip_address_version=getattr(pip, "public_ip_address_version", None),
                sku_name=(pip.sku.name if pip.sku else None),
                idle_timeout_in_minutes=getattr(pip, "idle_timeout_in_minutes", None),
                associated_resource_id=(pip.ip_configuration.id if pip.ip_configuration else None),
            )
        )
    return result


__all__ = ["list_public_ip_addresses"]
