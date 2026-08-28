"""Offline analyzer entrypoint: runs the diagnostics engine against a
sanitized, previously-exported ``HybridNetworkSnapshot`` JSON document
instead of a live GCP project -- no GCP client library call, no
credentials, no network access. Used for reproducible golden-test
fixtures and for analyzing a snapshot exported from an environment this
server has no live access to.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gcp_network_mcp.diagnostics.health import NetworkHealthReport, get_network_health
from gcp_network_mcp.diagnostics.hybrid_topology import build_hybrid_topology
from gcp_network_mcp.diagnostics.models import Finding
from gcp_network_mcp.diagnostics.risks import find_network_risks
from gcp_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot
from gcp_network_mcp.models.topology import HybridTopology


def load_snapshot(source: str | Path | dict[str, Any]) -> HybridNetworkSnapshot:
    """Load a ``HybridNetworkSnapshot`` from a JSON file path, a raw JSON
    string, or an already-parsed dict."""
    if isinstance(source, dict):
        data = source
    elif isinstance(source, Path):
        data = json.loads(source.read_text())
    else:
        # A raw JSON document always starts with '{' once stripped; only
        # treat a string as a file path when it doesn't look like JSON.
        # A garbage string that is neither valid JSON nor a real path
        # (e.g. a long free-text blob) can still make Path(source) raise
        # OSError -- ENAMETOOLONG on some platforms, plus any other
        # filesystem-level rejection -- so that's translated into a clean
        # ValueError here rather than leaking a raw, platform-specific
        # OSError out of this function.
        stripped = source.strip()
        if stripped.startswith("{"):
            data = json.loads(stripped)
        else:
            try:
                data = json.loads(Path(source).read_text())
            except OSError as exc:
                raise ValueError(
                    f"source is neither a JSON document nor a readable file path: {exc}"
                ) from exc
    return HybridNetworkSnapshot.model_validate(data)


def analyze_offline_snapshot(
    source: str | Path | dict[str, Any],
) -> tuple[HybridNetworkSnapshot, list[Finding], HybridTopology, NetworkHealthReport]:
    """Load a sanitized snapshot and run the full diagnostics engine
    against it -- the same rules ``gcp_find_network_risks``/
    ``gcp_get_hybrid_topology``/``gcp_get_network_health`` run against a
    live-collected snapshot, applied here to an offline one instead."""
    snapshot = load_snapshot(source)
    findings = find_network_risks(snapshot)
    topology = build_hybrid_topology(snapshot)
    health = get_network_health(snapshot)
    return snapshot, findings, topology, health


__all__ = ["analyze_offline_snapshot", "load_snapshot"]
