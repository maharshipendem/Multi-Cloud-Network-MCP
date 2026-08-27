"""Tag normalization.

Unlike AWS (a list of ``{Key, Value}`` pairs needing reshaping into a
dict), Azure SDK models already expose ``tags`` as ``dict[str, str] |
None`` -- this helper only needs to handle the ``None`` case so every
normalized model can rely on ``tags`` always being a (possibly empty)
dict, never ``None``.
"""

from __future__ import annotations

from azure_network_mcp.models.common import Tags


def normalize_tags(tags: dict[str, str] | None) -> Tags:
    return dict(tags) if tags else {}


__all__ = ["normalize_tags"]
