"""Normalized models for load-balancing resources: Forwarding Rules,
Target Proxies, and Backend Services (with health)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class ForwardingRuleSummary(GcpResource):
    """Normalized entry from ``ForwardingRulesClient``/
    ``GlobalForwardingRulesClient`` ``list``/``aggregated_list``/``get``."""

    ip_address: str | None = None
    ip_protocol: str | None = None
    port_range: str | None = None
    ports: list[str] = Field(default_factory=list)
    load_balancing_scheme: str | None = None
    network_self_link: str | None = None
    subnetwork_self_link: str | None = None
    target: str | None = None
    backend_service: str | None = None


class TargetProxySummary(GcpResource):
    """Normalized entry from ``TargetHttpProxiesClient``/
    ``TargetHttpsProxiesClient`` ``list``/``get``."""

    proxy_type: str
    url_map: str | None = None
    ssl_certificates: list[str] = Field(default_factory=list)


class BackendSummary(BaseModel):
    """One backend group attached to a Backend Service."""

    group: str | None = None
    balancing_mode: str | None = None
    capacity_scaler: float | None = None


class BackendHealthStatus(BaseModel):
    """One endpoint's health as reported by ``get_health``."""

    instance: str | None = None
    ip_address: str | None = None
    port: int | None = None
    health_state: str | None = None


class BackendServiceHealthSummary(BaseModel):
    """Aggregated health for one backend group of a Backend Service, from
    ``BackendServicesClient.get_health``."""

    group: str
    statuses: list[BackendHealthStatus] = Field(default_factory=list)


class BackendServiceSummary(GcpResource):
    """Normalized entry from ``BackendServicesClient``/
    ``RegionBackendServicesClient`` ``list``/``get``."""

    protocol: str | None = None
    port: int | None = None
    port_name: str | None = None
    load_balancing_scheme: str | None = None
    session_affinity: str | None = None
    timeout_sec: int | None = None
    health_check_self_links: list[str] = Field(default_factory=list)
    backends: list[BackendSummary] = Field(default_factory=list)
    health: list[BackendServiceHealthSummary] = Field(default_factory=list)


__all__ = [
    "BackendHealthStatus",
    "BackendServiceHealthSummary",
    "BackendServiceSummary",
    "BackendSummary",
    "ForwardingRuleSummary",
    "TargetProxySummary",
]
