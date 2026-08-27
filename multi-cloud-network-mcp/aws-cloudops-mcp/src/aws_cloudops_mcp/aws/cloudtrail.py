"""AWS service layer: CloudTrail lookup for recent network configuration
events, with a strict lookback window and result cap.

``cloudtrail:LookupEvents`` supports exactly one ``LookupAttributes``
filter per call and has no "event name in (...)" filter, so this queries
by ``EventSource=ec2.amazonaws.com`` (which covers VPC/EC2 network
resources -- routes, security groups, NACLs, peering, NAT/IGW, Transit
Gateway attachments) and filters the results down to a fixed allowlist of
network-relevant event names client-side, rather than issuing one AWS
call per event name.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.models.cloudtrail import NetworkConfigEvent

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

MAX_LOOKBACK_DAYS = 7
DEFAULT_LOOKBACK_HOURS = 24
MAX_RESULTS_CAP = 50

NETWORK_RELEVANT_EVENT_NAMES = frozenset(
    {
        "CreateRoute",
        "ReplaceRoute",
        "DeleteRoute",
        "CreateRouteTable",
        "DeleteRouteTable",
        "AssociateRouteTable",
        "DisassociateRouteTable",
        "ReplaceRouteTableAssociation",
        "AuthorizeSecurityGroupIngress",
        "AuthorizeSecurityGroupEgress",
        "RevokeSecurityGroupIngress",
        "RevokeSecurityGroupEgress",
        "CreateSecurityGroup",
        "DeleteSecurityGroup",
        "CreateNetworkAcl",
        "DeleteNetworkAcl",
        "CreateNetworkAclEntry",
        "DeleteNetworkAclEntry",
        "ReplaceNetworkAclEntry",
        "ReplaceNetworkAclAssociation",
        "CreateVpcPeeringConnection",
        "DeleteVpcPeeringConnection",
        "AcceptVpcPeeringConnection",
        "RejectVpcPeeringConnection",
        "CreateTransitGatewayVpcAttachment",
        "DeleteTransitGatewayVpcAttachment",
        "ModifyTransitGatewayVpcAttachment",
        "AcceptTransitGatewayVpcAttachment",
        "AssociateTransitGatewayRouteTable",
        "DisassociateTransitGatewayRouteTable",
        "EnableTransitGatewayRouteTablePropagation",
        "DisableTransitGatewayRouteTablePropagation",
        "CreateNatGateway",
        "DeleteNatGateway",
        "CreateInternetGateway",
        "DeleteInternetGateway",
        "AttachInternetGateway",
        "DetachInternetGateway",
        "CreateVpnConnection",
        "DeleteVpnConnection",
        "CreateVpnGateway",
        "DeleteVpnGateway",
        "AttachVpnGateway",
        "DetachVpnGateway",
        "ModifyVpcEndpoint",
        "CreateVpcEndpoint",
        "DeleteVpcEndpoints",
    }
)


def resolve_time_window(
    start_time: str | None, end_time: str | None, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """Resolve and clamp the (start, end) lookup window.

    Pure function (aside from reading the current time when ``now`` isn't
    given, for production use) so the clamping arithmetic can be tested
    directly without going through boto3/Stubber -- ``end_time`` defaults
    to now; ``start_time`` defaults to ``DEFAULT_LOOKBACK_HOURS`` before
    that; and the resulting span is clamped to ``MAX_LOOKBACK_DAYS``
    regardless of what was requested.
    """
    resolved_now = now if now is not None else datetime.now(UTC)
    end_dt = datetime.fromisoformat(end_time) if end_time else resolved_now
    start_dt = (
        datetime.fromisoformat(start_time)
        if start_time
        else end_dt - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
    )
    earliest_allowed = end_dt - timedelta(days=MAX_LOOKBACK_DAYS)
    if start_dt < earliest_allowed:
        start_dt = earliest_allowed
    return start_dt, end_dt


def lookup_network_config_events(
    client_factory: ClientFactory,
    *,
    region: str,
    start_time: str | None = None,
    end_time: str | None = None,
    max_results: int = MAX_RESULTS_CAP,
) -> list[NetworkConfigEvent]:
    """Look up recent network-relevant CloudTrail events.

    ``start_time``/``end_time`` are ISO 8601 strings; if omitted, defaults
    to the last ``DEFAULT_LOOKBACK_HOURS`` hours. The lookback window is
    clamped to ``MAX_LOOKBACK_DAYS`` regardless of what's requested, and
    ``max_results`` is clamped to ``MAX_RESULTS_CAP`` -- CloudTrail can
    hold a very large event history, and this tool is a bounded recent-
    activity check, not a general-purpose audit log query.
    """
    client = client_factory.get_client("cloudtrail", region=region)

    start_dt, end_dt = resolve_time_window(start_time, end_time)
    capped_max_results = max(1, min(max_results, MAX_RESULTS_CAP))

    raw = paginate(
        client,
        "lookup_events",
        "Events",
        max_items=capped_max_results,
        LookupAttributes=[{"AttributeKey": "EventSource", "AttributeValue": "ec2.amazonaws.com"}],
        StartTime=start_dt,
        EndTime=end_dt,
    )
    events = [
        NetworkConfigEvent(
            event_id=e["EventId"],
            event_name=e["EventName"],
            event_time=str(e["EventTime"]),
            username=e.get("Username"),
            resource_names=[
                r.get("ResourceName", "") for r in e.get("Resources", []) if r.get("ResourceName")
            ],
        )
        for e in raw
        if e.get("EventName") in NETWORK_RELEVANT_EVENT_NAMES
    ]
    return events[:capped_max_results]


__all__ = [
    "DEFAULT_LOOKBACK_HOURS",
    "MAX_LOOKBACK_DAYS",
    "MAX_RESULTS_CAP",
    "NETWORK_RELEVANT_EVENT_NAMES",
    "lookup_network_config_events",
    "resolve_time_window",
]
