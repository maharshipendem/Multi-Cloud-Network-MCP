"""Shared EC2 ``Filters``-parameter builders, used across service modules."""

from __future__ import annotations

from typing import Any


def vpc_filter(vpc_id: str | None) -> dict[str, Any]:
    if not vpc_id:
        return {}
    return {"Filters": [{"Name": "vpc-id", "Values": [vpc_id]}]}


def ids_filter(name: str, ids: list[str] | None) -> dict[str, Any]:
    if not ids:
        return {}
    return {"Filters": [{"Name": name, "Values": ids}]}
