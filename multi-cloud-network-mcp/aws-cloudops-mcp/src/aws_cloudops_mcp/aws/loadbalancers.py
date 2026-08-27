"""AWS service layer: Application/Network/Gateway load balancers (ELBv2).

``DescribeTargetGroups`` is a batch, account-wide call (good), but
``DescribeListeners`` and ``DescribeTargetHealth`` each require one call
per load balancer / target group respectively -- AWS has no batch variant
of either. Listeners are always fetched (bounded by the LB count already
returned, which is itself capped by ``max_page_results``); target health is
additionally bounded and opt-in since it roughly doubles the call count.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from aws_cloudops_mcp.aws.collection import CollectionResult, now_iso
from aws_cloudops_mcp.aws.pagination import paginate
from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.aws.regions import validate_region_format
from aws_cloudops_mcp.aws.tags import normalize_tags
from aws_cloudops_mcp.models.common import CollectionWarning, Tags
from aws_cloudops_mcp.models.network_resources import (
    Listener,
    ListenerAction,
    LoadBalancer,
    LoadBalancerAzSubnet,
    TargetGroup,
    TargetHealth,
)

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory

# elbv2:DescribeTags accepts at most 20 resource ARNs per call.
_DESCRIBE_TAGS_BATCH_SIZE = 20


def _fetch_tags_by_arn(client: Any, arns: list[str]) -> dict[str, Tags]:
    """Batch-fetch tags for LB/target-group ARNs (one call per 20 ARNs)."""
    tags_by_arn: dict[str, Tags] = {}
    for i in range(0, len(arns), _DESCRIBE_TAGS_BATCH_SIZE):
        batch = arns[i : i + _DESCRIBE_TAGS_BATCH_SIZE]
        response = call_readonly(client, "describe_tags", ResourceArns=batch)
        for entry in response.get("TagDescriptions", []):
            tags_by_arn[entry["ResourceArn"]] = normalize_tags(entry.get("Tags"))
    return tags_by_arn


def _normalize_listener(raw: dict[str, Any]) -> Listener:
    return Listener(
        listener_arn=raw["ListenerArn"],
        load_balancer_arn=raw["LoadBalancerArn"],
        protocol=raw.get("Protocol"),
        port=raw.get("Port"),
        default_actions=[
            ListenerAction(type=a.get("Type", ""), target_group_arn=a.get("TargetGroupArn"))
            for a in raw.get("DefaultActions", [])
        ],
    )


def _list_listeners(client: Any, load_balancer_arn: str, *, max_items: int) -> list[Listener]:
    raw = paginate(
        client,
        "describe_listeners",
        "Listeners",
        max_items=max_items,
        LoadBalancerArn=load_balancer_arn,
    )
    return [_normalize_listener(l) for l in raw]  # noqa: E741


def _fetch_target_health(
    client: Any, target_group_arn: str
) -> tuple[list[TargetHealth] | None, CollectionWarning | None]:
    try:
        response = call_readonly(client, "describe_target_health", TargetGroupArn=target_group_arn)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        return None, CollectionWarning(
            resource_type="target_health",
            code="ENRICHMENT_FAILED",
            message=f"Could not fetch target health for {target_group_arn}: {code}.",
        )
    targets = []
    for t in response.get("TargetHealthDescriptions", []):
        target = t.get("Target", {})
        health = t.get("TargetHealth", {})
        targets.append(
            TargetHealth(
                target_id=target.get("Id", ""),
                port=target.get("Port"),
                availability_zone=target.get("AvailabilityZone"),
                health_state=health.get("State"),
                health_reason=health.get("Reason"),
                health_description=health.get("Description"),
            )
        )
    return targets, None


def list_load_balancers(
    client_factory: ClientFactory,
    *,
    region: str,
    vpc_id: str | None = None,
    load_balancer_arns: list[str] | None = None,
    include_target_health: bool = False,
) -> CollectionResult:
    """List ALBs/NLBs/GWLBs joined with their listeners and target groups.

    ``include_target_health`` opts into one extra ``DescribeTargetHealth``
    call per target group (bounded by ``Settings.max_fanout_calls``); target
    groups beyond that cap, or any health check that fails, are recorded as
    warnings rather than silently omitted.
    """
    validate_region_format(region)
    client = client_factory.get_client("elbv2", region=region)
    settings = client_factory.settings
    account_id = client_factory.get_account_id()
    observed_at = now_iso()

    kwargs: dict[str, Any] = {}
    if load_balancer_arns:
        kwargs["LoadBalancerArns"] = load_balancer_arns
    raw_lbs = paginate(
        client,
        "describe_load_balancers",
        "LoadBalancers",
        max_items=settings.max_page_results,
        **kwargs,
    )
    if vpc_id:
        raw_lbs = [lb for lb in raw_lbs if lb.get("VpcId") == vpc_id]

    raw_target_groups = paginate(
        client,
        "describe_target_groups",
        "TargetGroups",
        max_items=settings.max_page_results,
    )
    target_groups_by_lb_arn: dict[str, list[dict[str, Any]]] = {}
    for tg in raw_target_groups:
        for lb_arn in tg.get("LoadBalancerArns", []):
            target_groups_by_lb_arn.setdefault(lb_arn, []).append(tg)

    all_arns = [lb["LoadBalancerArn"] for lb in raw_lbs] + [
        tg["TargetGroupArn"] for tg in raw_target_groups
    ]
    tags_by_arn = _fetch_tags_by_arn(client, all_arns) if all_arns else {}

    warnings: list[CollectionWarning] = []
    fanout_budget = settings.max_fanout_calls
    load_balancers = []
    for lb in raw_lbs:
        lb_arn = lb["LoadBalancerArn"]
        try:
            listeners = _list_listeners(client, lb_arn, max_items=settings.max_page_results)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            listeners = []
            warnings.append(
                CollectionWarning(
                    resource_type="listeners",
                    code="ENRICHMENT_FAILED",
                    message=f"Could not fetch listeners for {lb_arn}: {code}.",
                )
            )

        target_groups = []
        for tg in target_groups_by_lb_arn.get(lb_arn, []):
            targets: list[TargetHealth] | None = None
            if include_target_health:
                if fanout_budget > 0:
                    targets, warning = _fetch_target_health(client, tg["TargetGroupArn"])
                    fanout_budget -= 1
                    if warning:
                        warnings.append(warning)
                else:
                    warnings.append(
                        CollectionWarning(
                            resource_type="target_health",
                            code="FANOUT_CAP_REACHED",
                            message=(
                                f"Skipped target health for {tg['TargetGroupArn']}: "
                                f"max_fanout_calls ({settings.max_fanout_calls}) reached."
                            ),
                        )
                    )
            target_groups.append(
                TargetGroup(
                    account_id=account_id,
                    region=region,
                    observed_at=observed_at,
                    target_group_arn=tg["TargetGroupArn"],
                    target_group_name=tg.get("TargetGroupName", ""),
                    protocol=tg.get("Protocol"),
                    port=tg.get("Port"),
                    vpc_id=tg.get("VpcId"),
                    target_type=tg.get("TargetType"),
                    load_balancer_arns=tg.get("LoadBalancerArns", []),
                    targets=targets,
                    tags=tags_by_arn.get(tg["TargetGroupArn"], {}),
                )
            )

        load_balancers.append(
            LoadBalancer(
                account_id=account_id,
                region=region,
                observed_at=observed_at,
                load_balancer_arn=lb_arn,
                load_balancer_name=lb.get("LoadBalancerName", ""),
                dns_name=lb.get("DNSName"),
                scheme=lb.get("Scheme"),
                vpc_id=lb.get("VpcId"),
                type=lb.get("Type", ""),
                state=(lb.get("State") or {}).get("Code"),
                ip_address_type=lb.get("IpAddressType"),
                availability_zones=[
                    LoadBalancerAzSubnet(zone_name=az.get("ZoneName"), subnet_id=az.get("SubnetId"))
                    for az in lb.get("AvailabilityZones", [])
                ],
                security_group_ids=lb.get("SecurityGroups", []),
                listeners=listeners,
                target_groups=target_groups,
                tags=tags_by_arn.get(lb_arn, {}),
            )
        )

    return CollectionResult(data=load_balancers, warnings=warnings)
