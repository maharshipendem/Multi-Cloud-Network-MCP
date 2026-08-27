"""ARM service layer: resource groups, with an optional network-focused filter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from azure_network_mcp.arm.collection import CollectionResult, now_iso
from azure_network_mcp.arm.pagination import paginate
from azure_network_mcp.arm.tags import normalize_tags
from azure_network_mcp.models.common import CollectionWarning
from azure_network_mcp.models.subscriptions import ResourceGroup

if TYPE_CHECKING:
    from azure_network_mcp.arm.client_factory import ClientFactory


def list_resource_groups(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    name_contains: str | None = None,
    only_with_network_resources: bool = False,
) -> CollectionResult:
    """Call ResourceGroupsOperations.list.

    ``name_contains`` is a client-side substring filter (ARM's own
    ``$filter`` only supports exact tag-name/value equality, not a
    resource-group-name search). ``only_with_network_resources`` opts
    into one extra ``Resources.list_by_resource_group`` call per
    resource group (bounded by ``Settings.max_fanout_calls``, since ARM
    has no single call that answers "which resource groups contain a
    Microsoft.Network resource") to keep only groups containing at least
    one resource whose type starts with ``Microsoft.Network/``.
    """
    resource_client = client_factory.get_resource_client(subscription_id)
    settings = client_factory.settings
    observed_at = now_iso()

    raw = paginate(resource_client.resource_groups, "list", max_items=settings.max_page_results)
    groups = [
        ResourceGroup(
            resource_id=g.id,
            name=g.name,
            subscription_id=subscription_id,
            location=g.location,
            provisioning_state=(g.properties.provisioning_state if g.properties else None),
            tags=normalize_tags(g.tags),
            observed_at=observed_at,
            source_api="Microsoft.Resources/resourceGroups:list",
            managed_by=g.managed_by,
        )
        for g in raw
        if g.id and g.name
    ]

    if name_contains:
        needle = name_contains.lower()
        groups = [g for g in groups if needle in g.name.lower()]

    warnings: list[CollectionWarning] = []
    if only_with_network_resources:
        fanout_budget = settings.max_fanout_calls
        kept: list[ResourceGroup] = []
        for group in groups:
            if fanout_budget <= 0:
                warnings.append(
                    CollectionWarning(
                        resource_type="resource_group",
                        code="FANOUT_CAP_REACHED",
                        message=(
                            f"Skipped network-resource check for {group.name}: "
                            f"max_fanout_calls ({settings.max_fanout_calls}) reached -- "
                            "included in results without filtering."
                        ),
                    )
                )
                kept.append(group)
                continue
            resources = paginate(
                resource_client.resources,
                "list_by_resource_group",
                max_items=settings.max_page_results,
                resource_group_name=group.name,
            )
            fanout_budget -= 1
            if any((r.type or "").startswith("Microsoft.Network/") for r in resources):
                kept.append(group)
        groups = kept

    return CollectionResult(data=groups, warnings=warnings)


__all__ = ["list_resource_groups"]
