"""ARM service layer: Private Endpoints, Private Link Services, and
service endpoint policies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import parse_resource_id
from azure_network_mcp.models.private_link import (
    PrivateEndpoint,
    PrivateLinkService,
    PrivateLinkServiceConnectionSummary,
    ServiceEndpointPolicy,
)

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_private_endpoints(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[PrivateEndpoint]:
    """Call PrivateEndpointsOperations.list (one resource group) or
    .list_by_subscription (whole subscription)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.private_endpoints,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(
            client.private_endpoints, "list_by_subscription", max_items=settings.max_page_results
        )

    result = []
    for pe in raw:
        parsed = parse_resource_id(pe.id)
        connections = list(getattr(pe, "private_link_service_connections", None) or []) + list(
            getattr(pe, "manual_private_link_service_connections", None) or []
        )
        result.append(
            PrivateEndpoint(
                resource_id=pe.id,
                name=pe.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=pe.location,
                provisioning_state=getattr(pe, "provisioning_state", None),
                tags=normalize_tags(pe.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/privateEndpoints",
                subnet_id=(pe.subnet.id if getattr(pe, "subnet", None) else None),
                network_interface_ids=[
                    n.id for n in (pe.network_interfaces or []) if getattr(n, "id", None)
                ],
                private_link_service_connections=[
                    PrivateLinkServiceConnectionSummary(
                        name=c.name,
                        private_link_service_id=getattr(c, "private_link_service_id", None),
                        group_ids=list(getattr(c, "group_ids", None) or []),
                        connection_state=(
                            getattr(c.private_link_service_connection_state, "status", None)
                            if getattr(c, "private_link_service_connection_state", None)
                            else None
                        ),
                    )
                    for c in connections
                ],
            )
        )
    return result


def list_private_link_services(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[PrivateLinkService]:
    """Call PrivateLinkServicesOperations.list (one resource group) or
    .list_by_subscription (whole subscription)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.private_link_services,
            "list",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(
            client.private_link_services,
            "list_by_subscription",
            max_items=settings.max_page_results,
        )

    result = []
    for pls in raw:
        parsed = parse_resource_id(pls.id)
        result.append(
            PrivateLinkService(
                resource_id=pls.id,
                name=pls.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=pls.location,
                provisioning_state=getattr(pls, "provisioning_state", None),
                tags=normalize_tags(pls.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/privateLinkServices",
                alias=getattr(pls, "alias", None),
                visibility=(
                    ",".join(getattr(pls.visibility, "subscriptions", None) or [])
                    if getattr(pls, "visibility", None)
                    else None
                ),
                auto_approval=(
                    ",".join(getattr(pls.auto_approval, "subscriptions", None) or [])
                    if getattr(pls, "auto_approval", None)
                    else None
                ),
                fqdns=list(getattr(pls, "fqdns", None) or []),
                load_balancer_frontend_ip_configuration_ids=[
                    f.id
                    for f in (getattr(pls, "load_balancer_frontend_ip_configurations", None) or [])
                    if getattr(f, "id", None)
                ],
                private_endpoint_connection_count=len(
                    getattr(pls, "private_endpoint_connections", None) or []
                ),
                enable_proxy_protocol=getattr(pls, "enable_proxy_protocol", None),
            )
        )
    return result


def list_service_endpoint_policies(
    client_factory: ClientFactory, *, subscription_id: str, resource_group: str | None = None
) -> list[ServiceEndpointPolicy]:
    """Call ServiceEndpointPoliciesOperations.list (whole subscription) or
    .list_by_resource_group (one resource group)."""
    client = client_factory.get_network_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    if resource_group:
        raw = paginate(
            client.service_endpoint_policies,
            "list_by_resource_group",
            max_items=settings.max_page_results,
            resource_group_name=resource_group,
        )
    else:
        raw = paginate(
            client.service_endpoint_policies, "list", max_items=settings.max_page_results
        )

    result = []
    for policy in raw:
        parsed = parse_resource_id(policy.id)
        result.append(
            ServiceEndpointPolicy(
                resource_id=policy.id,
                name=policy.name,
                subscription_id=parsed.subscription_id or subscription_id,
                resource_group=parsed.resource_group,
                location=policy.location,
                provisioning_state=getattr(policy, "provisioning_state", None),
                tags=normalize_tags(policy.tags),
                observed_at=observed_at,
                source_api="Microsoft.Network/serviceEndpointPolicies",
                service_alias=getattr(policy, "service_alias", None),
                subnet_ids=[
                    s.id for s in (getattr(policy, "subnets", None) or []) if getattr(s, "id", None)
                ],
                definition_count=len(
                    getattr(policy, "service_endpoint_policy_definitions", None) or []
                ),
            )
        )
    return result


__all__ = [
    "list_private_endpoints",
    "list_private_link_services",
    "list_service_endpoint_policies",
]
