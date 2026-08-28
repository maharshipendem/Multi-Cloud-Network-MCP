"""Normalized models for the authenticated caller and the projects this
server is permitted to operate against."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CallerIdentity(BaseModel):
    """The identity this server is currently authenticated as.

    ``principal`` is best-effort: ADC does not always expose a human-
    readable principal (e.g. workload identity federation can leave it
    unresolved), in which case it is ``None`` rather than guessed at.
    ``impersonated_service_account`` is set only when
    ``GCP_IMPERSONATE_SERVICE_ACCOUNT`` is configured.
    """

    principal: str | None = None
    credential_type: str
    impersonated_service_account: str | None = None
    adc_project_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    quota_project_id: str | None = None


__all__ = ["CallerIdentity"]
