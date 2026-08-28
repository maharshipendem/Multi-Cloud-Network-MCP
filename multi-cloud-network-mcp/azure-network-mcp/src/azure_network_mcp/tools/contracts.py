"""MCP tools: azure_get_contract_capabilities, azure_export_normalized_topology.

These two tools are this repo's adapter surface for the sibling
``multicloud-network-mcp`` package's vendor-neutral contract (Milestone 9).
Per that package's ADR 0001 ("no runtime coupling"), this module never
imports ``multicloud_network_mcp`` -- it builds plain dicts shaped like
that contract's ``ProviderCapabilityManifest``/``TopologyGraph`` Pydantic
models, hand-rolling the same URN grammar
(``urn:mcnet:v<grammar>:<provider>:<scope>:<resource-type>:<native-id>``)
with the stdlib's own ``urllib.parse.quote`` rather than importing the
contract package's ``urn.py``. The ``CONTRACT_VERSION``/
``URN_GRAMMAR_VERSION`` values below are copied as plain literals from
that package's ``contracts/version.py`` as of when this module was
written -- they are not read from an import.

``azure_export_normalized_topology`` calls this repo's own
``azure_get_vnet_topology`` collector (``arm.topology.get_vnet_topology``)
and re-maps its already-collected ``VnetTopology`` output into the
contract's node/edge/URN shape -- it never re-implements collection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from azure_network_mcp import __version__
from azure_network_mcp.arm.networking import list_virtual_networks
from azure_network_mcp.arm.topology import get_vnet_topology
from azure_network_mcp.models.common import normalize_resource_id
from azure_network_mcp.models.topology import TopologyEdge, TopologyNode, VnetTopology
from azure_network_mcp.tools._shared import execute_tool, execute_tool_with_resolved_subscription
from azure_network_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from azure_network_mcp.arm.client_factory import ClientFactory

CAPABILITIES_TOOL_NAME = "azure_get_contract_capabilities"
EXPORT_TOOL_NAME = "azure_export_normalized_topology"

# --- multicloud-network-mcp contract constants (copied literals, not imports) ---
# Source: multicloud-network-mcp/src/multicloud_network_mcp/contracts/version.py
_CONTRACT_VERSION = "1.0.0"
_URN_GRAMMAR_VERSION = 1

# Source: multicloud-network-mcp/src/multicloud_network_mcp/contracts/urn.py
_URN_NID = "mcnet"
_URN_SAFE = "/-._~"
# Fixed scope-key emission order (never alphabetical/insertion-order) --
# identical to that module's own ``_SCOPE_KEY_ORDER``.
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

# This repo's own ``TopologyNode.node_type`` strings -> the contract's
# kebab-case ``ResourceType`` slug. Every node this milestone's
# ``get_vnet_topology`` can produce is a real, in-scope resource (this
# repo's topology tool has no free-form "external"/"unresolved" node-type
# convention of its own), so every mapped node's ``kind`` is "resource".
_NODE_TYPE_TO_RESOURCE_TYPE: dict[str, str] = {
    "virtual_network": "network",
    "subnet": "subnet",
    "network_security_group": "firewall-rule",
    "route_table": "route-table",
    "nat_gateway": "gateway",
    "network_interface": "network-interface",
    "public_ip_address": "address",
    "virtual_network_peering": "peering",
}

# Fallback for an edge endpoint that has no matching node (an
# out-of-scope reference -- e.g. a subnet's NSG in another resource
# group, a peering's remote VNet) -- inferred from the ARM resource ID's
# own type segment rather than left unresolvable, so every edge still
# gets a well-formed ``target_urn``/``source_urn``.
_ARM_TYPE_SEGMENT_TO_RESOURCE_TYPE: dict[str, str] = {
    "virtualnetworks": "network",
    "subnets": "subnet",
    "networksecuritygroups": "firewall-rule",
    "routetables": "route-table",
    "natgateways": "gateway",
    "networkinterfaces": "network-interface",
    "publicipaddresses": "address",
    "virtualnetworkpeerings": "peering",
}


def _escape(value: str) -> str:
    return quote(value, safe=_URN_SAFE)


def _build_urn(*, scope: dict[str, str], resource_type: str, native_id: str) -> str:
    """Mint a ``urn:mcnet:...`` string identical in shape to what
    ``multicloud_network_mcp.contracts.urn.build_urn`` produces, without
    importing that module (ADR 0001)."""
    scope_str = ",".join(
        f"{key}={_escape(scope[key])}" for key in _URN_SCOPE_KEY_ORDER if scope.get(key)
    )
    return (
        f"urn:{_URN_NID}:v{_URN_GRAMMAR_VERSION}:{_escape('azure')}:{scope_str}:"
        f"{resource_type}:{_escape(native_id)}"
    )


def _infer_resource_type(resource_id: str, node_type: str | None) -> str:
    if node_type is not None and node_type in _NODE_TYPE_TO_RESOURCE_TYPE:
        return _NODE_TYPE_TO_RESOURCE_TYPE[node_type]
    parts = [p for p in resource_id.split("/") if p]
    if len(parts) >= 2:
        segment = parts[-2].lower()
        if segment in _ARM_TYPE_SEGMENT_TO_RESOURCE_TYPE:
            return _ARM_TYPE_SEGMENT_TO_RESOURCE_TYPE[segment]
    return "network"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_capability_manifest() -> dict[str, Any]:
    """Build a ``ProviderCapabilityManifest``-shaped dict describing this
    adapter's normalized-export coverage, per
    ``multicloud-network-mcp/docs/tools.md``'s recommended convention."""
    supported_resource_types = [
        {
            "resource_type": "network",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From VirtualNetwork.",
        },
        {
            "resource_type": "subnet",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": None,
        },
        {
            "resource_type": "network-interface",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": None,
        },
        {
            "resource_type": "address",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From PublicIpAddress.",
        },
        {
            "resource_type": "route-table",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": None,
        },
        {
            "resource_type": "route",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": None,
        },
        {
            "resource_type": "firewall-rule",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From SecurityRule.",
        },
        {
            "resource_type": "transit-hub",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": False,
            "notes": "From VirtualHub; has address_prefix, unlike AWS/GCP transit hubs.",
        },
        {
            "resource_type": "attachment",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From HubVirtualNetworkConnection.",
        },
        {
            "resource_type": "peering",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From VirtualNetworkPeering.",
        },
        {
            "resource_type": "vpn-gateway",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": None,
        },
        {
            "resource_type": "vpn-tunnel",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": False,
            "notes": (
                "Modeled from VirtualNetworkGatewayConnection status, not a dedicated "
                "tunnel resource."
            ),
        },
        {
            "resource_type": "interconnect",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From ExpressRouteCircuit.",
        },
        {
            "resource_type": "interconnect-attachment",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From ExpressRouteCircuitPeering.",
        },
        {
            "resource_type": "dns-zone",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "From PrivateDnsZone.",
        },
        {
            "resource_type": "dns-resolver",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": "Azure is the one provider with real DNS resolver data.",
        },
        {
            "resource_type": "dns-rule",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": (
                "From DnsForwardingRule; Azure is the one provider with real resolver/rule data."
            ),
        },
        {
            "resource_type": "load-balancer",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": True,
            "notes": None,
        },
        {
            "resource_type": "endpoint",
            "export_tool": EXPORT_TOOL_NAME,
            "exact_mapping": False,
            "notes": "Synthesized from PrivateEndpoint and PrivateLinkService.",
        },
    ]

    return {
        "provider": "azure",
        "adapter_package": "azure-network-mcp",
        "adapter_version": __version__,
        "contract_version": _CONTRACT_VERSION,
        "min_supported_contract_version": _CONTRACT_VERSION,
        "urn_grammar_version": _URN_GRAMMAR_VERSION,
        "supported_resource_types": supported_resource_types,
        "supports_topology": True,
        "supports_diagnostics": False,
        "supports_observability": False,
        "generated_at": _now_iso(),
    }


def _resolve_vnet_location(
    client_factory: ClientFactory,
    *,
    subscription_id: str,
    resource_group: str,
    virtual_network_name: str,
) -> str | None:
    """Look up the VNet's ``location`` for the exported graph's
    ``CloudScope`` -- ``VnetTopology``/``TopologyNode`` carry no location
    field of their own, so this makes one small, already-existing
    ``list_virtual_networks`` call (the same call ``get_vnet_topology``
    itself makes) rather than duplicating any topology-assembly logic."""
    vnets = list_virtual_networks(
        client_factory, subscription_id=subscription_id, resource_group=resource_group
    )
    vnet = next((v for v in vnets if v.name == virtual_network_name), None)
    return vnet.location if vnet is not None else None


def _map_node(node: TopologyNode) -> dict[str, Any]:
    resource_type = _infer_resource_type(node.node_id, node.node_type)
    return {
        "urn": None,  # filled in by the caller, which has the scope
        "native_id": node.node_id,
        "kind": "resource",
        "resource_type": resource_type,
        "label": node.label,
        "scope": None,  # filled in by the caller
        "ownership": None,
        "tags": node.tags,
        "extensions": {"azure": {"node_type": node.node_type}},
    }


def _map_edge(
    edge: TopologyEdge, *, scope_for_urn: dict[str, str], node_types: dict[str, str]
) -> dict[str, Any]:
    source_type = _infer_resource_type(
        edge.source_id, node_types.get(normalize_resource_id(edge.source_id))
    )
    target_type = _infer_resource_type(
        edge.target_id, node_types.get(normalize_resource_id(edge.target_id))
    )
    return {
        "source_urn": _build_urn(
            scope=scope_for_urn, resource_type=source_type, native_id=edge.source_id
        ),
        "target_urn": _build_urn(
            scope=scope_for_urn, resource_type=target_type, native_id=edge.target_id
        ),
        "relationship": edge.relationship,
        "evidence": [{"source": edge.relationship, "detail": edge.evidence}],
    }


def _map_topology(topology: VnetTopology, *, location: str | None) -> dict[str, Any]:
    scope_for_urn: dict[str, str] = {"subscription_id": topology.subscription_id}
    if location:
        scope_for_urn["location"] = location
    if topology.resource_group:
        scope_for_urn["resource_group"] = topology.resource_group

    collected_at = _now_iso()
    scope = {
        "provider": "azure",
        "tenant_id": None,
        "account_id": None,
        "subscription_id": topology.subscription_id,
        "project_id": None,
        "resource_group": topology.resource_group,
        "region": None,
        "location": location,
        "zone": None,
        "collected_at": collected_at,
    }

    node_types = {normalize_resource_id(n.node_id): n.node_type for n in topology.nodes}

    mapped_nodes = []
    for node in topology.nodes:
        mapped = _map_node(node)
        mapped["urn"] = _build_urn(
            scope=scope_for_urn, resource_type=mapped["resource_type"], native_id=node.node_id
        )
        mapped["scope"] = scope
        mapped_nodes.append(mapped)

    mapped_edges = [
        _map_edge(edge, scope_for_urn=scope_for_urn, node_types=node_types)
        for edge in topology.edges
    ]

    warnings = [
        {
            "resource_type": w.resource_type,
            "resource_type_hint": None,
            "code": w.code,
            "message": w.message,
            "scope": None,
        }
        for w in topology.warnings
    ]

    return {
        "scope": scope,
        "completeness": "partial" if warnings else "complete",
        "nodes": mapped_nodes,
        "edges": mapped_edges,
        "warnings": warnings,
        "api_call_count": topology.api_call_count,
    }


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=CAPABILITIES_TOOL_NAME,
        description=(
            "Return this adapter's ProviderCapabilityManifest-shaped capability "
            "declaration for the multicloud-network-mcp vendor-neutral contract: "
            "which contract/URN-grammar version this adapter targets, and which "
            "resource types azure_export_normalized_topology can produce."
        ),
        meta=capability_meta(resource_types=["contract_capability_manifest"]),
    )
    def azure_get_contract_capabilities() -> dict[str, Any]:
        return execute_tool(
            tool_name=CAPABILITIES_TOOL_NAME,
            subscription_id=None,
            func=_build_capability_manifest,
        )

    @mcp.tool(
        name=EXPORT_TOOL_NAME,
        description=(
            "Build the same VNet topology graph as azure_get_vnet_topology, "
            "re-mapped into the multicloud-network-mcp vendor-neutral "
            "TopologyGraph shape: stable urn:mcnet:... node/edge identifiers, "
            "a CloudScope, and evidence-bearing edges. Additive to, and built "
            "entirely from, this repo's own already-collected topology data -- "
            "never a runtime dependency on the contract package itself."
        ),
        meta=capability_meta(resource_types=["virtual_network", "topology", "normalized_topology"]),
    )
    def azure_export_normalized_topology(
        resource_group: str,
        virtual_network_name: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Export a VNet's topology graph in the multicloud-network-mcp
        vendor-neutral shape.

        Args:
            resource_group: Resource group containing the virtual network.
            virtual_network_name: Name of the virtual network to map.
            subscription_id: Subscription to query. Falls back to
                AZURE_DEFAULT_SUBSCRIPTION_ID if omitted.
        """

        def _run(resolved: str) -> dict[str, Any]:
            topology = get_vnet_topology(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_network_name=virtual_network_name,
            )
            location = _resolve_vnet_location(
                client_factory,
                subscription_id=resolved,
                resource_group=resource_group,
                virtual_network_name=virtual_network_name,
            )
            return _map_topology(topology, location=location)

        return execute_tool_with_resolved_subscription(
            tool_name=EXPORT_TOOL_NAME,
            client_factory=client_factory,
            subscription_id=subscription_id,
            resource_group=resource_group,
            func=_run,
        )
