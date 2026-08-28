# Changelog

## 1.0.0 — Milestone 9: Versioned Multi-Cloud Network Contracts

Initial release. A new, independent package defining stable,
vendor-neutral contracts (JSON Schema 2020-12 + typed Pydantic v2
models) that `aws-cloudops-mcp`, `azure-network-mcp`, and
`gcp-network-mcp` can normalize their own data into — without any
runtime dependency between the four repos.

### Added

- A canonical URN grammar (`urn:mcnet:v1:<provider>:<scope>:<resource-type>:<native-id>`)
  with deterministic, reversible escaping — `src/multicloud_network_mcp/contracts/urn.py`,
  full spec in `docs/urn_grammar.md`.
- 21 canonical resource-type models unifying AWS/Azure/GCP network
  concepts (`Network`, `Subnet`, `NetworkInterface`, `Address`,
  `RouteTable`, `Route`, `FirewallRule`, `Gateway`, `TransitHub`,
  `Attachment`, `Peering`, `VpnGateway`, `VpnTunnel`, `Interconnect`,
  `InterconnectAttachment`, `DnsZone`, `DnsResolver`, `DnsRule`,
  `LoadBalancer`, `Endpoint`, `ObservabilityReference`), plus
  `TopologyGraph`/`TopologyNode`/`TopologyEdge`,
  `Finding`/`PathExplanation`, `ResponseEnvelope`/`CollectionWarning`/
  `PartialResultMetadata`/`PaginationMetadata`, and
  `ProviderCapabilityManifest` for capability/version negotiation.
- Extension preservation (`ExtensibleModel.extensions`, namespaced by
  provider) on every resource model — a provider-native fact this
  contract has no first-class field for is never discarded.
- Forward-compatible normalization-target vocabularies: every field
  drawing from a value set that may grow in a future minor version is
  plain-`str`-typed (not a strict enum), at both the Pydantic and JSON
  Schema layers — `models/enums.py`.
- Normalization tables/functions for CIDR/IP, protocol, port range,
  route origin/state, and severity/confidence
  (`contracts/normalization/`).
- 27 generated JSON Schema 2020-12 files (`contracts/schemas/v1/`),
  produced reproducibly from the Pydantic models by
  `scripts/generate_schemas.py` — never hand-edited.
- A conformance CLI (`python -m multicloud_network_mcp.contracts validate <dir>`)
  validating every example against both its schema and its typed model.
- Golden examples from all three clouds under `contracts/examples/{aws,azure,gcp}/`
  (80 total resource/topology/diagnostic/envelope/capability example
  files), each internally consistent within one fictitious scenario per
  provider.
- `docs/normalization.md` — the full per-resource-type mapping
  specification, documenting every unavoidable semantic difference
  found across the three providers' real models (AWS's dual firewall
  mechanism, AWS's missing Elastic IP resource, GCP's missing
  route origin/state fields, GCP's missing DNS resolver/rule, Azure's
  missing generic Gateway resource, and more).
- `docs/versioning.md` — SemVer policy, schema `$id`/publication rules,
  deprecation process, and the `negotiate()` compatibility algorithm.
- `docs/adr/0001-no-runtime-coupling.md` — why no cloud repo imports
  this package (or another cloud repo) at runtime.
- A narrowly-scoped, backward-compatible adapter addition to each cloud
  repo: `<provider>_get_contract_capabilities` and
  `<provider>_export_normalized_topology` MCP tools, built from plain
  dicts (never importing `multicloud_network_mcp` at runtime), wrapping
  each repo's own existing topology-collection logic.
- Round-trip, URN, IPv4/IPv6, extension-preservation, unknown-enum-
  forward-compatibility, absent/null-semantics, evidence-reference,
  partial-collection, provider-semantic-mapping, golden-contract, and
  version-compatibility tests under `tests/contracts/`.

### Scope boundaries

- **No aggregation/federation runtime** — this package defines shapes
  and a validation CLI only. Nothing here calls more than one cloud
  repo's MCP server or merges their results. See
  `docs/adr/0001-no-runtime-coupling.md` and `MILESTONE9_STATUS.md`'s
  scope boundary.
- No cloud repo's existing tools were changed in behavior, wire shape,
  or IAM/RBAC requirements — every adapter addition is purely additive.
- No provider semantics were forced identical across clouds — every
  genuine difference is documented in `docs/normalization.md` rather
  than papered over.
