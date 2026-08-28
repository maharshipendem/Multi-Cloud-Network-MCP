"""Normalized models for VPC Network Peering (embedded on ``Network.peerings``
-- there is no separate peering-listing API)."""

from __future__ import annotations

from pydantic import BaseModel


class NetworkPeering(BaseModel):
    """One peering entry from a Network's ``peerings`` field.

    ``owning_network_self_link`` is the network this peering was found
    on; ``network`` is GCP's own field name for the *peer* network's
    self-link -- the two are easy to conflate since both are network
    self-links, so they are kept as distinctly named fields rather than
    relying on the reader to infer direction from context.
    """

    name: str
    owning_network_self_link: str
    network: str
    state: str | None = None
    state_details: str | None = None
    exchange_subnet_routes: bool | None = None
    export_custom_routes: bool | None = None
    import_custom_routes: bool | None = None
    auto_create_routes: bool | None = None
    stack_type: str | None = None


__all__ = ["NetworkPeering"]
