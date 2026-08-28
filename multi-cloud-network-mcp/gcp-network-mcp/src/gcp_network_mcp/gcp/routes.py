"""Service-layer functions for VPC Routes."""

from __future__ import annotations

from google.cloud import compute_v1

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import now_iso
from gcp_network_mcp.gcp.pagination import paginate
from gcp_network_mcp.models.routes import NEXT_HOP_FIELD_TYPES, Route


def _derive_next_hop(route: compute_v1.Route) -> tuple[str, str | None]:
    for field_name, next_hop_type in NEXT_HOP_FIELD_TYPES.items():
        value = getattr(route, field_name, "")
        if value:
            return next_hop_type, str(value)
    return "unknown", None


def normalize_route(route: compute_v1.Route, *, project_id: str) -> Route:
    next_hop_type, next_hop_target = _derive_next_hop(route)
    return Route(
        self_link=route.self_link or None,
        id=str(route.id) if route.id else None,
        name=route.name,
        project_id=project_id,
        network_self_link=route.network,
        dest_range=route.dest_range,
        priority=route.priority,
        next_hop_type=next_hop_type,
        next_hop_target=next_hop_target,
        route_type=route.route_type or None,
        route_status=route.route_status or None,
        tags=list(route.tags),
        observed_at=now_iso(),
        source_api="RoutesClient.list",
    )


def list_routes(client_factory: ClientFactory, *, project_id: str) -> list[Route]:
    """Routes are a global (project-scoped, not region/zone-scoped)
    resource -- one plain ``list`` call covers the whole project."""
    raw = paginate(
        client_factory.routes(),
        "list",
        resource_type="route",
        project_id=project_id,
        project=project_id,
    )
    return [normalize_route(r, project_id=project_id) for r in raw]


__all__ = ["list_routes", "normalize_route"]
