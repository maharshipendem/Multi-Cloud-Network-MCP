"""``azure_find_network_risks``'s whole-snapshot scan: internet exposure
plus consistency checks, with an optional minimum-severity filter."""

from __future__ import annotations

from azure_network_mcp.diagnostics.consistency import find_blackhole_routes, find_degraded_resources
from azure_network_mcp.diagnostics.exposure import find_exposed_network_interfaces
from azure_network_mcp.diagnostics.models import Finding
from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot

_SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def find_network_risks(
    snapshot: HybridNetworkSnapshot, *, min_severity: str = "info"
) -> list[Finding]:
    threshold = _SEVERITY_ORDER.get(min_severity, 0)
    findings = (
        find_exposed_network_interfaces(snapshot)
        + find_degraded_resources(snapshot)
        + find_blackhole_routes(snapshot)
    )
    return [f for f in findings if _SEVERITY_ORDER.get(f.severity, 0) >= threshold]


__all__ = ["find_network_risks"]
