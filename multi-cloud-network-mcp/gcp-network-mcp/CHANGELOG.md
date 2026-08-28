# Changelog

## 0.2.0 — Milestone 8: GCP Advanced Networking and Diagnostics

### Added

- 30 new MCP tools (48 total) covering Network Connectivity Center
  (hubs/spokes/groups/route tables/routes/hub status), Cloud Router BGP
  status, HA/Classic Cloud VPN (gateways/tunnels/external gateways/status),
  Cloud Interconnect (interconnects/attachments/locations/diagnostics),
  Private Service Connect (service attachments/consumer endpoints),
  private services access ranges, Cloud DNS (zones/record sets), Packet
  Mirroring configuration, VPC Flow Logs configuration, Network
  Management Connectivity Tests (read-only — never creates one), and
  bounded/explicit-opt-in Cloud Logging/Monitoring reads.
- A deterministic diagnostics engine (`diagnostics/`) with 12 versioned
  rules (`ROUTE-001/002`, `FW-001/002`, `PEER-001`, `NCC-001`, `NAT-001`,
  `EXPOSE-001`, `HYBRID-001/002/003`, `DNS-001` — see
  `docs/rule_catalog.md`) and four analysis tools:
  `gcp_get_hybrid_topology`, `gcp_explain_network_path`,
  `gcp_find_network_risks`, `gcp_get_network_health`. Every finding
  carries severity, confidence (including `"indeterminate"` for unknown
  fabric behavior or incomplete policy visibility), evidence,
  assumptions, and limitations.
- An offline analyzer (`diagnostics/offline.py`) that runs the full
  engine against a previously-saved, sanitized snapshot with zero live
  GCP calls.
- Redaction-by-omission for VPN shared secrets and Interconnect pairing
  keys — the normalizers never read those fields, verified by tests
  asserting the literal secret string is absent from the normalized
  model's string representation.
- `paginate_with_unreachable()`, a third pagination primitive for
  Network Connectivity Center's `unreachable`-carrying list responses; a
  bespoke legacy-pager helper for `google.cloud.dns` (the one client
  library in this codebase that isn't gapic-generated).
- Extended `gcp-custom-role.yaml` with every M8 resource family's
  read-only permissions; `docs/rule_catalog.md`,
  `docs/limitations.md`, `docs/troubleshooting.md` (new); extended
  `docs/architecture.md`, `docs/security.md`, `docs/tools.md`.
- 357 unit tests (up from 145), covering every new service-layer
  normalizer, every diagnostics rule (healthy + every distinct
  triggering branch), the diagnostics snapshot's partial-collection
  resilience under a genuinely raising sub-collector, and the four new
  MCP tool groups end-to-end.

### Fixed

- `collect_hybrid_snapshot()` originally called several resource-family
  collectors directly rather than through its own `_collect()`
  exception-catching wrapper, so a single disabled API for any of those
  families (NCC, VPN, Interconnect, subnetworks, forwarding rules,
  routers, Shared VPC host status) would abort the entire diagnostics
  tool call instead of degrading to a partial result with a
  `CollectionWarning` — violating this milestone's explicit
  partial-results requirement. Every resource-family collection now
  routes through `_collect()` uniformly.
- `gcp/connectivity_center.py::normalize_group` passed the raw
  `AutoAccept` sub-message straight into a `bool` field, crashing with a
  `pydantic.ValidationError` for any hub with auto-accept actually
  configured; fixed to derive the bool from
  `auto_accept.auto_accept_projects`'s emptiness.

### Scope boundaries

- Cloud DNS forwarding/peering/policy configuration is not exposed — no
  Google-published client library surfaces it (see
  `docs/limitations.md#cloud-dns`).
- Private services access *connections* (as opposed to allocated ranges)
  are not exposed — no dedicated client library exists for the
  `servicenetworking.googleapis.com` API.
- No Network Management Performance Dashboard integration — no API
  found (`BLOCKED`).
- No cross-cloud federation schema — scoped to a future milestone.
- No mutation of any kind, anywhere in this codebase.

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
