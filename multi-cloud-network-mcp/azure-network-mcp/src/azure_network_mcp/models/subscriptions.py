"""Normalized models for subscriptions, tenants, locations, and resource
groups -- the ARM scoping hierarchy every other resource type sits under."""

from __future__ import annotations

from pydantic import BaseModel

from azure_network_mcp.models.common import AzureResource, Tags


class Subscription(BaseModel):
    """Normalized entry from SubscriptionClient.subscriptions.list/get.

    Not an ``AzureResource`` -- a subscription has no resource group or
    Azure region of its own; it *is* the top of that scoping hierarchy.
    """

    subscription_id: str
    display_name: str | None = None
    state: str | None = None
    tenant_id: str | None = None


class Tenant(BaseModel):
    """Normalized entry from SubscriptionClient.tenants.list."""

    tenant_id: str


class Location(BaseModel):
    """Normalized entry from SubscriptionClient.subscriptions.list_locations."""

    name: str
    display_name: str | None = None
    subscription_id: str


class ResourceGroup(AzureResource):
    """Normalized entry from ResourceManagementClient.resource_groups.list/get."""

    managed_by: str | None = None


__all__ = ["Location", "ResourceGroup", "Subscription", "Tags", "Tenant"]
