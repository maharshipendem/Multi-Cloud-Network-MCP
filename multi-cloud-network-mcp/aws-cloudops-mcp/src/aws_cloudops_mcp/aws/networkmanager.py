"""AWS service layer: Network Manager and Cloud WAN.

Both share the ``networkmanager`` boto3 client. ``describe_global_networks``
and the ``get_*`` calls for sites/devices/links/connections/registrations
are genuinely global-scope AWS resources reached through a single regional
API endpoint (``us-east-1`` unless the account opted into another home
Region) -- every record here is stamped ``scope="global"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from botocore.exceptions import ClientError

from aws_cloudops_mcp.aws.collection import CollectionResult, now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.common import CollectionWarning
from aws_cloudops_mcp.models.network_resources import MAX_POLICY_DOCUMENT_CHARS
from aws_cloudops_mcp.models.networkmanager import (
    CoreNetwork,
    CoreNetworkEdge,
    CoreNetworkSegment,
    GlobalNetwork,
    LinkBandwidth,
    NetworkManagerConnection,
    NetworkManagerDevice,
    NetworkManagerLink,
    NetworkManagerSite,
    SiteLocation,
    TransitGatewayRegistration,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def list_core_networks(
    client_factory: ClientFactory,
    *,
    region: str,
    include_details: bool = False,
    include_policy: bool = False,
) -> CollectionResult:
    """Call networkmanager:ListCoreNetworks and return the normalized list.

    Cloud WAN may be entirely unused/unavailable for an account; an empty
    list is the normal, non-error result in that case. ``include_details``
    opts into one extra ``GetCoreNetwork`` call per core network (segments/
    edges, bounded by ``Settings.max_fanout_calls``); ``include_policy``
    further opts into ``GetCoreNetworkPolicy`` (size-capped like VPC
    endpoint policies). If either enrichment call fails for a reason
    suggesting the capability itself is unsupported for this account/SDK
    (rather than a transient error), that core network's
    ``collection_completeness`` is set to ``"partial"`` with an explicit
    ``UNSUPPORTED_CAPABILITY`` warning instead of raising.
    """
    validate_region_format(region)
    client = client_factory.get_client("networkmanager", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client, "list_core_networks", "CoreNetworks", max_items=settings.max_page_results
    )
    warnings: list[CollectionWarning] = []
    fanout_budget = settings.max_fanout_calls
    core_networks = []
    for cn in raw:
        core_network_id = cn["CoreNetworkId"]
        completeness = "complete"
        segments: list[CoreNetworkSegment] | None = None
        edges: list[CoreNetworkEdge] | None = None
        policy_document: str | None = None
        policy_truncated = False

        if include_details:
            if fanout_budget > 0:
                try:
                    detail = call_readonly(
                        client, "get_core_network", CoreNetworkId=core_network_id
                    )
                    segments = [
                        CoreNetworkSegment(
                            name=s.get("Name"), edge_locations=s.get("EdgeLocations", [])
                        )
                        for s in detail.get("CoreNetwork", {}).get("Segments", [])
                    ]
                    edges = [
                        CoreNetworkEdge(edge_location=e.get("EdgeLocation"), asn=e.get("Asn"))
                        for e in detail.get("CoreNetwork", {}).get("Edges", [])
                    ]
                    fanout_budget -= 1
                except ClientError as exc:
                    completeness = "partial"
                    code = exc.response.get("Error", {}).get("Code", "Unknown")
                    warnings.append(
                        CollectionWarning(
                            resource_type="core_network_details",
                            code="UNSUPPORTED_CAPABILITY",
                            message=f"Could not fetch details for {core_network_id}: {code}.",
                        )
                    )
            else:
                completeness = "partial"
                warnings.append(
                    CollectionWarning(
                        resource_type="core_network_details",
                        code="FANOUT_CAP_REACHED",
                        message=(
                            f"Skipped detail enrichment for {core_network_id}: "
                            f"max_fanout_calls ({settings.max_fanout_calls}) reached."
                        ),
                    )
                )

        if include_policy and fanout_budget > 0:
            try:
                policy_response = call_readonly(
                    client, "get_core_network_policy", CoreNetworkId=core_network_id
                )
                doc = policy_response.get("CoreNetworkPolicy", {}).get("PolicyDocument")
                if doc:
                    doc_str = doc if isinstance(doc, str) else str(doc)
                    if len(doc_str) > MAX_POLICY_DOCUMENT_CHARS:
                        policy_document, policy_truncated = (
                            doc_str[:MAX_POLICY_DOCUMENT_CHARS],
                            True,
                        )
                    else:
                        policy_document = doc_str
                fanout_budget -= 1
            except ClientError as exc:
                completeness = "partial"
                code = exc.response.get("Error", {}).get("Code", "Unknown")
                warnings.append(
                    CollectionWarning(
                        resource_type="core_network_policy",
                        code="UNSUPPORTED_CAPABILITY",
                        message=f"Could not fetch policy for {core_network_id}: {code}.",
                    )
                )
        elif include_policy:
            completeness = "partial"
            warnings.append(
                CollectionWarning(
                    resource_type="core_network_policy",
                    code="FANOUT_CAP_REACHED",
                    message=(
                        f"Skipped policy enrichment for {core_network_id}: "
                        f"max_fanout_calls ({settings.max_fanout_calls}) reached."
                    ),
                )
            )

        core_networks.append(
            CoreNetwork(
                account_id=account_id,
                region=region,
                scope="global",
                observed_at=observed_at,
                source_api="networkmanager:ListCoreNetworks",
                collection_completeness=completeness,
                core_network_id=core_network_id,
                core_network_arn=cn.get("CoreNetworkArn"),
                global_network_id=cn.get("GlobalNetworkId"),
                owner_account_id=cn.get("OwnerAccountId"),
                state=cn.get("State", ""),
                description=cn.get("Description"),
                segments=segments,
                edges=edges,
                policy_document=policy_document,
                policy_document_truncated=policy_truncated,
                tags=normalize_tags(cn.get("Tags")),
            )
        )

    return CollectionResult(data=core_networks, warnings=warnings)


def list_global_networks(
    client_factory: ClientFactory, *, region: str, global_network_ids: list[str] | None = None
) -> list[GlobalNetwork]:
    """Call networkmanager:DescribeGlobalNetworks and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("networkmanager", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs = {"GlobalNetworkIds": global_network_ids} if global_network_ids else {}
    raw = paginate(
        client,
        "describe_global_networks",
        "GlobalNetworks",
        max_items=settings.max_page_results,
        **kwargs,
    )
    return [
        GlobalNetwork(
            account_id=account_id,
            region=region,
            scope="global",
            observed_at=observed_at,
            source_api="networkmanager:DescribeGlobalNetworks",
            global_network_id=gn["GlobalNetworkId"],
            global_network_arn=gn.get("GlobalNetworkArn"),
            description=gn.get("Description"),
            state=gn.get("State", ""),
            tags=normalize_tags(gn.get("Tags")),
        )
        for gn in raw
    ]


def list_network_manager_sites(
    client_factory: ClientFactory, *, region: str, global_network_id: str
) -> list[NetworkManagerSite]:
    """Call networkmanager:GetSites and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("networkmanager", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "get_sites",
        "Sites",
        max_items=settings.max_page_results,
        GlobalNetworkId=global_network_id,
    )
    result = []
    for site in raw:
        loc = site.get("Location") or {}
        result.append(
            NetworkManagerSite(
                account_id=account_id,
                region=region,
                scope="global",
                observed_at=observed_at,
                source_api="networkmanager:GetSites",
                site_id=site["SiteId"],
                global_network_id=global_network_id,
                description=site.get("Description"),
                location=SiteLocation(
                    address=loc.get("Address"),
                    latitude=loc.get("Latitude"),
                    longitude=loc.get("Longitude"),
                )
                if loc
                else None,
                state=site.get("State", ""),
                tags=normalize_tags(site.get("Tags")),
            )
        )
    return result


def list_network_manager_devices(
    client_factory: ClientFactory, *, region: str, global_network_id: str
) -> list[NetworkManagerDevice]:
    """Call networkmanager:GetDevices and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("networkmanager", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "get_devices",
        "Devices",
        max_items=settings.max_page_results,
        GlobalNetworkId=global_network_id,
    )
    return [
        NetworkManagerDevice(
            account_id=account_id,
            region=region,
            scope="global",
            observed_at=observed_at,
            source_api="networkmanager:GetDevices",
            device_id=d["DeviceId"],
            global_network_id=global_network_id,
            site_id=d.get("SiteId"),
            description=d.get("Description"),
            device_type=d.get("Type"),
            vendor=d.get("Vendor"),
            model=d.get("Model"),
            state=d.get("State", ""),
            tags=normalize_tags(d.get("Tags")),
        )
        for d in raw
    ]


def list_network_manager_links(
    client_factory: ClientFactory, *, region: str, global_network_id: str
) -> list[NetworkManagerLink]:
    """Call networkmanager:GetLinks and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("networkmanager", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "get_links",
        "Links",
        max_items=settings.max_page_results,
        GlobalNetworkId=global_network_id,
    )
    result = []
    for link in raw:
        bw = link.get("Bandwidth") or {}
        result.append(
            NetworkManagerLink(
                account_id=account_id,
                region=region,
                scope="global",
                observed_at=observed_at,
                source_api="networkmanager:GetLinks",
                link_id=link["LinkId"],
                global_network_id=global_network_id,
                site_id=link.get("SiteId"),
                description=link.get("Description"),
                link_type=link.get("Type"),
                bandwidth=LinkBandwidth(
                    upload_speed=bw.get("UploadSpeed"), download_speed=bw.get("DownloadSpeed")
                )
                if bw
                else None,
                provider=link.get("Provider"),
                state=link.get("State", ""),
                tags=normalize_tags(link.get("Tags")),
            )
        )
    return result


def list_network_manager_connections(
    client_factory: ClientFactory, *, region: str, global_network_id: str
) -> list[NetworkManagerConnection]:
    """Call networkmanager:GetConnections and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("networkmanager", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "get_connections",
        "Connections",
        max_items=settings.max_page_results,
        GlobalNetworkId=global_network_id,
    )
    return [
        NetworkManagerConnection(
            account_id=account_id,
            region=region,
            scope="global",
            observed_at=observed_at,
            source_api="networkmanager:GetConnections",
            connection_id=c["ConnectionId"],
            global_network_id=global_network_id,
            device_id=c.get("DeviceId"),
            connected_device_id=c.get("ConnectedDeviceId"),
            link_id=c.get("LinkId"),
            connected_link_id=c.get("ConnectedLinkId"),
            description=c.get("Description"),
            state=c.get("State", ""),
            tags=normalize_tags(c.get("Tags")),
        )
        for c in raw
    ]


def list_transit_gateway_registrations(
    client_factory: ClientFactory, *, region: str, global_network_id: str
) -> list[TransitGatewayRegistration]:
    """Call networkmanager:GetTransitGatewayRegistrations and return the normalized list."""
    validate_region_format(region)
    client = client_factory.get_client("networkmanager", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    raw = paginate(
        client,
        "get_transit_gateway_registrations",
        "TransitGatewayRegistrations",
        max_items=settings.max_page_results,
        GlobalNetworkId=global_network_id,
    )
    result = []
    for reg in raw:
        state = reg.get("State") or {}
        result.append(
            TransitGatewayRegistration(
                account_id=account_id,
                region=region,
                scope="global",
                observed_at=observed_at,
                source_api="networkmanager:GetTransitGatewayRegistrations",
                global_network_id=global_network_id,
                transit_gateway_arn=reg.get("TransitGatewayArn", ""),
                state=state.get("Code", ""),
                state_message=state.get("Message"),
            )
        )
    return result
