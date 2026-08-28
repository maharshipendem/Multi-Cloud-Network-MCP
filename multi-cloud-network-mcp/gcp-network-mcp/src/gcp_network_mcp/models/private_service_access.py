"""Normalized model for private services access allocated IP ranges.

A private services access range is a regular ``GlobalAddress`` with
``purpose="VPC_PEERING"`` -- GCP has no distinct resource type for it, so
this is a derived view over ``gcp.addresses.list_global_addresses``'s
output (see ``gcp/private_service_access.py``), not a new collection
path. The *connection* linking this range to a service producer's
network is a separate Service Networking API resource
(``services.connections``); no current Google-published Python client
library (gapic or otherwise) exposes it -- see
docs/limitations.md#private-services-access-connections. This model
covers the range only.
"""

from __future__ import annotations

from pydantic import BaseModel


class PrivateServiceAccessRange(BaseModel):
    self_link: str | None = None
    name: str
    project_id: str
    address: str
    prefix_length: int | None = None
    network_self_link: str | None = None
    status: str | None = None


__all__ = ["PrivateServiceAccessRange"]
