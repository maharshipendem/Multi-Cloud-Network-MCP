"""Reusable AWS tag normalizer.

AWS APIs return tags as a list of ``{"Key": ..., "Value": ...}`` objects.
Every part of this codebase that surfaces tags should go through
``normalize_tags`` so tools consistently return ``{"Key": "Value"}`` maps.
"""

from __future__ import annotations

from typing import Any


def normalize_tags(raw_tags: list[dict[str, Any]] | None) -> dict[str, str]:
    """Convert AWS's list-of-Key/Value-dicts tag format into a flat mapping."""
    if not raw_tags:
        return {}
    return {tag["Key"]: tag.get("Value", "") for tag in raw_tags if "Key" in tag}
