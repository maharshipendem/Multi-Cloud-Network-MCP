"""Service-layer functions for load-balancing resources: Forwarding
Rules, Target Proxies, and Backend Services (with health)."""

from __future__ import annotations

from google.api_core import exceptions as gax
from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.errors import translate_gcp_error
from gcp_network_mcp.gcp.pagination import paginate_aggregated
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.models.common import CollectionWarning, parse_self_link
from gcp_network_mcp.models.load_balancing import (
    BackendHealthStatus,
    BackendServiceHealthSummary,
    BackendServiceSummary,
    BackendSummary,
    ForwardingRuleSummary,
    TargetProxySummary,
)

# Bounds the per-backend-service fan-out to ``get_health`` -- a backend
# service can have many backend groups, and this is called once per
# group, per backend service, per topology/tool call.
MAX_HEALTH_FANOUT = 20


def normalize_forwarding_rule(
    rule: compute_v1.ForwardingRule, *, project_id: str
) -> ForwardingRuleSummary:
    parsed = parse_self_link(rule.self_link) if rule.self_link else None
    return ForwardingRuleSummary(
        self_link=rule.self_link or None,
        id=str(rule.id) if rule.id else None,
        name=rule.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        ip_address=rule.I_p_address or None,
        ip_protocol=rule.I_p_protocol or None,
        port_range=rule.port_range or None,
        ports=list(rule.ports),
        load_balancing_scheme=rule.load_balancing_scheme or None,
        network_self_link=rule.network or None,
        subnetwork_self_link=rule.subnetwork or None,
        target=rule.target or None,
        backend_service=rule.backend_service or None,
        psc_connection_status=rule.psc_connection_status or None,
        observed_at=now_iso(),
        source_api="ForwardingRulesClient.aggregated_list",
    )


def list_forwarding_rules(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.forwarding_rules(),
        "aggregated_list",
        items_field="forwarding_rules",
        resource_type="forwarding_rule",
        project_id=project_id,
        project=project_id,
    )
    return CollectionResult(
        data=[normalize_forwarding_rule(r, project_id=project_id) for r in raw], warnings=warnings
    )


def _normalize_target_proxy(
    proxy: compute_v1.TargetHttpProxy | compute_v1.TargetHttpsProxy,
    *,
    project_id: str,
    proxy_type: str,
) -> TargetProxySummary:
    parsed = parse_self_link(proxy.self_link) if proxy.self_link else None
    return TargetProxySummary(
        self_link=proxy.self_link or None,
        id=str(proxy.id) if proxy.id else None,
        name=proxy.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        proxy_type=proxy_type,
        url_map=proxy.url_map or None,
        ssl_certificates=list(getattr(proxy, "ssl_certificates", [])),
        observed_at=now_iso(),
        source_api=f"Target{proxy_type}ProxiesClient.aggregated_list",
    )


def list_target_proxies(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    http_raw, http_warnings = paginate_aggregated(
        client_factory.target_http_proxies(),
        "aggregated_list",
        items_field="target_http_proxies",
        resource_type="target_http_proxy",
        project_id=project_id,
        project=project_id,
    )
    https_raw, https_warnings = paginate_aggregated(
        client_factory.target_https_proxies(),
        "aggregated_list",
        items_field="target_https_proxies",
        resource_type="target_https_proxy",
        project_id=project_id,
        project=project_id,
    )
    data = [
        _normalize_target_proxy(p, project_id=project_id, proxy_type="Http") for p in http_raw
    ] + [_normalize_target_proxy(p, project_id=project_id, proxy_type="Https") for p in https_raw]
    return CollectionResult(data=data, warnings=[*http_warnings, *https_warnings])


def _normalize_backend(backend: compute_v1.Backend) -> BackendSummary:
    return BackendSummary(
        group=backend.group or None,
        balancing_mode=backend.balancing_mode or None,
        capacity_scaler=backend.capacity_scaler,
    )


def normalize_backend_service(
    service: compute_v1.BackendService, *, project_id: str
) -> BackendServiceSummary:
    parsed = parse_self_link(service.self_link) if service.self_link else None
    return BackendServiceSummary(
        self_link=service.self_link or None,
        id=str(service.id) if service.id else None,
        name=service.name,
        project_id=project_id,
        region=parsed.region if parsed else None,
        protocol=service.protocol or None,
        port=service.port or None,
        port_name=service.port_name or None,
        load_balancing_scheme=service.load_balancing_scheme or None,
        session_affinity=service.session_affinity or None,
        timeout_sec=service.timeout_sec or None,
        health_check_self_links=list(service.health_checks),
        backends=[_normalize_backend(b) for b in service.backends],
        observed_at=now_iso(),
        source_api="BackendServicesClient.aggregated_list",
    )


def _fetch_health(
    client_factory: ClientFactory,
    service: compute_v1.BackendService,
    *,
    project_id: str,
    region: str | None,
) -> tuple[list[BackendServiceHealthSummary], list[CollectionWarning]]:
    client = (
        client_factory.region_backend_services() if region else client_factory.backend_services()
    )
    kwargs: dict[str, str] = {"project": project_id, "backend_service": service.name}
    if region:
        kwargs["region"] = region

    health: list[BackendServiceHealthSummary] = []
    warnings: list[CollectionWarning] = []
    for backend in list(service.backends)[:MAX_HEALTH_FANOUT]:
        if not backend.group:
            continue
        try:
            result = call_readonly(
                client,
                "get_health",
                resource_group_reference_resource=compute_v1.ResourceGroupReference(
                    group=backend.group
                ),
                **kwargs,
            )
        except gax.GoogleAPICallError as exc:
            error = translate_gcp_error(
                exc, resource_type="backend_service_health", project_id=project_id
            )
            warnings.append(
                CollectionWarning(
                    resource_type="backend_service_health",
                    code=error.error_type,
                    message=error.message,
                    project_id=project_id,
                )
            )
            continue
        health.append(
            BackendServiceHealthSummary(
                group=backend.group,
                statuses=[
                    BackendHealthStatus(
                        instance=s.instance or None,
                        ip_address=s.ip_address or None,
                        port=s.port or None,
                        health_state=s.health_state or None,
                    )
                    for s in result.health_status
                ],
            )
        )
    return health, warnings


def list_backend_services(
    client_factory: ClientFactory, *, project_id: str, include_health: bool = True
) -> CollectionResult:
    raw, warnings = paginate_aggregated(
        client_factory.backend_services(),
        "aggregated_list",
        items_field="backend_services",
        resource_type="backend_service",
        project_id=project_id,
        project=project_id,
    )
    data: list[BackendServiceSummary] = []
    for service in raw:
        summary = normalize_backend_service(service, project_id=project_id)
        if include_health:
            parsed = parse_self_link(service.self_link) if service.self_link else None
            health, health_warnings = _fetch_health(
                client_factory,
                service,
                project_id=project_id,
                region=parsed.region if parsed else None,
            )
            summary.health = health
            warnings.extend(health_warnings)
        data.append(summary)
    return CollectionResult(data=data, warnings=warnings)


__all__ = [
    "list_backend_services",
    "list_forwarding_rules",
    "list_target_proxies",
    "normalize_backend_service",
    "normalize_forwarding_rule",
]
