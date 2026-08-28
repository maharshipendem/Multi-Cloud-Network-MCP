# Azure golden examples -- notes

26 example JSON files, covering 20 of the 21 canonical resource types
(all except `Gateway`) plus one each of `topology-graph`, `finding`,
`path-explanation`, `response-envelope`, and
`provider-capability-manifest`. All 26 pass
`python -m multicloud_network_mcp.contracts validate contracts/examples/azure`
against both the generated JSON Schema and the Pydantic model.

Every example was built by importing the actual `multicloud_network_mcp.contracts`
Pydantic models and `build_urn()` in a generation script
(`.venv/bin/python3` at the package root), never hand-typed, so URN
grammar and required-field completeness are guaranteed rather than
assumed. All examples share one fake, internally-consistent scenario:
subscription `a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d`, resource group
`rg-networking`, region `eastus`, a VNet `vnet-app-eastus`
(`10.20.0.0/16`) with subnet `snet-app`, attached to Virtual WAN hub
`vhub-eastus` via a vWAN VPN gateway terminating an on-premises site,
plus ExpressRoute, Private DNS, DNS Resolver, Private Link, and
observability resources layered on top. No real customer identifiers,
IPs, or ARM resource IDs appear anywhere.

## Skipped: `Gateway`

`Gateway` (the generic internet/NAT egress gateway, per
`resources.py`'s own docstring) has **no first-class Azure resource
equivalent that sits in a route's next hop the way AWS's
`InternetGateway`/`NatGateway` does**. Azure's closest resource,
`NatGateway`, attaches directly to a *subnet* (`Subnet.nat_gateway_id`),
not to a route table entry -- and default internet egress for a subnet
with no NAT gateway requires no explicit resource at all (Azure's
implicit default-outbound-access path). Rather than force-fitting
`NatGateway` into a canonical model whose docstring explicitly
describes Azure's gap here, this example set omits `Gateway` entirely,
per the canonical model's own documented guidance that "an adapter for
[Azure] may therefore emit zero `Gateway` resources for a given scope
even when internet egress is fully functional -- that is not itself an
omission to flag." If a future revision wants an Azure `Gateway`
example anyway, the natural candidate is Azure's `NatGateway`
(`Microsoft.Network/natGateways`), with `network_urn` left `None` (a
NAT gateway has no VNet-level reference, only `subnet_ids`) and
`gateway_type="nat"`.

## Judgment calls mapping Azure fields onto contract vocabularies

- **`Route.next_hop_type`**: Azure's `EffectiveRoute.next_hop_type`
  value `"VirtualAppliance"` (a UDR pointing at an NVA's private IP)
  was mapped to this contract's `"instance"` -- the NVA is a compute
  instance, and `"instance"` is the closest entry in the documented
  `next_hop_type` vocabulary (`internet-gateway`/`nat-gateway`/
  `instance`/`vpn-tunnel`/`peering`/`transit-hub`/`interconnect`/
  `local`/`blackhole`/`other`). The original Azure value is preserved
  verbatim in `extensions["azure"]["native_next_hop_type"]`.
- **`Route.origin`/`Route.state`**: mapped via
  `normalization/route.py`'s tables exactly (`"User"` ->
  `RouteOrigin.STATIC` -> `"static"`; `"Active"` -> `RouteState.ACTIVE`
  -> `"active"`), confirmed by re-reading that module rather than
  guessing.
- **`FirewallRule.protocol`**: Azure's capitalized `"Tcp"` normalizes
  case-insensitively via `normalization/protocol.py` to `"tcp"`; the
  original casing is preserved in
  `extensions["azure"]["native_protocol"]`.
- **`VpnTunnel.status`**: Azure's `VpnConnection.connection_status`
  value `"Connected"` was mapped to `ObservedState.UP` ("up"); the raw
  string is preserved verbatim in `native_status`. No shared/pre-shared
  key field was ever populated -- `azure-network-mcp`'s own
  `VpnConnection` model never reads `shared_key` either (see that
  repo's `models/hybrid_connectivity.py` module docstring), and this
  contract's `VpnTunnel` has no field to put one in regardless.
- **`Interconnect`/`InterconnectAttachment` redaction**: same pattern
  -- `ExpressRouteCircuit.authorization_key`/`service_key` and
  `ExpressRouteCircuitPeering.shared_key` are never read by
  `azure-network-mcp`'s own normalizers, and `redacted=True` is set
  unconditionally on both examples, matching the contract's permanent
  guarantee.
- **`Interconnect.state`**: Azure exposes two separate provisioning
  signals (`circuit_provisioning_state="Enabled"` and
  `service_provider_provisioning_state="Provisioned"`) with no single
  native field matching this contract's one `state` string. Collapsed
  to `"enabled"` (the Azure-side state, since that's what the tenant
  actually controls) with both raw values preserved under
  `extensions["azure"]`.
- **`DnsResolver` granularity**: the canonical `DnsResolver` model's
  `direction`/`ip_addresses` fields are inherently per-endpoint facts
  (Azure's `DnsResolverInboundEndpoint`/`OutboundEndpoint`), not facts
  of the parent `Microsoft.Network/dnsResolvers` resource itself (which
  has no direction or IP of its own). The example therefore uses the
  **inbound endpoint's own resource ID** as `native_id`/`urn`, not the
  parent resolver's ID; the parent resolver's ID and
  `dns_resolver_state` are preserved under
  `extensions["azure"]["dns_resolver_id"]`.
- **`DnsRule.resolver_urn`**: in real Azure, a `DnsForwardingRule`
  belongs to a `DnsForwardingRuleset`, which associates with one or
  more **outbound** endpoints -- not the inbound endpoint this example
  set's `DnsResolver` record represents. Since this example set
  includes only one `DnsResolver` record (the inbound endpoint, to
  match the requested filename convention), `DnsRule.resolver_urn`
  points at that same inbound-endpoint URN for referential consistency
  within this example set rather than minting an unused outbound-only
  URN. A production adapter should point `resolver_urn` at the actual
  associated outbound endpoint's URN instead.
- **`LoadBalancer`**: only the Standard `LoadBalancer` (network-layer)
  resource is given a full example; the provider-capability manifest
  documents that `ApplicationGateway` (layer-7) maps onto the same
  canonical shape with `lb_type="application"` and a synthesized
  `listener_ports` (assembled from `ApplicationGatewayListener`
  entries), matching the same aggregation pattern this contract's own
  `LoadBalancer` docstring describes for GCP's disaggregated LB model --
  not built as a second example file since one `LoadBalancer` example
  already demonstrates the shape and the manifest's `notes` field
  covers the mapping.
- **`NetworkInterface.firewall_rule_group_urns`**: populated with a URN
  for the *whole* NSG (`resource_type="firewall-rule"`,
  `native_id=<NSG's own resource ID>`, distinct from the individual
  `SecurityRule`'s URN used for the `firewall-rule.azure-nsg-allow-ssh.json`
  example, which has a different `native_id`, the rule's own child
  resource ID). Both are legitimately typed `firewall-rule` per this
  contract's kebab-case `ResourceType` vocabulary; only the individual
  rule got its own full example file.
- **`Peering.state`**: Azure's `VirtualNetworkPeering.peering_state`
  value `"Connected"` was lowercased to `"connected"` for consistency
  with every other lowercase `state`/`status` value across these
  examples -- `Peering.state` is plain free-text on this model (no
  normalization table exists for it, since AWS/Azure/GCP peering state
  vocabularies don't correspond closely enough to warrant one), so this
  is a stylistic choice, not a normalization requirement.
- **Cross-subscription peering / topology `UNRESOLVED` node**: the
  peering's remote VNet lives in a second fake subscription
  (`99999999-8888-4777-9666-555555555555`) this collection has no RBAC
  visibility into. `Peering.remote_network_urn` is left `None` with
  `remote_native_id` populated (per the model's own documented
  contract for this exact situation), and the topology graph represents
  the same peer as a `NodeKind.UNRESOLVED` node carrying an `Ownership`
  with `owner_subscription_id` set and a paired `CollectionWarning`
  explaining the RBAC gap -- `completeness="partial"` on the graph
  follows automatically from that warning being present.
- **`response-envelope.azure-get-virtual-network.json`**: wraps the
  same `Network` record as `network.azure-vnet-app-eastus.json`
  (embedded via `.model_dump(mode="json")`) to demonstrate the standard
  tool-call envelope shape around a real canonical payload rather than
  inventing a second, disconnected resource.
- **`provider-capability-manifest.azure-manifest.json`**:
  `adapter_version="0.2.0"` was read directly from
  `azure-network-mcp/pyproject.toml`'s `[project].version`, not
  guessed. `contract_version` and `min_supported_contract_version` both
  equal this package's `CONTRACT_VERSION` (`"1.0.0"`) since this is the
  first Azure manifest generated against it. `supported_resource_types`
  lists exactly the 20 types this example set actually demonstrates
  (`Gateway` is absent from the list, consistent with the skip above).
