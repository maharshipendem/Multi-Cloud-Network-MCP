"""Normalized models for Compute Engine instance connectivity metadata
(this milestone exposes network interfaces/connectivity, not full
instance inventory -- disks, machine config, etc. are out of scope)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from gcp_network_mcp.models.common import GcpResource


class AccessConfigSummary(BaseModel):
    """One external/NAT access config on a network interface."""

    type_: str
    name: str | None = None
    nat_ip: str | None = None
    network_tier: str | None = None
    public_ptr_domain_name: str | None = None


class NetworkInterfaceSummary(BaseModel):
    """One network interface on an instance."""

    name: str
    network_self_link: str | None = None
    subnetwork_self_link: str | None = None
    network_ip: str | None = None
    stack_type: str | None = None
    nic_type: str | None = None
    access_configs: list[AccessConfigSummary] = Field(default_factory=list)
    alias_ip_ranges: list[str] = Field(default_factory=list)


class InstanceSummary(GcpResource):
    """Normalized entry from ``InstancesClient.list``/``aggregated_list``/``get``,
    reduced to connectivity-relevant fields."""

    status: str | None = None
    machine_type: str | None = None
    can_ip_forward: bool | None = None
    tags: list[str] = Field(default_factory=list)
    service_accounts: list[str] = Field(default_factory=list)
    network_interfaces: list[NetworkInterfaceSummary] = Field(default_factory=list)


__all__ = ["AccessConfigSummary", "InstanceSummary", "NetworkInterfaceSummary"]
