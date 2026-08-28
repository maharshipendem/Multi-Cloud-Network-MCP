"""Route origin/state normalization.

- **AWS** (``Route.origin``): ``"CreateRouteTable"`` (the route table's
  auto-created local route), ``"CreateRoute"`` (user-created static
  route), ``"EnableVgwRoutePropagation"`` (BGP-propagated from a virtual
  private gateway). ``Route.state``: ``"active"`` / ``"blackhole"``.
- **Azure** (``EffectiveRoute.source``): ``"Default"`` (platform
  system route), ``"User"`` (user-defined route), ``"VirtualNetworkGateway"``
  (BGP-propagated). ``EffectiveRoute.state``: ``"Active"`` / ``"Invalid"``.
- **GCP**: has **no origin or state field on ``Route`` at all** -- a
  real gap, not an oversight in this table. GCP's route API returns
  only the route's own configuration (destination, priority, next hop);
  whether a route is "system" vs. "static" vs. "dynamic" must be
  *inferred* by an adapter (e.g. a ``0.0.0.0/0`` route with
  ``next_hop_gateway`` set to the well-known default-internet-gateway
  URI is almost certainly system-created, but this is inference, not
  observation -- an adapter doing this inference should record it as
  such, e.g. via a lower-confidence ``Finding`` if the origin matters to
  a diagnostic, never presented as a directly-observed fact). GCP
  likewise has no route-level "active"/"blackhole" state; an adapter can
  approximate ``BLACKHOLE`` for a route whose next hop resolves to
  nothing, but again that is inference over other collected data, not a
  raw field this table can normalize from. See
  ``docs/normalization.md``'s route section for the full writeup.
"""

from __future__ import annotations

from multicloud_network_mcp.contracts.models.enums import RouteOrigin, RouteState

_ORIGIN_TABLE: dict[str, RouteOrigin] = {
    # AWS
    "createroutetable": RouteOrigin.SYSTEM,
    "createroute": RouteOrigin.STATIC,
    "enablevgwroutepropagation": RouteOrigin.DYNAMIC,
    # Azure
    "default": RouteOrigin.SYSTEM,
    "user": RouteOrigin.STATIC,
    "virtualnetworkgateway": RouteOrigin.DYNAMIC,
}

_STATE_TABLE: dict[str, RouteState] = {
    # AWS
    "active": RouteState.ACTIVE,
    "blackhole": RouteState.BLACKHOLE,
    # Azure
    "invalid": RouteState.INACTIVE,
}


def normalize_route_origin(raw: str | None) -> str:
    """Map a raw AWS ``Route.origin``/Azure ``EffectiveRoute.source``
    string onto ``RouteOrigin``'s vocabulary (plain ``str`` return, per
    this contract's normalization-target-enum rule). ``None`` or an
    unrecognized value normalizes to ``RouteOrigin.UNKNOWN.value`` --
    the correct result for GCP, which has no origin field to normalize
    from at all (see this module's docstring)."""
    if raw is None:
        return RouteOrigin.UNKNOWN.value
    return _ORIGIN_TABLE.get(raw.strip().lower(), RouteOrigin.UNKNOWN).value


def normalize_route_state(raw: str | None) -> str:
    """Map a raw AWS/Azure route state string onto ``RouteState``'s
    vocabulary. ``None`` or unrecognized normalizes to
    ``RouteState.UNKNOWN.value`` -- again the correct result for GCP."""
    if raw is None:
        return RouteState.UNKNOWN.value
    return _STATE_TABLE.get(raw.strip().lower(), RouteState.UNKNOWN).value


__all__ = ["normalize_route_origin", "normalize_route_state"]
