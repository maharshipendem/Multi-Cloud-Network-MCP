# GCP golden examples -- notes

All 24 files under this directory were hand-built against the real
`multicloud_network_mcp.contracts.models` Pydantic models and the real
`multicloud_network_mcp.contracts.urn.build_urn()` grammar, cross-checked
field-by-field against `../gcp-network-mcp/src/gcp_network_mcp/models/*.py`
(this session's actual GCP adapter models) rather than guessed. `python -m
multicloud_network_mcp.contracts validate contracts/examples/gcp` reports
**24/24 PASS** (both JSON-Schema and Pydantic-model validation for every
file).

They all describe one internally-consistent, fictitious scenario: GCP
project `acme-prod-networking-123456`, a custom-mode Shared VPC network
`prod-shared-vpc` with two subnetworks (`prod-shared-vpc-us-central1`,
`10.10.0.0/20`, flow logs enabled; `prod-shared-vpc-us-east1`,
`10.20.0.0/20`, flow logs disabled), an instance `app-server-1` in
`us-central1-a`, a Private Service Access range, an IAP-scoped SSH
firewall rule, a static route to on-premises `172.16.0.0/16` via an HA
VPN tunnel, an NCC hub with an inactive spoke, an HA VPN gateway/tunnel
pair terminating at an on-premises peer, a Dedicated Interconnect and
its attachment, a public Cloud DNS zone, an internal HTTP(S) load
balancer, a Private Service Connect consumer/producer pair, a VPC Flow
Logs config, and a cross-project VPC peering to a second (unresolvable)
project `acme-partner-services-654321` used to demonstrate the topology
graph's `UNRESOLVED` node. All identifiers are fake but GCP-shaped
(real self-link/resource-name grammar); no real customer data.

## Coverage

17 of the 21 canonical resource types have a GCP example (`network`,
`subnet`, `network-interface`, `address`, `route`, `firewall-rule`,
`transit-hub`, `attachment`, `peering`, `vpn-gateway`, `vpn-tunnel`,
`interconnect`, `interconnect-attachment`, `dns-zone`, `load-balancer`,
`endpoint` -- two files, consumer and producer -- and
`observability-reference`), plus one `topology-graph`, one `finding`,
one `path-explanation`, one `response-envelope`, and one
`provider-capability-manifest` -- 24 files total.

## Skipped resource types (structural GCP gaps, not omissions)

- **`route-table`**: GCP has no route-table resource at all -- routes
  are directly project/network-scoped, with no intermediate table (see
  `resources.py::RouteTable`'s own docstring, and
  `route.gcp-to-onprem.json`'s `_note`). Per that docstring's stated
  preference, this is omitted entirely rather than synthesizing one
  fake implicit table per network, which would misrepresent GCP's
  actual model.

- **`gateway`**: GCP's default-internet-route case is implicit-only --
  a network's default route to the internet has no backing gateway
  resource whatsoever (see `resources.py::Gateway`'s docstring). Skipped
  rather than synthesized: `route.gcp-to-onprem.json` already
  demonstrates a route with a resolvable non-gateway next hop
  (`next_hop_type="vpn-tunnel"`), and inventing a placeholder `Gateway`
  record for the unmodeled default-internet case would assert a
  resource GCP doesn't actually expose.

- **`dns-resolver`** / **`dns-rule`**: GCP has no resolver-endpoint or
  conditional-forwarding-rule resource distinct from a `DnsZone`/policy
  -- a structural gap in GCP's DNS product surface, not a collection
  failure (see `resources.py::DnsResolver`/`DnsRule`'s own docstrings
  and `gcp_network_mcp.models.dns`'s module docstring / this session's
  `docs/limitations.md#cloud-dns`). Neither is exampled here.

`provider-capability-manifest.gcp-manifest.json`'s 17-entry
`supported_resource_types` list additionally omits `network-interface`
and `observability-reference` -- not because GCP lacks either concept
(both have real example files in this directory), but because this
manifest is copied **verbatim** from gcp-network-mcp's own real
`gcp_get_contract_capabilities` implementation
(`gcp_network_mcp.tools.contracts._capability_manifest()`,
`adapter_version` `0.2.0`), which does not yet report either type or
wire up diagnostics/observability export
(`supports_diagnostics=false`, `supports_observability=false`). This is
a deliberate choice: the manifest example reflects what the adapter
*actually* returns today, not an aspirational manifest matching every
file in this directory -- the gap between the two (this directory's
`finding`/`path-explanation`/`observability-reference` files show what
that richer output would look like once wired up) is itself worth
preserving as an honest example of adapter/contract-fixture drift.

## Judgment calls mapping GCP values onto this contract's vocabularies

- **`route.gcp-to-onprem.json`** (pre-existing, referenced for context):
  `origin="unknown"`/`state="unknown"` are the *correct* normalization
  result per `normalization/route.py`'s own docstring -- GCP's Route API
  returns no origin/state field at all. `priority=1000` is populated
  because that's GCP's own genuine strength (an explicit tie-break
  AWS/Azure don't have).

- **`vpn-gateway.gcp-ha-vpn-gw1.json`**: `is_ha=true` is a **lossless**
  mapping here, unlike the AWS `vpn-gateway` example's inferred
  `is_ha` -- every `VpnGatewaysClient` resource in GCP is an HA VPN
  gateway by construction; Classic VPN uses an entirely distinct
  `TargetVpnGateway` type, out of this adapter's scope. `asn` is `null`:
  an HA VPN gateway carries no ASN of its own in GCP's model -- the ASN
  lives on the associated Cloud Router, which has no canonical resource
  type in this contract (see "Not modeled" below). `state="available"`
  is inferred, not read from a native field, the same way
  `network.gcp-prod-shared-vpc.json`'s `state` is (`gcp_network_mcp
  .models.vpn.VpnGateway` carries no `state` field at all).

- **`vpn-tunnel.gcp-ha-vpn-gw1-tunnel-0.json`**: `bgp_enabled`/
  `bgp_asn` are populated via a legitimate cross-resource lookup (the
  associated Cloud Router's `RouterBgpPeerConfig.peer_asn`, joined via
  `router_self_link`/`RouterBgpPeerStatus.linked_vpn_tunnel`), not
  fabricated -- GCP's own `VpnTunnel` model carries no BGP fields
  itself. `peer_gateway_urn` is `null`, matching the AWS `vpn-tunnel`
  example's same judgment: the on-premises device is not collected as
  its own resource, so `peer_ip` (`203.0.113.20`) is the only
  identifying fact captured. `redacted=true` is permanent -- no
  shared-secret field exists anywhere on this model or the GCP one it's
  built from.

- **`interconnect-attachment.gcp-dedicated-va-us-central1.json`**:
  `router_urn` is deliberately `null` (not pointed at a stand-in
  resource, unlike the AWS `interconnect-attachment` example, which
  points `router_urn` at its Transit Gateway): a GCP attachment has no
  direct network reference of its own -- it attaches to a Cloud Router,
  whose network you resolve separately -- and Cloud Router has no
  canonical resource type here, so there is no lossless URN to
  populate `router_urn` with. Guessing a stand-in (the owning `Network`,
  or the NCC transit-hub) would overclaim a relationship this
  attachment doesn't directly assert; the raw `router_self_link` is
  preserved in `extensions.gcp` instead. `asn` is `null` for the same
  reason (Dedicated, not Partner, so no `partner_asn`; the router's own
  ASN isn't exposed on the attachment).

- **`dns-zone.gcp-acme-example-com.json`**: `is_private=false` and
  `linked_network_urns=[]` are both **best-effort defaults**, not
  observed facts. `google-cloud-dns` -- the only Google-published
  Python client for Cloud DNS, and the only one `gcp-network-mcp` uses
  -- exposes no `visibility`/`privateVisibilityConfig` accessor at all
  (see `gcp_network_mcp.models.dns`'s module docstring). Defaulting to
  `false`/empty (rather than asserting a privacy guarantee or a network
  binding this collection never verified) is the least-overclaiming
  choice available given that structural gap. `name_servers` *is*
  populated and reliable regardless, per `resources.py::DnsZone`'s own
  docstring -- GCP always returns a managed zone's assigned name
  servers independent of the visibility gap.

- **`load-balancer.gcp-prod-app-ilb.json`**: synthesized, not a 1:1
  export, per `resources.py::LoadBalancer`'s own docstring -- assembled
  from a chain of three GCP resources (`ForwardingRule` +
  `TargetHttpsProxy` + `BackendService`), none of which alone is "the
  load balancer." `native_id`/`urn` are minted from the forwarding
  rule, the one piece with a stable per-LB identity.

- **`endpoint.gcp-psc-to-partner-api.json`** (consumer) /
  **`endpoint.gcp-prod-app-service-attachment.json`** (producer):
  built as a deliberate pair, unlike AWS (which has no first-class
  producer-side resource at all -- see `aws/NOTES.md`). The consumer
  side is a synthesis (a `ForwardingRule` targeting a Service
  Attachment URL is not its own GCP resource type); the producer side
  is a **direct, lossless mapping** (GCP's `ServiceAttachment` *is* a
  first-class resource with its own self-link) -- a genuine advantage
  GCP has over AWS's producer-side gap. The producer example's
  `subnet_urn` is `null`: a `ServiceAttachment` references a NAT-subnet
  *pool* (`nat_subnet_self_links`, preserved in `extensions.gcp`), a
  materially different relationship than a single consumer-facing
  subnet, so it isn't forced into `subnet_urn`.

- **`peering.gcp-prod-shared-vpc-to-partner-vpc.json`**:
  `remote_network_urn` is `null` and `remote_native_id` is populated
  instead -- the peer network `partner-vpc` lives in project
  `acme-partner-services-654321`, a scope this collection's credentials
  cannot read into. Paired with the `UNRESOLVED` node for the same peer
  in `topology-graph.gcp-vpc-topology.json`. `allow_forwarded_traffic`
  is `null` (no matching GCP field at all -- that concept is
  Azure-specific); `exchange_subnet_routes`/`import_custom_routes`/
  `export_custom_routes` are GCP's own genuine, directly-observed
  fields (unlike for an AWS-sourced `Peering`, where the contract's own
  docstring says those must stay `null`). `native_id` is a synthesized
  `projects/.../networks/.../peerings/<name>` identifier: GCP peerings
  are embedded on `Network.peerings`, with no independent self-link of
  their own.

- **`observability-reference.gcp-flow-logs-us-central1.json`** /
  **`finding.gcp-flow-logs-disabled-us-east1.json`**: deliberately
  paired to contrast GCP's *two independent* flow-log mechanisms for
  the same resource type -- a `Subnetwork`'s own built-in
  `enableFlowLogs` toggle (already present as
  `extensions.gcp.enable_flow_logs` on both `subnet.*` example files)
  versus the separate, more configurable Network Management API
  `VpcFlowLogsConfig` resource this `observability-reference` example
  represents. The `finding` shows the diagnostic consequence of the
  *absent* case: `prod-shared-vpc-us-east1` has neither mechanism
  active.

- **`path-explanation.gcp-iap-ssh-to-app-server-1.json`**: the one
  `overall_verdict` in this directory set to `"partially_evaluated"`
  (AWS's/Azure's path-explanation examples both reach a definite
  verdict) -- deliberately chosen to exercise that branch of
  `PathExplanation`'s contract. The firewall-evaluation finding reaches
  `confidence="high"`; a second finding notes that Identity-Aware
  Proxy's own per-request tunnel authorization (a distinct IAM layer
  beyond VPC firewall rules) is out of this collection's scope, at
  `confidence="indeterminate"` with empty `evidence`/`reasoning` -- a
  finding that correctly says "cannot determine" rather than silently
  omitting that layer or guessing it's fine.

## Not modeled (no canonical resource type exists for these)

Two GCP-native resources recur throughout `extensions.gcp` across this
directory but never get their own canonical resource type, because none
of this contract's 21 canonical types corresponds to them closely
enough to avoid misrepresentation:

- **Cloud Router** (`RoutersClient`) -- the BGP/ASN identity behind
  `vpn-gateway`, `vpn-tunnel`, and `interconnect-attachment` alike.
  Its `self_link` is preserved in each of those files'
  `extensions.gcp` (`router_self_link`), and its BGP peer config is the
  legitimate source for `vpn-tunnel`'s `bgp_asn` (see above), but the
  router resource itself is never exampled standalone.
- **`InterconnectLocation`** -- static colocation-facility metadata,
  not a per-customer resource; `interconnect.gcp-dedicated-interconnect-1
  .json`'s `location` field carries only the facility name as free
  text, not a full location record.

## Topology graph (`topology-graph.gcp-vpc-topology.json`)

6 nodes / 5 edges, `completeness="partial"` (required whenever
`warnings` is non-empty):

- 4 `RESOURCE` nodes: the network, its `us-central1` subnet, the HA VPN
  gateway, and its VPN tunnel -- all reusing the exact same `urn`
  values as their standalone resource example files.
- 1 `EXTERNAL` node: the on-premises VPN peer IP (`203.0.113.20`, the
  same `peer_ip` as `vpn-tunnel.gcp-ha-vpn-gw1-tunnel-0.json`).
- 1 `UNRESOLVED` node: the cross-project peered network `partner-vpc`
  (project `acme-partner-services-654321`), paired with a
  `CollectionWarning` (`code="cross_project_permission_denied"`)
  explaining that this collection's credentials have no cross-project
  read access to resolve the peer network's own attributes, even though
  the peering itself was observed from `prod-shared-vpc`'s own side --
  matching `peering.gcp-prod-shared-vpc-to-partner-vpc.json`'s own
  `remote_network_urn=null`/`remote_native_id` choice.

Note: gcp-network-mcp's own *current* `gcp_export_normalized_topology`
implementation (`gcp_network_mcp.tools.contracts._to_topology_graph`)
never actually emits an `UNRESOLVED` `NodeKind` today -- its
`_kind_for_node_type` helper only ever returns `"resource"` or
`"external"`. This example is intentionally more complete than that
current implementation to demonstrate full contract fidelity (the
`UNRESOLVED` kind this contract's schema supports); closing that gap in
the real adapter is a follow-up beyond this milestone's example-fixture
scope.

## Version pins used

- `contract_version` / `min_supported_contract_version` in
  `provider-capability-manifest.gcp-manifest.json`: `1.0.0`
  (`multicloud_network_mcp.contracts.version.CONTRACT_VERSION` at
  generation time).
- `urn_grammar_version`: `1`
  (`multicloud_network_mcp.contracts.version.URN_GRAMMAR_VERSION`).
- `adapter_version`: `0.2.0`, matching `gcp-network-mcp/pyproject.toml`'s
  `version` field (checked directly) -- and matching the literal
  `_ADAPTER_VERSION` constant hardcoded in
  `gcp_network_mcp.tools.contracts` itself.
