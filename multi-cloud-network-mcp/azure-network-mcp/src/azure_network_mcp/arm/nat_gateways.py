"""ARM service layer: NAT gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import NatGateway

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_nat_gateways(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[NatGateway]:
    """Call NatGatewaysOperations.list_all (whole subscription) or .list
    (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.nat_gateways,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.nat_gateways, "list_all", max_items=settings.max_page_results)

    result = []
    for gw in raw:
        parsed = parse_resource_id(gw.id)
        result.append(
            NatGateway(
                resource_id=gw.id,
                name=gw.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=gw.location,
                provisioning_state=getattr(gw, "provisioning_state", None),
                tags=normalize_tags(gw.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/natGateways",
                sku_name=(gw.sku.name if gw.sku else None),
                idle_timeout_in_minutes=getattr(gw, "idle_timeout_in_minutes", None),
                public_ip_address_ids=[p.id for p in (gw.public_ip_addresses or []) if p.id],
                subnet_ids=[s.id for s in (gw.subnets or []) if s.id],
            )
        )
    return result


__all__ = ["list_nat_gateways"]
