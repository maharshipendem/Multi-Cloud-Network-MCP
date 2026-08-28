from __future__ import annotations

from google.api_core import exceptions as gax
from google.cloud import compute_v1
from tests.conftest import PROJECT_ID, make_aggregated_pager

from gcp_network_mcp.gcp.load_balancing import (
    list_backend_services,
    list_forwarding_rules,
    list_target_proxies,
)


def test_list_forwarding_rules_across_scopes(client_factory) -> None:
    global_rule = compute_v1.ForwardingRule(
        name="global-fr",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/forwardingRules/global-fr",
        I_p_address="34.1.1.1",
        I_p_protocol="TCP",
        load_balancing_scheme="EXTERNAL",
        target="target-proxy-1",
    )
    client_factory.forwarding_rules().aggregated_list.return_value = make_aggregated_pager(
        {"global": [global_rule]}, items_field="forwarding_rules"
    )
    result = list_forwarding_rules(client_factory, project_id=PROJECT_ID)
    assert len(result.data) == 1
    assert result.data[0].ip_address == "34.1.1.1"
    assert result.data[0].ip_protocol == "TCP"


def test_list_target_proxies_combines_http_and_https(client_factory) -> None:
    http_proxy = compute_v1.TargetHttpProxy(name="http-proxy", url_map="url-map-1")
    https_proxy = compute_v1.TargetHttpsProxy(
        name="https-proxy", url_map="url-map-1", ssl_certificates=["cert-1"]
    )
    client_factory.target_http_proxies().aggregated_list.return_value = make_aggregated_pager(
        {"global": [http_proxy]}, items_field="target_http_proxies"
    )
    client_factory.target_https_proxies().aggregated_list.return_value = make_aggregated_pager(
        {"global": [https_proxy]}, items_field="target_https_proxies"
    )
    result = list_target_proxies(client_factory, project_id=PROJECT_ID)
    assert {p.proxy_type for p in result.data} == {"Http", "Https"}
    https = next(p for p in result.data if p.proxy_type == "Https")
    assert https.ssl_certificates == ["cert-1"]


def test_list_backend_services_includes_health(client_factory) -> None:
    backend_service = compute_v1.BackendService(
        name="bes-1",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/backendServices/bes-1",
        protocol="HTTP",
        backends=[compute_v1.Backend(group="instance-group-1", balancing_mode="UTILIZATION")],
    )
    client_factory.backend_services().aggregated_list.return_value = make_aggregated_pager(
        {"global": [backend_service]}, items_field="backend_services"
    )
    client_factory.backend_services().get_health.return_value = (
        compute_v1.BackendServiceGroupHealth(
            health_status=[
                compute_v1.HealthStatus(
                    instance="vm-1", ip_address="10.0.0.5", health_state="HEALTHY"
                )
            ]
        )
    )
    result = list_backend_services(client_factory, project_id=PROJECT_ID, include_health=True)
    assert len(result.data) == 1
    service = result.data[0]
    assert len(service.health) == 1
    assert service.health[0].group == "instance-group-1"
    assert service.health[0].statuses[0].health_state == "HEALTHY"
    assert result.warnings == []


def test_list_backend_services_skips_health_when_disabled(client_factory) -> None:
    backend_service = compute_v1.BackendService(
        name="bes-1",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/backendServices/bes-1",
        backends=[compute_v1.Backend(group="instance-group-1")],
    )
    client_factory.backend_services().aggregated_list.return_value = make_aggregated_pager(
        {"global": [backend_service]}, items_field="backend_services"
    )
    result = list_backend_services(client_factory, project_id=PROJECT_ID, include_health=False)
    assert result.data[0].health == []
    client_factory.backend_services().get_health.assert_not_called()


def test_list_backend_services_health_failure_becomes_warning_not_exception(client_factory) -> None:
    backend_service = compute_v1.BackendService(
        name="bes-1",
        self_link=f"https://www.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/backendServices/bes-1",
        backends=[compute_v1.Backend(group="instance-group-1")],
    )
    client_factory.backend_services().aggregated_list.return_value = make_aggregated_pager(
        {"global": [backend_service]}, items_field="backend_services"
    )
    client_factory.backend_services().get_health.side_effect = gax.Forbidden("no permission")
    result = list_backend_services(client_factory, project_id=PROJECT_ID, include_health=True)
    assert result.data[0].health == []
    assert len(result.warnings) == 1
    assert result.warnings[0].resource_type == "backend_service_health"
