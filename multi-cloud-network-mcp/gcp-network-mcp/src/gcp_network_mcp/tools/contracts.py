"""MCP tools: ``gcp_get_contract_capabilities``, ``gcp_export_normalized_topology``.

Milestone 9 adapter surface for the sibling ``multicloud-network-mcp``
repo's vendor-neutral JSON Schema 2020-12 + Pydantic contract (see that
repo's ``docs/adr/0001-no-runtime-coupling.md``). Per that ADR, this
module never imports ``multicloud_network_mcp`` at runtime -- it builds
plain dicts shaped like that contract's ``ProviderCapabilityManifest``
and ``TopologyGraph`` models by hand, including a self-contained URN
builder that reproduces ``multicloud_network_mcp.contracts.urn``'s exact
grammar (same scope key order, same ``urllib.parse.quote`` escaping)
without depending on that package. Every constant sourced from that
repo (``CONTRACT_VERSION``, ``URN_GRAMMAR_VERSION``) is a hardcoded
literal here, not an import.

Both tools reuse this server's existing, already-collected data:
``gcp_export_normalized_topology`` calls the very same
``gcp.topology.get_vpc_topology`` that backs ``gcp_get_vpc_topology`` and
only re-shapes its output, never re-collecting anything. Every existing
tool in this package (including ``gcp_get_vpc_topology`` itself) is
completely unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from gcp_network_mcp.gcp.topology import get_vpc_topology
from gcp_network_mcp.models.common import CollectionWarning as GcpCollectionWarning
from gcp_network_mcp.models.topology import TopologyEdge as GcpTopologyEdge
from gcp_network_mcp.models.topology import TopologyNode as GcpTopologyNode
from gcp_network_mcp.models.topology import VpcTopology
from gcp_network_mcp.tools._shared import execute_tool, execute_tool_with_resolved_project
from gcp_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from gcp_network_mcp.auth.session import ResourceContext
    from gcp_network_mcp.gcp.client_factory import ClientFactory

CAPABILITIES_TOOL_NAME = "gcp_get_contract_capabilities"
TOPOLOGY_TOOL_NAME = "gcp_export_normalized_topology"

# multicloud_network_mcp.contracts.version's CONTRACT_VERSION/URN_GRAMMAR_VERSION,
# read once and hardcoded here (never imported -- see module docstring).
_CONTRACT_VERSION = "1.0.0"
_URN_GRAMMAR_VERSION = 1

_ADAPTER_PACKAGE = "gcp-network-mcp"
_ADAPTER_VERSION = "0.2.0"  # keep in sync with pyproject.toml's [project].version

# --- URN construction --------------------------------------------------
#
# Reproduces multicloud_network_mcp.contracts.urn.build_urn's exact
# grammar: urn:mcnet:v<major>:<provider>:<scope>:<resource-type>:<native-id>,
# with the scope emitted in the same fixed key order and the same
# percent-encoding rule (quote(value, safe="/-._~")), by hand rather than
# by importing that module.

_URN_SCOPE_KEY_ORDER = (
    "tenant_id",
    "account_id",
    "subscription_id",
    "project_id",
    "region",
    "location",
    "zone",
    "resource_group",
)
_URN_SAFE = "/-._~"


def _urn_escape(value: str) -> str:
    return quote(value, safe=_URN_SAFE)


def _build_urn(*, provider: str, scope: dict[str, str], resource_type: str, native_id: str) -> str:
    scope_str = ",".join(
        f"{key}={_urn_escape(scope[key])}" for key in _URN_SCOPE_KEY_ORDER if scope.get(key)
    )
    return (
        f"urn:mcnet:v{_URN_GRAMMAR_VERSION}:{_urn_escape(provider)}:{scope_str}:"
        f"{resource_type}:{_urn_escape(native_id)}"
    )


# --- gcp_export_normalized_topology: VpcTopology -> TopologyGraph shape --
#
# gcp/topology.py's own free-form `node_type` strings, mapped onto this
# contract's closed ResourceType slug vocabulary and NodeKind.
_NODE_TYPE_TO_RESOURCE_TYPE = {
    "network": "network",
    "subnetwork": "subnet",
    "instance": "network-interface",
    "router": "gateway",
    "external_network": "network",
}

# An edge's relationship, mapped to the best-effort ResourceType of its
# target when that target has no matching node -- gcp/topology.py never
# fabricates a node for an OUT_OF_SCOPE_TARGET reference (except the
# peering case, which does get an `external_network` node), so this is
# how a target-only URN still gets a defensible resource type, inferred
# from what each relationship always points at in gcp/topology.py's own
# join logic.
_RELATIONSHIP_TARGET_RESOURCE_TYPE = {
    "belongs_to_network": "network",
    "attached_to_network": "network",
    "has_interface_in": "subnet",
    "peered_with": "network",
}


def _resource_type_for_node_type(node_type: str) -> str:
    return _NODE_TYPE_TO_RESOURCE_TYPE.get(node_type, node_type)


def _kind_for_node_type(node_type: str) -> str:
    # gcp/topology.py's only ever-fabricated placeholder node is
    # `external_network` (an out-of-project peering target); every other
    # node type this repo's topology builder emits is a directly-observed,
    # in-scope resource.
    return "external" if node_type == "external_network" else "resource"


def _node_scope(node: GcpTopologyNode, *, observed_at: str) -> dict[str, Any] | None:
    # An `external_network` placeholder node carries no project_id (it was
    # never resolved against a real project) -- matching TopologyNode's own
    # contract, `scope` is None whenever a node has no cloud scope at all.
    if node.project_id is None:
        return None
    return {
        "provider": "gcp",
        "tenant_id": None,
        "account_id": None,
        "subscription_id": None,
        "project_id": node.project_id,
        "resource_group": None,
        "region": node.region,
        "location": None,
        "zone": node.zone,
        "collected_at": observed_at,
    }


def _map_node(node: GcpTopologyNode, *, observed_at: str) -> dict[str, Any]:
    resource_type = _resource_type_for_node_type(node.node_type)
    scope = {
        key: value
        for key, value in (
            ("project_id", node.project_id),
            ("region", node.region),
            ("zone", node.zone),
        )
        if value
    }
    urn = _build_urn(
        provider="gcp", scope=scope, resource_type=resource_type, native_id=node.node_id
    )
    return {
        "urn": urn,
        "native_id": node.node_id,
        "kind": _kind_for_node_type(node.node_type),
        "resource_type": resource_type,
        "label": node.label,
        "scope": _node_scope(node, observed_at=observed_at),
        "ownership": None,
        "tags": dict(node.labels),
        "extensions": {"gcp": {"node_type": node.node_type}},
    }


def _urn_for_edge_endpoint(node_id: str, node_urns: dict[str, str], *, relationship: str) -> str:
    if node_id in node_urns:
        return node_urns[node_id]
    # Unresolved cross-scope reference (an OUT_OF_SCOPE_TARGET this
    # collector warned about but never fabricated a node for): no cloud
    # scope is claimed for it, since this single-project collection never
    # confirmed which project/region it actually belongs to.
    resource_type = _RELATIONSHIP_TARGET_RESOURCE_TYPE.get(relationship, "network")
    return _build_urn(provider="gcp", scope={}, resource_type=resource_type, native_id=node_id)


def _map_edge(edge: GcpTopologyEdge, node_urns: dict[str, str]) -> dict[str, Any]:
    return {
        "source_urn": _urn_for_edge_endpoint(
            edge.source_id, node_urns, relationship=edge.relationship
        ),
        "target_urn": _urn_for_edge_endpoint(
            edge.target_id, node_urns, relationship=edge.relationship
        ),
        "relationship": edge.relationship,
        # SourceEvidence is {source, detail}; gcp/topology.py's own edges
        # only ever carry the single `evidence` string, so it's wrapped
        # into a one-entry list rather than lost.
        "evidence": [{"source": edge.relationship, "detail": edge.evidence}],
    }


def _map_warning(warning: GcpCollectionWarning) -> dict[str, Any]:
    return {
        "resource_type": warning.resource_type,
        "code": warning.code,
        "message": warning.message,
        # CollectionWarning.scope is a nested CloudScope in the contract,
        # not GCP's own flat project_id/scope strings -- reshaping those
        # precisely is best-effort/optional per this milestone's scope, so
        # it's left unset rather than guessed at.
        "scope": None,
    }


def _to_topology_graph(topology: VpcTopology, *, project_id: str) -> dict[str, Any]:
    mapped_nodes = [_map_node(node, observed_at=topology.observed_at) for node in topology.nodes]
    node_urns = {
        node.node_id: mapped["urn"]
        for node, mapped in zip(topology.nodes, mapped_nodes, strict=True)
    }
    edges = [_map_edge(edge, node_urns) for edge in topology.edges]

    return {
        "scope": {
            "provider": "gcp",
            "tenant_id": None,
            "account_id": None,
            "subscription_id": None,
            "project_id": project_id,
            "resource_group": None,
            # GCP VPC networks are global, so this graph-level scope
            # carries no region -- individual nodes (subnetworks, routers)
            # still carry their own region in `scope`.
            "region": None,
            "location": None,
            "zone": None,
            "collected_at": topology.observed_at,
        },
        "completeness": topology.completeness,
        "nodes": mapped_nodes,
        "edges": edges,
        "warnings": [_map_warning(warning) for warning in topology.warnings],
        "api_call_count": topology.api_call_count,
    }


# --- gcp_get_contract_capabilities: ProviderCapabilityManifest shape ----


def _resource_type_support(
    resource_type: str, *, exact_mapping: bool, notes: str | None = None
) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "export_tool": TOPOLOGY_TOOL_NAME,
        "exact_mapping": exact_mapping,
        "notes": notes,
    }


def _capability_manifest() -> dict[str, Any]:
    supported_resource_types = [
        _resource_type_support(
            "network",
            exact_mapping=False,
            notes=(
                "Maps a GCP VPC network node 1:1 by identity (self-link/name), but this "
                "contract's Network shape (e.g. an aggregate CIDR) has no direct GCP field -- "
                "a GCP network itself carries no CIDR; it would need to be synthesized by "
                "unioning the network's subnetworks' ranges."
            ),
        ),
        _resource_type_support(
            "subnet",
            exact_mapping=True,
            notes="GCP Subnetwork maps directly: self-link, region, and ipCidrRange are exact.",
        ),
        _resource_type_support(
            "route",
            exact_mapping=False,
            notes=(
                "GCP Route resources are collected by gcp_list_routes but not yet joined as "
                "topology nodes/edges by gcp_export_normalized_topology's graph."
            ),
        ),
        _resource_type_support(
            "firewall-rule",
            exact_mapping=False,
            notes=(
                "GCP Firewall rules/policies are collected by gcp_list_firewall_rules and "
                "gcp_list_network_firewall_policies but not yet joined into the topology graph."
            ),
        ),
        _resource_type_support(
            "transit-hub",
            exact_mapping=False,
            notes=(
                "From Network Connectivity Center Hub (gcp_list_ncc_hubs). NCC has no direct "
                "equivalent of a single hub CIDR/route table; a hub's routing state is spread "
                "across its route tables and groups, not yet joined into the topology graph."
            ),
        ),
        _resource_type_support(
            "attachment",
            exact_mapping=False,
            notes=(
                "From Network Connectivity Center Spoke (gcp_list_ncc_spokes) -- an NCC spoke "
                "wraps a VPC/VPN/Interconnect/Router appliance resource rather than being a "
                "first-class attachment object itself; not yet joined into the topology graph."
            ),
        ),
        _resource_type_support(
            "peering",
            exact_mapping=True,
            notes=(
                "GCP VPC Network Peering maps directly: name, state, and both networks are "
                "exact (see the `peered_with` edges in gcp_export_normalized_topology)."
            ),
        ),
        _resource_type_support(
            "vpn-gateway",
            exact_mapping=False,
            notes=(
                "GCP HA VPN/Classic VPN gateways are collected by gcp_list_vpn_gateways but "
                "not yet joined into the topology graph."
            ),
        ),
        _resource_type_support(
            "vpn-tunnel",
            exact_mapping=False,
            notes=(
                "GCP VPN tunnels are collected by gcp_list_vpn_tunnels but not yet joined into "
                "the topology graph."
            ),
        ),
        _resource_type_support(
            "interconnect",
            exact_mapping=False,
            notes=(
                "GCP Dedicated/Partner Interconnects are collected by gcp_list_interconnects "
                "but not yet joined into the topology graph."
            ),
        ),
        _resource_type_support(
            "interconnect-attachment",
            exact_mapping=False,
            notes=(
                "GCP Interconnect Attachments (VLAN attachments) are collected by "
                "gcp_list_interconnect_attachments but not yet joined into the topology graph."
            ),
        ),
        _resource_type_support(
            "dns-zone",
            exact_mapping=False,
            notes=(
                "GCP Cloud DNS managed zones are collected by gcp_list_dns_zones but not yet "
                "joined into the topology graph."
            ),
        ),
        _resource_type_support(
            "load-balancer",
            exact_mapping=False,
            notes=(
                "From this server's ForwardingRuleSummary (gcp_list_forwarding_rules), a "
                "synthesis over GCP's forwarding-rule/target-proxy/backend-service resource "
                "chain rather than one first-class GCP load-balancer object; not yet joined "
                "into the topology graph."
            ),
        ),
        _resource_type_support(
            "endpoint",
            exact_mapping=False,
            notes=(
                "From GCP Private Service Connect ServiceAttachment/PscEndpoint "
                "(gcp_list_service_attachments/gcp_list_psc_endpoints); not yet joined into "
                "the topology graph."
            ),
        ),
        _resource_type_support(
            "address",
            exact_mapping=False,
            notes=(
                "From GCP Private Service Access allocated ranges "
                "(gcp_list_private_service_access_ranges) -- a synthesis over a VPC peering "
                "range reservation rather than a standalone GCP Address resource; not yet "
                "joined into the topology graph."
            ),
        ),
        # route-table, dns-resolver, and dns-rule are deliberately omitted:
        # GCP has no first-class equivalent of any of the three (no
        # per-network route table object -- routes are collection-scoped
        # to the network directly; no managed DNS resolver/rule resource
        # distinct from a Cloud DNS zone/policy).
    ]

    return {
        "provider": "gcp",
        "adapter_package": _ADAPTER_PACKAGE,
        "adapter_version": _ADAPTER_VERSION,
        "contract_version": _CONTRACT_VERSION,
        "min_supported_contract_version": _CONTRACT_VERSION,
        "urn_grammar_version": _URN_GRAMMAR_VERSION,
        "supported_resource_types": supported_resource_types,
        "supports_topology": True,
        "supports_diagnostics": False,
        "supports_observability": False,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def register(
    mcp: MCPServer, client_factory: ClientFactory, resource_context: ResourceContext
) -> None:
    @mcp.tool(
        name=CAPABILITIES_TOOL_NAME,
        description=(
            "Return this adapter's ProviderCapabilityManifest for the "
            "multicloud-network-mcp vendor-neutral contract -- which contract "
            "version this server targets, which resource types it can export in "
            "that contract's shape (and via which tool), and whether topology/"
            "diagnostics/observability export is currently supported. Lets a "
            "cross-cloud consumer negotiate compatibility before trusting this "
            "server's normalized-export output."
        ),
        meta=capability_meta(resource_types=["contract-capabilities"]),
    )
    def gcp_get_contract_capabilities() -> dict[str, Any]:
        return execute_tool(
            tool_name=CAPABILITIES_TOOL_NAME,
            project_id=None,
            func=_capability_manifest,
        )

    @mcp.tool(
        name=TOPOLOGY_TOOL_NAME,
        description=(
            "Return one project's VPC topology (the same graph "
            "gcp_get_vpc_topology assembles) re-shaped into the "
            "multicloud-network-mcp contract's vendor-neutral TopologyGraph "
            "shape: stable urn:mcnet:... identifiers in place of GCP self-links, "
            "an explicit resource/external/unresolved kind per node, and typed "
            "source evidence per edge. Purely a re-shaping of already-collected "
            "data -- it performs no additional GCP API calls beyond what "
            "gcp_get_vpc_topology itself already makes."
        ),
        meta=capability_meta(resource_types=["topology"]),
    )
    def gcp_export_normalized_topology(project_id: str | None = None) -> dict[str, Any]:
        """Export one project's VPC topology in the shared cross-cloud contract shape.

        Args:
            project_id: Project to query. Falls back to
                GCP_DEFAULT_PROJECT_ID if omitted.
        """
        return execute_tool_with_resolved_project(
            tool_name=TOPOLOGY_TOOL_NAME,
            resource_context=resource_context,
            project_id=project_id,
            func=lambda resolved: _to_topology_graph(
                get_vpc_topology(client_factory, project_id=resolved), project_id=resolved
            ),
        )


__all__ = ["register"]
