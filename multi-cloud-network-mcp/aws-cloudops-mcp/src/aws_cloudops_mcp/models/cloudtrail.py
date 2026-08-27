"""Normalized model for CloudTrail network-configuration event lookups.

Deliberately excludes the raw ``CloudTrailEvent`` JSON blob CloudTrail
returns per event -- that payload can be large and includes full request
parameters (which, for some EC2 actions, is more detail than a bounded
diagnostic lookup should surface). Only summary fields (who, what, when,
which resources) are kept, matching this codebase's established
size/redaction posture for anything that could otherwise balloon a tool
response.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NetworkConfigEvent(BaseModel):
    event_id: str
    event_name: str
    event_time: str
    username: str | None = None
    resource_names: list[str] = Field(default_factory=list)


__all__ = ["NetworkConfigEvent"]
