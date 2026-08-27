"""ARM service layer: load balancers and application gateways inventory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.network_resources import (
    ApplicationGateway,
    ApplicationGatewayListener,
    BackendAddressPool,
    FrontendIpConfiguration,
    LoadBalancer,
    LoadBalancingRule,
    Probe,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_load_balancers(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[LoadBalancer]:
    """Call LoadBalancersOperations.list_all (whole subscription) or
    .list (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.load_balancers,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.load_balancers, "list_all", max_items=settings.max_page_results)

    result = []
    for lb in raw:
        parsed = parse_resource_id(lb.id)
        result.append(
            LoadBalancer(
                resource_id=lb.id,
                name=lb.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=lb.location,
                provisioning_state=getattr(lb, "provisioning_state", None),
                tags=normalize_tags(lb.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/loadBalancers",
                sku_name=(lb.sku.name if lb.sku else None),
                sku_tier=(lb.sku.tier if lb.sku else None),
                frontend_ip_configurations=[
                    FrontendIpConfiguration(
                        name=f.name,
                        private_ip_address=getattr(f, "private_ip_address", None),
                        public_ip_address_id=(
                            f.public_ip_address.id if f.public_ip_address else None
                        ),
                        subnet_id=(f.subnet.id if f.subnet else None),
                    )
                    for f in (lb.frontend_ip_configurations or [])
                ],
                backend_address_pools=[
                    BackendAddressPool(
                        name=p.name,
                        backend_ip_configuration_ids=[
                            c.id
                            for c in (p.backend_ip_configurations or [])
                            if getattr(c, "id", None)
                        ],
                    )
                    for p in (lb.backend_address_pools or [])
                ],
                load_balancing_rules=[
                    LoadBalancingRule(
                        name=r.name,
                        protocol=getattr(r, "protocol", None),
                        frontend_port=getattr(r, "frontend_port", None),
                        backend_port=getattr(r, "backend_port", None),
                        frontend_ip_configuration_id=(
                            r.frontend_ip_configuration.id if r.frontend_ip_configuration else None
                        ),
                        backend_address_pool_id=(
                            r.backend_address_pool.id if r.backend_address_pool else None
                        ),
                    )
                    for r in (lb.load_balancing_rules or [])
                ],
                probes=[
                    Probe(
                        name=p.name,
                        protocol=getattr(p, "protocol", None),
                        port=getattr(p, "port", None),
                        request_path=getattr(p, "request_path", None),
                    )
                    for p in (lb.probes or [])
                ],
            )
        )
    return result


def list_application_gateways(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[ApplicationGateway]:
    """Call ApplicationGatewaysOperations.list_all (whole subscription)
    or .list (one resource group). Summary-level inventory only (SKU,
    listeners, operational/provisioning state) -- WAF policy, rewrite
    rules, and routing-rule detail are out of this milestone's scope.
    """
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.application_gateways,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(client.application_gateways, "list_all", max_items=settings.max_page_results)

    result = []
    for gw in raw:
        parsed = parse_resource_id(gw.id)
        listeners = list(gw.http_listeners or []) or list(gw.listeners or [])
        result.append(
            ApplicationGateway(
                resource_id=gw.id,
                name=gw.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=gw.location,
                provisioning_state=getattr(gw, "provisioning_state", None),
                tags=normalize_tags(gw.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/applicationGateways",
                sku_name=(gw.sku.name if gw.sku else None),
                sku_tier=(gw.sku.tier if gw.sku else None),
                sku_capacity=(gw.sku.capacity if gw.sku else None),
                operational_state=getattr(gw, "operational_state", None),
                listeners=[
                    ApplicationGatewayListener(
                        name=listener.name,
                        protocol=getattr(listener, "protocol", None),
                        frontend_ip_configuration_id=(
                            listener.frontend_ip_configuration.id
                            if getattr(listener, "frontend_ip_configuration", None)
                            else None
                        ),
                        frontend_port_id=(
                            listener.frontend_port.id
                            if getattr(listener, "frontend_port", None)
                            else None
                        ),
                    )
                    for listener in listeners
                ],
                backend_address_pool_names=[
                    p.name for p in (gw.backend_address_pools or []) if p.name
                ],
            )
        )
    return result


__all__ = ["list_application_gateways", "list_load_balancers"]
