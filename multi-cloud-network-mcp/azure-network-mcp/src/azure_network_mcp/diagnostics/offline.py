"""Offline dry-run mode: load a saved, sanitized ``HybridNetworkSnapshot``
JSON file and run the exact same diagnostics functions
(``risks.find_network_risks``, ``consistency.*``, ``exposure.*``,
``hybrid_topology.build_hybrid_topology``) against it, with zero Azure
calls. See ``fixtures/demo_hybrid_snapshot.json`` for a hand-built demo
fixture reproducing several findings at once.

``azure_explain_network_path`` is not available offline: it depends on
per-NIC effective route/NSG data
(``diagnostics.snapshot.collect_nic_effective_state``), which isn't part
of ``HybridNetworkSnapshot`` and has no offline equivalent in this
milestone.
"""

from __future__ import annotations

import json
from pathlib import Path

from azure_network_mcp.diagnostics.snapshot import HybridNetworkSnapshot


def load_snapshot_from_file(path: str | Path) -> HybridNetworkSnapshot:
    """Load a ``HybridNetworkSnapshot`` from a saved JSON file, making no
    Azure API calls."""
    data = json.loads(Path(path).read_text())
    return HybridNetworkSnapshot.model_validate(data)


__all__ = ["load_snapshot_from_file"]
