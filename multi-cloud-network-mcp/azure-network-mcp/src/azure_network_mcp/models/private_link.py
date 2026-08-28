"""Normalized models for Private Endpoints, Private Link Services, and
service endpoint policies."""

from __future__ import annotations

from pydantic import BaseModel, Field

from azure_network_mcp.models.common import AzureResource


class PrivateLinkServiceConnectionSummary(BaseModel):
    name: str | None = None
    private_link_service_id: str | None = None
    group_ids: list[str] = Field(default_factory=list)
    connection_state: str | None = None


class PrivateEndpoint(AzureResource):
    """Normalized entry from PrivateEndpointsOperations.list/list_by_subscription/get."""

    subnet_id: str | None = None
    network_interface_ids: list[str] = Field(default_factory=list)
    private_link_service_connections: list[PrivateLinkServiceConnectionSummary] = Field(
        default_factory=list
    )


class PrivateLinkService(AzureResource):
    """Normalized entry from PrivateLinkServicesOperations.list/list_by_subscription/get."""

    alias: str | None = None
    visibility: str | None = None
    auto_approval: str | None = None
    fqdns: list[str] = Field(default_factory=list)
    load_balancer_frontend_ip_configuration_ids: list[str] = Field(default_factory=list)
    private_endpoint_connection_count: int = 0
    enable_proxy_protocol: bool | None = None


class ServiceEndpointPolicy(AzureResource):
    """Normalized entry from ServiceEndpointPoliciesOperations.list/get."""

    service_alias: str | None = None
    subnet_ids: list[str] = Field(default_factory=list)
    definition_count: int = 0


__all__ = [
    "PrivateEndpoint",
    "PrivateLinkService",
    "PrivateLinkServiceConnectionSummary",
    "ServiceEndpointPolicy",
]
