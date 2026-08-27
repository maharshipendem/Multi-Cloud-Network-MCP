"""AWS service layer: VPC endpoints and endpoint services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cloudops_mcp.aws.collection import now_iso
from aws_cloudops_mcp.aws.filters import vpc_filter
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.network_resources import (
    MAX_POLICY_DOCUMENT_CHARS,
    VpcEndpoint,
    VpcEndpointDnsEntry,
    VpcEndpointService,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def _normalize_policy(raw_policy: str | None, *, include_policies: bool) -> tuple[str | None, bool]:
    if not include_policies or not raw_policy:
        return None, False
    if len(raw_policy) > MAX_POLICY_DOCUMENT_CHARS:
        return raw_policy[:MAX_POLICY_DOCUMENT_CHARS], True
    return raw_policy, False


def list_vpc_endpoints(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    vpc_endpoint_ids: list[str] | None = None,
    include_policies: bool = False,
) -> list[VpcEndpoint]:
    """Call ec2:DescribeVpcEndpoints and return the normalized list.

    ``policy_document`` is omitted entirely unless ``include_policies`` is
    set, and even then is truncated past ``MAX_POLICY_DOCUMENT_CHARS``
    (``policy_document_truncated=True``) rather than returned in full --
    policy documents can be large, and this tool is a read-only inventory,
    not a policy-authoring surface.
    """
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = dict(vpc_filter(vpc_id))
    if vpc_endpoint_ids:
        kwargs["VpcEndpointIds"] = vpc_endpoint_ids

    raw = paginate(
        client,
        "describe_vpc_endpoints",
        "VpcEndpoints",
        max_items=settings.max_page_results,
        **kwargs,
    )
    result = []
    for ep in raw:
        policy_document, truncated = _normalize_policy(
            ep.get("PolicyDocument"), include_policies=include_policies
        )
        result.append(
            VpcEndpoint(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                vpc_endpoint_id=ep["VpcEndpointId"],
                vpc_id=ep.get("VpcId", ""),
                service_name=ep.get("ServiceName", ""),
                vpc_endpoint_type=ep.get("VpcEndpointType", ""),
                state=ep.get("State"),
                route_table_ids=ep.get("RouteTableIds", []),
                subnet_ids=ep.get("SubnetIds", []),
                security_group_ids=[g["GroupId"] for g in ep.get("Groups", []) if g.get("GroupId")],
                network_interface_ids=ep.get("NetworkInterfaceIds", []),
                private_dns_enabled=ep.get("PrivateDnsEnabled"),
                dns_entries=[
                    VpcEndpointDnsEntry(
                        dns_name=d.get("DnsName"), hosted_zone_id=d.get("HostedZoneId")
                    )
                    for d in ep.get("DnsEntries", [])
                ],
                policy_document=policy_document,
                policy_document_truncated=truncated,
                tags=normalize_tags(ep.get("Tags")),
            )
        )
    return result


def list_vpc_endpoint_services(
    client_factory: ClientFactory, *, region: str
) -> list[VpcEndpointService]:
    """Call ec2:DescribeVpcEndpointServices and return the services visible
    to this account/region (AWS-provided services plus any of the account's
    own endpoint service configurations)."""
    validate_region_format(region)
    client = client_factory.get_client("ec2", region=region)
    settings = client_factory.settings

    raw = paginate(
        client,
        "describe_vpc_endpoint_services",
        "ServiceDetails",
        max_items=settings.max_page_results,
    )
    return [
        VpcEndpointService(
            service_name=s.get("ServiceName", ""),
            service_id=s.get("ServiceId"),
            service_type=[t.get("ServiceType", "") for t in s.get("ServiceType", [])],
            owner=s.get("Owner"),
            availability_zones=s.get("AvailabilityZones", []),
            private_dns_name=s.get("PrivateDnsName"),
            vpc_endpoint_policy_supported=s.get("VpcEndpointPolicySupported"),
            region=region,
        )
        for s in raw
    ]
