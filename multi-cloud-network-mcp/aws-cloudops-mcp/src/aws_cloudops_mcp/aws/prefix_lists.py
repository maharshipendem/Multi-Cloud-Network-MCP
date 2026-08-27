"""AWS service layer: customer-managed prefix lists."""

from __future__ import annotations

from typing import TYPE_CHECKING

from botocore.exceptions import ClientError

from aws_cloudops_mcp.aws.collection import CollectionResult, now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.common import CollectionWarning
from aws_cloudops_mcp.models.network_resources import ManagedPrefixList, ManagedPrefixListEntry

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _fetch_entries(
    client: object, prefix_list_id: str, *, max_items: int
) -> tuple[list[ManagedPrefixListEntry] | None, CollectionWarning | None]:
    try:
        raw_entries = paginate(
            client,
            "get_managed_prefix_list_entries",
            "Entries",
            max_items=max_items,
            PrefixListId=prefix_list_id,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        return None, CollectionWarning(
            resource_type="managed_prefix_list_entries",
            code="ENRICHMENT_FAILED",
            message=f"Could not fetch entries for {prefix_list_id}: {code}.",
        )
    return [
        ManagedPrefixListEntry(cidr=e["Cidr"], description=e.get("Description"))
        for e in raw_entries
    ], None


def list_managed_prefix_lists(
    client_factory: ClientFactory,
    *,
    region: str,
    include_entries: bool = False,
    prefix_list_ids: list[str] | None = None,
) -> CollectionResult:
    """Call ec2:DescribeManagedPrefixLists and return the normalized list.

    ``include_entries`` opts into fetching each prefix list's CIDR entries
    (one extra ``GetManagedPrefixListEntries`` call per prefix list --
    AWS has no batch API for this) up to ``Settings.max_fanout_calls``
    prefix lists; anything beyond that cap, or any fetch that fails, is
    recorded as a warning rather than silently omitted.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {"PrefixListIds": prefix_list_ids} if prefix_list_ids else {}
    raw = paginate(
        client,
        "describe_managed_prefix_lists",
        "PrefixLists",
        max_items=settings.max_page_results,
        **kwargs,
    )

    warnings: list[CollectionWarning] = []
    fanout_budget = settings.max_fanout_calls
    prefix_lists: list[ManagedPrefixList] = []
    for pl in raw:
        prefix_list_id = pl["PrefixListId"]
        entries: list[ManagedPrefixListEntry] | None = None
        if include_entries:
            if fanout_budget > 0:
                entries, warning = _fetch_entries(
                    client, prefix_list_id, max_items=settings.max_page_results
                )
                fanout_budget -= 1
                if warning:
                    warnings.append(warning)
            else:
                warnings.append(
                    CollectionWarning(
                        resource_type="managed_prefix_list_entries",
                        code="FANOUT_CAP_REACHED",
                        message=(
                            f"Skipped entry enrichment for {prefix_list_id}: "
                            f"max_fanout_calls ({settings.max_fanout_calls}) reached."
                        ),
                    )
                )

        prefix_lists.append(
            ManagedPrefixList(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                prefix_list_id=prefix_list_id,
                prefix_list_name=pl.get("PrefixListName"),
                state=pl.get("State"),
                address_family=pl.get("AddressFamily"),
                max_entries=pl.get("MaxEntries"),
                version=pl.get("Version"),
                owner_id=pl.get("OwnerId"),
                entries=entries,
                tags=normalize_tags(pl.get("Tags")),
            )
        )

    return CollectionResult(data=prefix_lists, warnings=warnings)
