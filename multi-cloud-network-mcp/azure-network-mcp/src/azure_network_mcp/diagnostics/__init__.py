"""Deterministic Azure network diagnostics engine.

Mirrors this project's AWS sibling's ``aws_cloudops_mcp.diagnostics``
package in *shape* (the ``Finding``/rule-catalog contract, the
find/explain/risks/health tool split, an offline dry-run mode) while every
rule's actual logic is Azure-native. This package never imports the Azure
SDK or the MCP transport directly -- ``diagnostics.hybrid_snapshot`` is the
single seam bridging live ARM calls (reusing this repository's own
``arm.*`` service-layer functions) into the ``HybridNetworkSnapshot``
input every rule module consumes. See docs/architecture.md#diagnostics-engine.
"""

from __future__ import annotations
