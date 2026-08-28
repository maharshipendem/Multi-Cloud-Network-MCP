"""Normalized models for the "which projects can this server see/operate
against" surface."""

from __future__ import annotations

from pydantic import BaseModel


class PermittedProject(BaseModel):
    """One project this server is permitted to operate against.

    ``source`` records *why* this project is in the result: ``"allowlist"``
    (explicitly configured via ``GCP_PROJECT_ALLOWLIST``) or ``"search"``
    (discovered via Resource Manager's ``search_projects``, i.e. whatever
    the configured identity's IAM bindings expose) -- a caller should
    never conflate "discoverable" with "explicitly allowlisted".
    """

    project_id: str
    display_name: str | None = None
    state: str | None = None
    parent: str | None = None
    source: str


__all__ = ["PermittedProject"]
