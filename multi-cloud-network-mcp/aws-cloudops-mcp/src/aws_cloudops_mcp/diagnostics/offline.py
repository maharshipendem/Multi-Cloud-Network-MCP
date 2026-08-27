"""Offline dry-run mode: load a saved, sanitized :class:`NetworkSnapshot`
from a JSON file instead of collecting one from live AWS calls.

Since every ``diagnostics.*`` function already takes a plain
``NetworkSnapshot`` and never touches boto3 or an MCP context, "offline
mode" is nothing more than constructing that same object from a file
instead of from ``aws.snapshot.collect_network_snapshot`` -- there is no
separate code path for diagnostics to behave differently offline versus
live, which is the point: a saved fixture and a live snapshot are
interchangeable inputs to the same deterministic engine.
"""

from __future__ import annotations

import json
from pathlib import Path

from aws_cloudops_mcp.diagnostics.snapshot import NetworkSnapshot


def load_snapshot(path: str | Path) -> NetworkSnapshot:
    """Load and validate a saved snapshot JSON file.

    Raises ``pydantic.ValidationError`` if the file's shape doesn't match
    :class:`NetworkSnapshot` -- a malformed or hand-edited fixture fails
    loudly here rather than producing silently-wrong diagnostic output.
    """
    raw = json.loads(Path(path).read_text())
    return NetworkSnapshot.model_validate(raw)


def save_snapshot(snapshot: NetworkSnapshot, path: str | Path) -> None:
    """Save a snapshot to a JSON file (e.g. to capture a live snapshot for
    later offline replay, or to hand-author a sanitized test fixture)."""
    Path(path).write_text(snapshot.model_dump_json(indent=2))


__all__ = ["load_snapshot", "save_snapshot"]
