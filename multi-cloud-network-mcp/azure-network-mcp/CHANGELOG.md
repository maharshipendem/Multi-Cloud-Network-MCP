# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - Milestone 6 - Azure Advanced Networking and Diagnostics

### Added

- ARM service-layer and MCP-tool coverage for hybrid connectivity: Virtual
  WAN/Virtual Hub (including hub route tables/routes, hub VNet
  connections, hub BGP connections, and routing-intent route maps),
  standalone Azure Route Server (`arm/route_server.py`, a filtered view
  over Virtual Hub), VPN (both vWAN-scoped `VpnGateway`/`VpnSite`/
  `VpnConnection` and classic `VirtualNetworkGateway`/
  `LocalNetworkGateway`/`VirtualNetworkGatewayConnection`), and
  ExpressRoute (circuits, peerings, circuit-to-circuit connections,
  vWAN ExpressRoute gateways/connections, Direct ports and links).
- ARM service-layer and MCP-tool coverage for Private Link (Private
  Endpoints, Private Link Services, service endpoint policies), Private
  DNS (zones, VNet links, bounded record-set summaries) and Azure DNS
  Resolver (inbound/outbound endpoints, forwarding rulesets/rules/VNet
  links), Azure Firewall (firewall and firewall-policy inventory with
  bounded per-collection rule-count summaries), and read-only Network
  Watcher (native topology, existing connection monitors, VNet/NSG flow
  log configuration — never creates/starts/stops any of them).
- Bounded Azure Monitor metric queries (`arm/monitor.py`) against a fixed,
  network-relevant metric catalog per resource type, capped to a 24-hour
  lookback and 288 datapoints per series — mirrors the AWS sibling's
  bounded CloudWatch integration.
- A new, ARM-independent diagnostics engine
  (`azure_network_mcp.diagnostics`): a five-rule catalog
  (`ROUTE-001` effective-route resolution, `SEC-001` effective-NSG rule
  evaluation, `EXPOSE-001` internet exposure, `CONSIST-001` degraded
  resource/connection state, `CONSIST-002` blackhole/orphaned UDRs — see
  [docs/rule_catalog.md](docs/rule_catalog.md)), leaning on Azure's own
  effective-route-table/effective-NSG computations rather than
  reimplementing route/security-group evaluation from scratch. Every
  `Finding` carries `severity`/`confidence`/`evidence`/`reasoning`/
  `assumptions`/`limitations`/`freshness`, with `confidence:
  "indeterminate"` as a first-class outcome, never an omission.
- Four new diagnostics tools: `azure_get_hybrid_topology` (resource-group-
  scoped hybrid connectivity graph joining VNets/hubs/VPN/ExpressRoute),
  `azure_explain_network_path` (route + NSG evaluation for one source NIC
  toward a destination, `overall_verdict` never silently upgraded to
  `"allowed"` on incomplete evidence), `azure_find_network_risks`
  (whole-resource-group risk scan), and `azure_get_network_health`
  (degraded resources/connections plus opt-in bounded metrics).
- `diagnostics/offline.py::load_snapshot_from_file` — an offline dry-run
  mode running the same risk/topology/consistency functions against a
  saved, sanitized `HybridNetworkSnapshot` JSON with zero Azure calls; see
  [fixtures/demo_hybrid_snapshot.json](fixtures/demo_hybrid_snapshot.json).
- `security.guardrails.READ_ONLY_ACTIONS` gained three more explicitly
  justified `begin_*` exceptions:
  `begin_get_bgp_peer_status` (classic gateway BGP peer status),
  `begin_list_advertised_routes`/`begin_list_learned_routes` (hub/Route
  Server BGP peer routes) — each a genuinely read-only computation, not a
  loosening of the read-only rule.
- Redaction by omission for every secret-shaped SDK field this
  milestone's new resource types embed directly (`shared_key`,
  `site_key`, `authorization_key`, `service_key` on `VpnConnection`,
  `VpnSite`, `ExpressRouteCircuit`, `ExpressRouteCircuitPeering`,
  `ExpressRouteCircuitConnection`, `ExpressRouteConnection`,
  `VirtualNetworkGatewayConnection`) — never read by any collector, and
  `ExpressRouteCircuitAuthorizationsOperations` (which manages the actual
  authorization key) is never called at all. Statically enforced by
  `tests/unit/test_no_mutation_calls.py::test_no_arm_module_ever_reads_a_secret_shaped_field`.
- 48 new MCP tools (67 total), each with `capability_meta()` and a
  non-empty description; 110+ new unit tests (300+ total, 95%+ line
  coverage), including scenario-specific coverage for vWAN route
  propagation, custom hub routes, S2S VPN/BGP degradation, ExpressRoute
  states, Private Endpoint/subnet joins, Route Server peers, asymmetric/
  orphaned UDRs, NSG priority/default-rule evaluation, public exposure,
  partial RBAC, unsupported region/API version, throttling, and stale
  metrics — plus a dedicated end-to-end MCP smoke-test suite
  (`tests/unit/test_mcp_smoke_milestone6.py`) covering every new tool
  through the real `call_tool()` path.
- `azure-custom-role.json` extended with every read action (and the three
  new `/action` computations) this milestone's tools need.
- New docs: [docs/rule_catalog.md](docs/rule_catalog.md),
  [docs/limitations.md](docs/limitations.md),
  [docs/troubleshooting.md](docs/troubleshooting.md); `docs/architecture.md`,
  `docs/security.md`, and `docs/tools.md` extended for the diagnostics
  engine, the three new guardrail exceptions, redaction, and all 48 new
  tools.

### Scope decisions (disclosed, not silent gaps — see [docs/limitations.md](docs/limitations.md))

- Network Watcher's `begin_get_network_configuration_diagnostic` and
  `begin_get_troubleshooting_result` are not implemented: their method
  names are easily confused with genuinely mutating operations
  (`begin_get_troubleshooting` *starts* a run), so per this milestone's
  own stop condition ("an SDK operation has unclear mutation semantics"),
  neither is implemented.
- Connection Monitor time-series data points are out of scope (they live
  in Azure Monitor Logs, a distinct capability); only configuration and
  last-known status are returned.
- `EXPOSE-001` evaluates a NIC's *configured* NSG rules rather than
  Azure's per-NIC effective-rule computation, to avoid an unbounded
  fan-out across every internet-facing NIC in a resource group; this
  assumption is disclosed on every `EXPOSE-001` finding.

## [0.1.0] - Milestone 5 - Azure Network MCP Foundation

### Added

- MCP server foundation over stdio, with a layered architecture
  (`tools` → `security` → `arm` → `arm.client_factory` → `auth`) mirroring
  the architectural patterns established by this project's independent
  AWS sibling, `aws-cloudops-mcp` — no code shared or imported between
  the two.
- Azure Resource Manager integration via `azure-mgmt-network`,
  `azure-mgmt-resource`, and `azure-mgmt-subscription`, with
  `arm/client_factory.py` as the single seam constructing Azure SDK
  clients: per-subscription `NetworkManagementClient`/
  `ResourceManagementClient` caching, a singleton tenant-scoped
  `SubscriptionClient`, and centralized retry/timeout configuration.
- Credential resolution exclusively via
  `azure.identity.DefaultAzureCredential` (service principal env vars,
  workload identity federation, managed identity, or an interactive
  Azure CLI/PowerShell/Developer CLI session) — no credential is ever
  accepted as tool input, stored, or logged.
- `AZURE_SUBSCRIPTION_ALLOWLIST`/`AZURE_TENANT_ALLOWLIST` (optional,
  comma-separated), enforced by `auth/session.py::SubscriptionContext`
  before any ARM client is constructed for a disallowed scope.
- Structured JSON logging (`logging/setup.py`) with per-request
  correlation IDs, mirroring the AWS sibling's log-field shape adapted
  to `subscription_id`/`resource_group` in place of `account_id`/`region`.
- `security/guardrails.py`: every ARM SDK call funnels through
  `assert_read_only_operation`, which allows only `get`/`list`-prefixed
  methods plus two explicitly justified exceptions —
  `begin_get_effective_route_table` and
  `begin_list_effective_network_security_groups` — genuinely read-only
  long-running computations that happen to use the SDK's `begin_`
  mutation-signaling prefix.
- Nineteen MCP tools across identity/context, subscriptions/tenants/
  locations, resource groups, virtual networks/subnets, route tables
  (including effective route tables), network security groups
  (including custom rules and effective NSGs), network interfaces,
  public IP addresses, VNet peerings, NAT gateways, load balancers, and
  application gateways — see [docs/tools.md](docs/tools.md).
- `arm/topology.py::get_vnet_topology` (`azure_get_vnet_topology`): a
  deterministic, single-VNet-scoped node/edge graph joining subnets,
  NSGs, route tables, NAT gateways, NICs, public IPs, and peerings, with
  `evidence` on every edge, stable `(node_type, node_id)`/
  `(source_id, target_id, relationship)` ordering, and explicit
  `CollectionWarning`s for any reference outside the VNet's own resource
  group rather than a silently dropped edge.
- `capability_meta()` on every tool
  (`{"cloud": "azure", "read_only": true, "resource_types": [...]}`) for
  future multi-cloud federation discovery, without requiring a Python
  import of this codebase.
- 175 offline unit tests (98%+ line coverage of `src/`). Azure has no
  moto-equivalent SDK mocking library, so every ARM SDK operation-group
  method is monkeypatched directly via `unittest.mock`, including a
  dedicated `tests/unit/test_mcp_smoke.py` suite that exercises every
  tool through the real `MCPServer.call_tool()` path (not just the ARM
  service layer) by monkeypatching the SDK client classes themselves
  before `build_server()` constructs its own `ClientFactory`.
- `azure-custom-role.json`: a least-privilege custom Azure RBAC role,
  narrower than the built-in `Reader` role, scoped to exactly the
  actions this milestone's tools need (including the two effective-*
  `/action` permissions).
- Dockerfile, docker-compose.yml, `.env.example`, and
  `mcp-client-config.example.json` for local development and deployment.
- Full documentation: [README.md](README.md),
  [docs/architecture.md](docs/architecture.md),
  [docs/security.md](docs/security.md), [docs/tools.md](docs/tools.md),
  [docs/development.md](docs/development.md).

### Fixed

- `auth/credentials.py`: `DefaultAzureCredential` rejects a unified
  `tenant_id` constructor kwarg outright (`TypeError`) in the installed
  SDK version — caught by `tests/unit/test_credentials.py` during
  development, before it could reach a real deployment. Fixed by passing
  the tenant to each sub-credential's own tenant-scoping kwarg
  (`interactive_browser_tenant_id`, `workload_identity_tenant_id`,
  `broker_tenant_id`, `shared_cache_tenant_id`) instead of a
  nonexistent unified one.
- Every tool accepting an optional `subscription_id` originally resolved
  it (via `SubscriptionContext.resolve_subscription_id`) *before*
  calling `execute_tool`, so a disallowed or unresolvable subscription
  raised outside `execute_tool`'s error-translation `try`/`except` and
  crashed the MCP tool call with an unhandled exception instead of
  returning this server's normal structured error envelope. Caught by
  `tests/unit/test_mcp_smoke.py` exercising the real `call_tool()` path.
  Fixed by introducing
  `tools/_shared.py::execute_tool_with_resolved_subscription`, which
  performs the resolution *inside* the same guarded call every other
  exception already passes through — every one of the thirteen
  affected tool functions was updated to use it.
