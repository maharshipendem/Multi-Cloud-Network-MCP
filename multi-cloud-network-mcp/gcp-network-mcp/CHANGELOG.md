# Changelog

## 0.1.0 — Milestone 7: GCP Network MCP Foundation

Initial release. Independent, production-quality, read-only MCP server
for Google Cloud network operations.

### Added

- Application Default Credentials (ADC) resolution with optional service
  account impersonation; explicit project/folder/organization
  allowlists; a read-only guardrail requiring no per-method exception
  list (unlike the Azure sibling's `begin_*` ambiguity).
- 18 MCP tools: caller identity, permitted projects, networks,
  subnetworks (+ secondary ranges), routes (+ next-hop type derivation),
  firewall rules (+ GCP's implied default rules), hierarchical and
  network-scoped Firewall Policies, instance network interfaces,
  addresses (regional + global), forwarding rules, target proxies,
  backend services (+ health), Cloud Router/NAT, VPC Network Peering,
  Shared VPC host/service relationships, and a deterministic
  `gcp_get_vpc_topology` node/edge graph.
- Partial-result handling: a disabled API or missing IAM permission for
  one resource type is always surfaced as an explicit
  `CollectionWarning`, never silently treated as "zero resources."
- 145 unit tests, 99% coverage; a static AST-based guard against any
  service-layer module bypassing the read-only guardrail; end-to-end MCP
  `list_tools()`/`call_tool()` smoke tests with the GCP client classes
  mocked at construction time.
- `gcp-custom-role.yaml` — a least-privilege custom IAM role example.
- Dockerfile, docker-compose.yml, `.env.example`, sanitized topology
  fixture, full documentation set.

### Scope boundaries

- No advanced hybrid-connectivity diagnostics engine (unlike the Azure
  sibling's Milestone 6) — foundational inventory + topology only, per
  this milestone's explicit scope.
- No cross-cloud response-envelope unification — deferred to a future
  milestone.
- No mutation of any kind, anywhere in this codebase.
