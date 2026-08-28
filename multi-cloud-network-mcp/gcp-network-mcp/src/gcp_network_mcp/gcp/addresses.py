"""Service-layer functions for reserved IP Addresses (regional and global)."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate, paginate_aggregated
from gcp_network_mcp.models.addresses import AddressSummary
from gcp_network_mcp.models.common import parse_self_link


def normalize_address(
    address: compute_v1.Address,
    *,
    project_id: str,
    source_api: str = "AddressesClient.aggregated_list",
) -> AddressSummary:
    parsed = parse_self_link(address.self_link) if address.self_link else None
    return AddressSummary(
        self_link=address.self_link or None,
        id=str(address.id) if address.id else None,
        name=address.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        address=address.address,
        address_type=address.address_type or None,
        prefix_length=address.prefix_length or None,
        status=address.status or None,
        purpose=address.purpose or None,
        network_self_link=address.network or None,
        subnetwork_self_link=address.subnetwork or None,
        network_tier=address.network_tier or None,
        users=list(address.users),
        observed_at=now_iso(),
        source_api=source_api,
    )


def list_regional_addresses(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.addresses(),
        "aggregated_list",
        items_field="addresses",
        resource_type="address",
        project_id=project_id,
        project=project_id,
    )
    data = [normalize_address(a, project_id=project_id) for a in raw]
    return CollectionResult(data=data, warnings=warnings)


def list_global_addresses(
    client_factory: ClientFactory, *, project_id: str
) -> list[AddressSummary]:
    raw = paginate(
        client_factory.global_addresses(),
        "list",
        resource_type="global_address",
        project_id=project_id,
        project=project_id,
    )
    return [
        normalize_address(a, project_id=project_id, source_api="GlobalAddressesClient.list")
        for a in raw
    ]


__all__ = ["list_global_addresses", "list_regional_addresses", "normalize_address"]
