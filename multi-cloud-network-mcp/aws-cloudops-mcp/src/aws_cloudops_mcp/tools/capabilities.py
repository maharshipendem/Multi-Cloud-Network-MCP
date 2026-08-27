"""Capability metadata attached to every MCP tool's ``meta=`` field.

Lets a future multi-cloud federation layer discover which AWS resource
types this server can read (and confirm every tool is read-only) purely by
calling ``list_tools()`` and reading each tool's ``meta`` -- no Python
import of this codebase required.
"""

from __future__ import annotations

from typing import Any


def capability_meta(*, resource_types: list[str], read_only: bool = True) -> dict[str, Any]:
    return {
        "cloud": "aws",
        "read_only": read_only,
        "resource_types": resource_types,
    }
