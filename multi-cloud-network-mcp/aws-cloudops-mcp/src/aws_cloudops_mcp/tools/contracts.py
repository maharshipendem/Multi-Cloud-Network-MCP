"""MCP tools: ``aws_get_contract_capabilities``, ``aws_export_normalized_topology``.

These are this repo's "adapter" tools in the sense described by the
sibling ``multicloud-network-mcp`` package's ADR 0001 ("No runtime
coupling between cloud repos or with this package") and its
``docs/tools.md`` naming convention. **Per ADR 0001, this module never
imports ``multicloud_network_mcp`` at runtime** -- it builds plain
dicts shaped like that package's ``ProviderCapabilityManifest``/
``TopologyGraph`` Pydantic models (``contracts/models/capability.py``/
``contracts/models/topology.py``), using hardcoded copies of that
package's version constants (``CONTRACT_VERSION``/
``URN_GRAMMAR_VERSION``, read once from ``contracts/version.py`` and
pinned here as literals) and a hand-rolled reimplementation of its
URN-building rule (``contracts/urn.py``'s percent-encoding scheme,
reusing only the stdlib ``urllib.parse.quote`` call that module itself
uses -- never importing the module).

Both tools reuse this repo's existing, already-read-only
``aws.topology.get_vpc_topology`` collector (the same one
``aws_get_vpc_topology`` calls) rather than duplicating any AWS
collection logic -- this module only re-shapes that collector's
already-normalized output into the contract's node/edge/URN vocabulary.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_package_version
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from aws_cloudops_mcp.aws.topology import get_vpc_topology
from aws_cloudops_mcp.models.topology import VpcTopology
from aws_cloudops_mcp.tools._shared import execute_tool
from aws_cloudops_mcp.tools.capabilities import capability_meta

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from aws_cloudops_mcp.aws.client_factory import ClientFactory

CAPABILITIES_TOOL_NAME = "aws_get_contract_capabilities"
EXPORT_TOPOLOGY_TOOL_NAME = "aws_export_normalized_topology"

# multicloud-network-mcp's contracts/version.py, hardcoded as of the
# values read at the time this module was written -- never imported,
# per ADR 0001. Bump these two literals by hand if that package's
# version constants ever change.
_CONTRACT_VERSION = "1.0.0"
_URN_GRAMMAR_VERSION = 1

# multicloud-network-mcp's contracts/urn.py escapes every value it
# doesn't fully control the same way: stdlib urllib.parse.quote with
# this exact `safe` set. Reusing the stdlib call directly (not the
# contracts module) keeps this repo's URNs byte-identical to what that
# package's own `build_urn()` would produce for the same inputs.
_URN_SAFE = "/-._~"

_PACKAGE_NAME = "aws-cloudops-mcp"

# aws.topology.get_vpc_topology's own `node_type` vocabulary, mapped
# onto multicloud-network-mcp's canonical, kebab-case `ResourceType`
# slugs (contracts/models/enums.py). Anything not listed here (e.g.
# AWS's own `managed_prefix_list`, which has no canonical contract type)
# falls back to the original AWS node_type string itself in
# `_resource_type_for` rather than being forced into a misleading
# canonical bucket.
_NODE_TYPE_TO_RESOURCE_TYPE: dict[str, str] = {
    "vpc": "network",
    "subnet": "subnet",
    "route_table": "route-table",
    "internet_gateway": "gateway",
    "egress_only_internet_gateway": "gateway",
    "nat_gateway": "gateway",
    "security_group": "firewall-rule",
    "network_acl": "firewall-rule",
    "network_interface": "network-interface",
    "vpc_peering_connection": "peering",
    "vpc_endpoint": "endpoint",
    "load_balancer": "load-balancer",
    "target_group": "load-balancer",
}


def _resource_type_for(node_type: str) -> str:
    return _NODE_TYPE_TO_RESOURCE_TYPE.get(node_type, node_type)


def _urn_escape(value: str) -> str:
    return quote(value, safe=_URN_SAFE)


def _build_urn(
    *, account_id: str | None, region: str | None, resource_type: str, native_id: str
) -> str:
    """Mint a ``urn:mcnet:v<grammar>:aws:<scope>:<resource-type>:<native-id>``
    string, following multicloud-network-mcp's URN grammar exactly
    (``contracts/urn.py``): the scope's key order is fixed
    (``tenant_id, account_id, subscription_id, project_id, region,
    location, zone, resource_group`` -- AWS only ever populates
    ``account_id``/``region``), absent keys are omitted rather than
    emitted empty, and every value we don't fully control is
    percent-encoded via ``_urn_escape``.
    """
    scope_parts: list[str] = []
    if account_id:
        scope_parts.append(f"account_id={_urn_escape(account_id)}")
    if region:
        scope_parts.append(f"region={_urn_escape(region)}")
    scope_str = ",".join(scope_parts)
    return (
        f"urn:mcnet:v{_URN_GRAMMAR_VERSION}:{_urn_escape('aws')}:{scope_str}:"
        f"{resource_type}:{_urn_escape(native_id)}"
    )


def _adapter_version() -> str:
    """The real current version from this repo's ``pyproject.toml``.

    Read directly from the file rather than from installed package
    metadata: an editable/dev install's ``dist-info`` can lag behind the
    working tree's actual ``pyproject.toml`` after a version bump, and
    this manifest must never report a stale version. Falls back to
    installed package metadata, then a last-resort literal, only if the
    file genuinely can't be read (e.g. a packaged wheel install with no
    ``pyproject.toml`` alongside it).
    """
    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    try:
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
        version = data.get("project", {}).get("version")
        if isinstance(version, str) and version:
            return version
    except (OSError, tomllib.TOMLDecodeError):
        pass
    try:
        return _installed_package_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0"


def _resource_type_support(
    resource_type: str, *, exact_mapping: bool, notes: str | None = None
) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "export_tool": EXPORT_TOPOLOGY_TOOL_NAME,
        "exact_mapping": exact_mapping,
        "notes": notes,
    }


def _build_capability_manifest() -> dict[str, Any]:
    """Build this adapter's ``ProviderCapabilityManifest``-shaped dict.

    Every resource type below is genuinely observable by this repo's
    existing tool suite (Milestones 1-3's VPC, hybrid-connectivity, and
    DNS collectors), but ``exact_mapping`` is set honestly per type:
    ``True`` only for the resource types ``aws_export_normalized_topology``
    itself actually emits as graph nodes today (it wraps the single-VPC
    ``aws_get_vpc_topology`` collector, not the wider hybrid-connectivity
    one), ``False`` -- with an explanatory ``notes`` -- for types this
    adapter can observe via its other tools but does not yet fold into
    that single normalized-topology export.
    """
    supported_resource_types = [
        _resource_type_support("network", exact_mapping=True, notes="Mapped from an AWS VPC."),
        _resource_type_support("subnet", exact_mapping=True),
        _resource_type_support(
            "route-table",
            exact_mapping=True,
            notes=(
                "The route table container is a node; individual routes "
                "are not (see the 'route' entry below)."
            ),
        ),
        _resource_type_support(
            "route",
            exact_mapping=False,
            notes=(
                "AWS routes are represented as topology edges "
                "(relationship 'routes_to'/'local_route', carrying the "
                "route's destination/target/state as edge evidence) "
                "rather than as standalone nodes."
            ),
        ),
        _resource_type_support(
            "firewall-rule",
            exact_mapping=False,
            notes=(
                "Both AWS mechanisms this contract's firewall-rule type "
                "unifies -- EC2 SecurityGroupRule and NetworkAclEntry -- "
                "are represented, but only at security-group/network-ACL "
                "container granularity (one node per security group or "
                "NACL); individual allow/deny rule entries are not yet "
                "exploded into their own nodes. Full rule detail remains "
                "available from aws_list_security_groups and "
                "aws_list_network_acls."
            ),
        ),
        _resource_type_support(
            "transit-hub",
            exact_mapping=False,
            notes=(
                "AWS Transit Gateways are collected by this adapter's "
                "aws_get_hybrid_topology and aws_list_transit_gateways "
                "tools, but not yet folded into aws_export_normalized_"
                "topology's single-VPC scope."
            ),
        ),
        _resource_type_support(
            "attachment",
            exact_mapping=False,
            notes=(
                "AWS Transit Gateway attachments are collected by "
                "aws_get_hybrid_topology and "
                "aws_list_transit_gateway_attachments, not yet folded "
                "into aws_export_normalized_topology."
            ),
        ),
        _resource_type_support(
            "peering", exact_mapping=True, notes="Mapped from an AWS VPC peering connection."
        ),
        _resource_type_support(
            "vpn-gateway",
            exact_mapping=False,
            notes=(
                "Collected by aws_list_vpn_gateways / "
                "aws_get_hybrid_topology, not yet folded into "
                "aws_export_normalized_topology."
            ),
        ),
        _resource_type_support(
            "vpn-tunnel",
            exact_mapping=False,
            notes=(
                "Collected by aws_list_vpn_connections / "
                "aws_get_hybrid_topology, not yet folded into "
                "aws_export_normalized_topology."
            ),
        ),
        _resource_type_support(
            "interconnect",
            exact_mapping=False,
            notes=(
                "AWS Direct Connect connections are collected by "
                "aws_list_direct_connect_connections, not yet folded "
                "into aws_export_normalized_topology."
            ),
        ),
        _resource_type_support(
            "interconnect-attachment",
            exact_mapping=False,
            notes=(
                "AWS Direct Connect virtual interfaces are collected by "
                "aws_list_direct_connect_virtual_interfaces, not yet "
                "folded into aws_export_normalized_topology."
            ),
        ),
        _resource_type_support(
            "dns-zone",
            exact_mapping=False,
            notes=(
                "Route 53 hosted zones are collected by "
                "aws_list_hosted_zones / aws_get_hybrid_topology, not "
                "yet folded into aws_export_normalized_topology."
            ),
        ),
        _resource_type_support(
            "load-balancer",
            exact_mapping=True,
            notes=(
                "Mapped from an AWS load balancer; a load balancer's "
                "target groups are also mapped to this type (AWS has no "
                "separate contract-level type for them)."
            ),
        ),
        _resource_type_support(
            "endpoint", exact_mapping=True, notes="Mapped from an AWS VPC endpoint."
        ),
        _resource_type_support(
            "network-interface", exact_mapping=True, notes="Mapped from an ENI."
        ),
    ]

    return {
        "provider": "aws",
        "adapter_package": _PACKAGE_NAME,
        "adapter_version": _adapter_version(),
        "contract_version": _CONTRACT_VERSION,
        "min_supported_contract_version": _CONTRACT_VERSION,
        "urn_grammar_version": _URN_GRAMMAR_VERSION,
        "supported_resource_types": supported_resource_types,
        "supports_topology": True,
        "supports_diagnostics": False,
        "supports_observability": False,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _build_scope(*, account_id: str | None, region: str, collected_at: str) -> dict[str, Any]:
    return {
        "provider": "aws",
        "tenant_id": None,
        "account_id": account_id,
        "subscription_id": None,
        "project_id": None,
        "resource_group": None,
        "region": region,
        "location": None,
        "zone": None,
        "collected_at": collected_at,
    }


def _map_topology_to_graph(
    topology: VpcTopology, *, account_id: str | None, region: str
) -> dict[str, Any]:
    """Re-map an already-collected ``VpcTopology`` into a
    ``TopologyGraph``-shaped dict, per multicloud-network-mcp's
    ``contracts/models/topology.py``.

    Every node this repo's own collector already resolved becomes a
    ``kind: "resource"`` node with a minted ``urn:mcnet:...`` identifier
    (the original AWS ID is kept as ``native_id``). An edge is only
    emitted when *both* endpoints resolved to a real node -- some of
    this repo's edges intentionally reference an out-of-scope AWS ID
    with no corresponding node (e.g. a route to a resource type this
    milestone doesn't collect), each already flagged by a
    ``CollectionWarning`` in ``topology.warnings``; rather than
    fabricate an ``UNRESOLVED`` node just to keep such an edge, it is
    left out of the exported edge list and the underlying warning is
    carried through instead.
    """
    collected_at = datetime.now(UTC).isoformat()
    scope = _build_scope(account_id=account_id, region=region, collected_at=collected_at)

    urn_by_node_id: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []
    for node in topology.nodes:
        resource_type = _resource_type_for(node.node_type)
        urn = _build_urn(
            account_id=account_id,
            region=region,
            resource_type=resource_type,
            native_id=node.node_id,
        )
        urn_by_node_id[node.node_id] = urn
        nodes.append(
            {
                "urn": urn,
                "native_id": node.node_id,
                "kind": "resource",
                "resource_type": resource_type,
                "label": node.label,
                "scope": dict(scope),
                "ownership": None,
                "tags": dict(node.tags),
                "extensions": {"aws": {"node_type": node.node_type}},
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in topology.edges:
        source_urn = urn_by_node_id.get(edge.source_id)
        target_urn = urn_by_node_id.get(edge.target_id)
        if source_urn is None or target_urn is None:
            continue
        edges.append(
            {
                "source_urn": source_urn,
                "target_urn": target_urn,
                "relationship": edge.relationship,
                "evidence": [{"source": edge.relationship, "detail": edge.evidence}],
            }
        )
    edges.sort(key=lambda e: (e["source_urn"], e["target_urn"], e["relationship"]))

    warnings = [
        {
            "resource_type": warning.resource_type,
            "resource_type_hint": None,
            "code": warning.code,
            "message": warning.message,
            "scope": None,
        }
        for warning in topology.warnings
    ]

    return {
        "scope": scope,
        "completeness": "partial" if warnings else "complete",
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
        "api_call_count": topology.api_call_count,
    }


def _export_normalized_topology(
    client_factory: ClientFactory, *, region: str, vpc_id: str
) -> dict[str, Any]:
    topology = get_vpc_topology(client_factory, region=region, vpc_id=vpc_id)
    try:
        account_id = client_factory.get_account_id()
    except Exception:  # noqa: BLE001 - account id is best-effort, matches execute_tool's own handling
        account_id = None
    return _map_topology_to_graph(topology, account_id=account_id, region=region)


def register(mcp: MCPServer, client_factory: ClientFactory) -> None:
    @mcp.tool(
        name=CAPABILITIES_TOOL_NAME,
        description=(
            "Return this adapter's multicloud-network-mcp contract "
            "capability manifest: the contract/URN-grammar versions this "
            "adapter targets, and which AWS resource types it can "
            "normalize into the contract's vendor-neutral TopologyGraph "
            "shape via aws_export_normalized_topology (and which of those "
            "mappings are exact vs. best-effort today). Static metadata; "
            "makes no AWS API calls beyond the identity lookup every tool "
            "in this server performs."
        ),
        meta=capability_meta(resource_types=["contract_capabilities"]),
    )
    def aws_get_contract_capabilities() -> dict[str, Any]:
        return execute_tool(
            tool_name=CAPABILITIES_TOOL_NAME,
            client_factory=client_factory,
            region=None,
            func=_build_capability_manifest,
        )

    @mcp.tool(
        name=EXPORT_TOPOLOGY_TOOL_NAME,
        description=(
            "Assemble the same VPC networking topology graph as "
            "aws_get_vpc_topology, re-mapped into multicloud-network-mcp's "
            "vendor-neutral TopologyGraph shape: stable urn:mcnet:... node "
            "identifiers (alongside each node's original AWS ID), a "
            "formal resource_type/kind per node, and each edge's evidence "
            "wrapped as structured {source, detail} entries. Read-only; "
            "issues the exact same AWS API calls as aws_get_vpc_topology."
        ),
        meta=capability_meta(resource_types=["vpc_topology", "normalized_topology"]),
    )
    def aws_export_normalized_topology(region: str, vpc_id: str) -> dict[str, Any]:
        """Assemble a VPC's topology graph in the multicloud-network-mcp contract's shape.

        Args:
            region: AWS region to query, e.g. "us-east-1".
            vpc_id: The VPC to build the topology graph for.
        """
        return execute_tool(
            tool_name=EXPORT_TOPOLOGY_TOOL_NAME,
            client_factory=client_factory,
            region=region,
            func=lambda: _export_normalized_topology(client_factory, region=region, vpc_id=vpc_id),
        )
