# Milestone 6 Status Report — Azure Advanced Networking and Diagnostics

```
Milestone: 6 — Azure Advanced Networking and Diagnostics
Status: PASS
Date: 2026-08-27
```

## Prerequisite check

Milestone 5 was re-validated before starting this milestone's own work:
`ruff format --check`, `ruff check`, `mypy src`, and `pytest` (175 tests)
all passed cleanly, with no defects found beyond the two disclosed fixes
already recorded in Milestone 5's own status report and changelog.

## Scope

Extend `azure-network-mcp` with advanced connectivity (Virtual WAN/Hub,
VPN, ExpressRoute, Route Server), Private Link/DNS, Azure Firewall,
read-only Network Watcher/Monitor integration, and a deterministic
network diagnostics engine — while remaining independently deployable
and strictly read-only. Full detail in [CHANGELOG.md](CHANGELOG.md).

## Tools, SDK operations, and RBAC

67 MCP tools total (19 Milestone 5, 48 Milestone 6). Full per-tool
parameter tables are in [docs/tools.md](docs/tools.md#milestone-6-tools);
the complete RBAC action list is in
[azure-custom-role.json](azure-custom-role.json). Six ARM SDK clients now
in use: `NetworkManagementClient`, `ResourceManagementClient`,
`SubscriptionClient` (Milestone 5), plus `PrivateDnsManagementClient`,
`DnsResolverManagementClient`, and `MonitorManagementClient`
(Milestone 6), each cached per subscription (or, for `SubscriptionClient`,
once per process) by `ClientFactory`.

### Guardrail exceptions added

Three new explicitly-justified `begin_*` read-only exceptions (bringing
the total to five), each a genuinely read-only computation despite the
SDK's mutation-signaling `begin_` prefix — see
[docs/security.md#why-begin_-needs-five-narrow-exceptions](docs/security.md):

| Method | Operation group | What it computes |
|---|---|---|
| `begin_get_bgp_peer_status` | `VirtualNetworkGatewaysOperations` | Current BGP session state for a classic gateway's peers |
| `begin_list_advertised_routes` | `VirtualHubBgpConnectionsOperations` | Routes a hub/Route Server BGP connection advertised to its peer |
| `begin_list_learned_routes` | `VirtualHubBgpConnectionsOperations` | Routes a hub/Route Server BGP connection learned from its peer |

## Diagnostics rule catalog

Five rules — full detail in [docs/rule_catalog.md](docs/rule_catalog.md):

| Rule ID | Title | Default severity | Used by |
|---|---|---|---|
| `ROUTE-001` | Effective route resolution | info | `azure_explain_network_path` |
| `SEC-001` | Effective NSG rule evaluation | info | `azure_explain_network_path` |
| `EXPOSE-001` | Network interface internet exposure | medium | `azure_find_network_risks` |
| `CONSIST-001` | Degraded or failed resource/connection state | high | `azure_find_network_risks`, `azure_get_network_health` |
| `CONSIST-002` | Blackhole or orphaned user-defined route | medium | `azure_find_network_risks`, `azure_get_network_health` |

Architecturally leaner than the AWS sibling's own routing/security-group
engine by design: `ROUTE-001`/`SEC-001` lean on Azure's own effective-
route-table/effective-NSG computations (already merging system/UDR/BGP
routes and subnet+NIC-level NSG associations) rather than reimplementing
that merge logic — see
[docs/architecture.md#diagnostics-engine](docs/architecture.md#diagnostics-engine).

## Scenario coverage

Every scenario the milestone spec named by name has dedicated test
coverage:

| Scenario | Test(s) |
|---|---|
| vWAN propagation | `test_diagnostics_hybrid_topology.py::test_vwan_hub_vnet_propagation_produces_an_edge` |
| Custom hub routes | `test_hybrid_connectivity.py` (hub route table normalization), `test_diagnostics_hybrid_topology.py` |
| S2S VPN/BGP degradation | `test_diagnostics_consistency.py::test_unhealthy_vpn_connection_status_is_flagged` (parametrized over Disconnected/NotConnected/Degraded/Unknown) |
| ExpressRoute states | `test_diagnostics_consistency.py::test_degraded_express_route_circuit_is_flagged`, `test_diagnostics_hybrid_topology.py::test_express_route_gateway_circuit_connection_chain` |
| Private Endpoint DNS | `test_diagnostics_hybrid_topology.py::test_private_endpoint_resides_in_subnet` |
| Route Server peers | `test_hybrid_connectivity.py::test_list_route_servers_filters_to_standalone_hubs`, `test_diagnostics_hybrid_topology.py::test_route_server_hub_gets_route_server_node_type` |
| Asymmetric UDRs | `test_diagnostics_consistency.py::test_virtual_appliance_route_to_known_nic_is_not_flagged` / `test_virtual_appliance_route_to_unknown_ip_is_indeterminate` |
| NSG priority/default rules | `test_diagnostics_security.py::test_lowest_priority_number_wins_first_match`, `test_priority_100_beats_priority_200_for_same_traffic`, `test_default_deny_all_inbound_rule_still_evaluates_outbound_only` |
| Public exposure | `test_diagnostics_exposure.py` (5 tests: sensitive-port/non-sensitive severity split, restricted rule not flagged, no-public-IP never flagged, no-NSG-found indeterminate) |
| Azure Firewall path | `test_private_link_dns_firewall_watcher_monitor.py::test_list_azure_firewalls_extracts_public_ips`; firewall inventory participates in `azure_get_hybrid_topology`/health via standard resource collection (no dedicated firewall-path diagnostic rule — see Scope decisions below) |
| Partial RBAC | `test_diagnostics_snapshot.py::test_collect_hybrid_snapshot_degrades_gracefully_on_partial_rbac` |
| Unsupported region/API version | `test_diagnostics_snapshot.py::test_collect_hybrid_snapshot_degrades_gracefully_on_unsupported_region` |
| Throttling | `test_diagnostics_snapshot.py::test_collect_hybrid_snapshot_degrades_gracefully_on_throttling` |
| Stale metrics | `test_private_link_dns_firewall_watcher_monitor.py::test_get_metrics_flags_stale_when_no_datapoints` |

Golden-test evidence chains: every `Finding`-producing test above asserts
on `evidence`/`reasoning`/`confidence`/`limitations` content, not just a
severity/verdict string — see e.g.
`test_diagnostics_routing.py::test_route_evidence_traces_back_to_matched_route`.

No action/create/start packet-capture APIs: verified by
`tests/unit/test_no_mutation_calls.py` (static AST scan of every
`arm/*.py`/`tools/*.py` module for a hardcoded mutating method-name
literal or secret-shaped field access) plus by inspection — no
`arm/network_watcher.py` function calls `begin_get_troubleshooting`,
any `*_packet_capture*` method, or any connection-monitor/flow-log
create/start/stop method.

## Redactions

Every secret-shaped field this milestone's new resource types embed
directly is never read by any collector — see
[docs/security.md#redaction](docs/security.md#redaction) for the full
field/model table and
[docs/limitations.md](docs/limitations.md#scope-decisions-milestone-6)
for why `ExpressRouteCircuitAuthorizationsOperations` is never called at
all. Statically enforced by
`test_no_mutation_calls.py::test_no_arm_module_ever_reads_a_secret_shaped_field`,
and per-resource-type asserted with a deliberately obvious sentinel
secret value in `test_hybrid_connectivity.py` (9 dedicated redaction
tests, one per affected resource type/collector).

## Partial behavior / unsupported features

Disclosed in full in [docs/limitations.md](docs/limitations.md); summary:

- Network Watcher's `begin_get_network_configuration_diagnostic` and
  `begin_get_troubleshooting_result` are **not implemented** — stop
  condition triggered ("an SDK operation has unclear mutation
  semantics": both share a name shape with the genuinely mutating
  `begin_get_troubleshooting`). "Existing diagnostic result retrieval"
  from the milestone spec is instead satisfied by
  `azure_list_flow_logs`.
- Connection Monitor time-series data points are out of scope (Azure
  Monitor Logs, a distinct capability); `azure_list_connection_monitors`
  returns configuration and last-known status only.
- `EXPOSE-001` evaluates a NIC's configured (not Azure's computed
  effective) NSG rules, to keep the whole-resource-group scan bounded;
  disclosed on every `EXPOSE-001` finding's `assumptions` field.
- Azure Route Server has no dedicated ARM resource type; modeled as a
  filtered view over Virtual Hub, matching Azure's own actual
  representation.
- No independent verification against every Azure region/API version —
  a resource type unsupported in a given region degrades to an empty
  collection plus a warning rather than failing the whole call (see
  Scenario coverage above).

## Tests and validation

```
ruff format --check .    138 files already formatted
ruff check .              All checks passed!
mypy src                  Success: no issues found in 88 source files
pytest -m "not integration" --cov=src --cov-report=term-missing
                           306 passed, 95% line coverage (2818 statements, 140 missed)
python -m build            Successfully built azure_network_mcp-0.2.0.tar.gz
                            and azure_network_mcp-0.2.0-py3-none-any.whl
```

131 new tests since Milestone 5 (175 → 306), including:

- 9 hybrid-connectivity ARM-layer tests with explicit secret-redaction
  assertions (`test_hybrid_connectivity.py`)
- 8 Private Link/DNS/Firewall/Watcher/Monitor ARM-layer tests
  (`test_private_link_dns_firewall_watcher_monitor.py`)
- 61 diagnostics-engine tests across 9 files (routing, security,
  exposure, consistency, snapshot, hybrid topology, explain, risks,
  health, offline)
- 48 end-to-end MCP smoke tests for every Milestone 6 tool
  (`test_mcp_smoke_milestone6.py`), exercising the real
  `MCPServer.call_tool()` path
- Updated `test_server.py`/`test_no_mutation_calls.py` covering all 67
  tools and both mutation/secret-field static scans

An offline diagnostics smoke test also ran successfully against
[fixtures/demo_hybrid_snapshot.json](fixtures/demo_hybrid_snapshot.json)
(a hand-built fixture reproducing an `EXPOSE-001`, `CONSIST-001`, and
`CONSIST-002` finding at once, plus a topology with `virtual_network`
and `vpn_gateway` node types) — see `test_diagnostics_offline.py`.

**`docker build` was not run** — the Docker daemon is unavailable in
this sandbox (`docker info` fails), the same disclosed constraint from
Milestone 5's own status report. The `Dockerfile` is unchanged from
Milestone 5 (no new runtime dependencies require image changes beyond
the three new `azure-mgmt-*` packages already declared in
`pyproject.toml`, which `pip install .` inside the image picks up
automatically) but has not been built or run in this environment.

Live checks were **not run** (no Azure credentials available in this
sandbox); `tests/integration/test_live_azure.py` remains structurally
present from Milestone 5, not yet extended with Milestone 6-specific
live assertions, and continues to require explicit `pytest -m integration`
plus real read-only Azure credentials to execute.

## Performance

No performance regressions expected: every new collector follows the
same bounded-pagination (`arm.pagination.paginate`, capped by
`MAX_PAGE_RESULTS`) and bounded-fan-out (`MAX_FANOUT_CALLS`,
`diagnostics.health.MAX_METRIC_RESOURCES`) patterns Milestone 5
established. `diagnostics.snapshot.collect_hybrid_snapshot`'s own cost
scales with the number of distinct resource families actually present in
one resource group (VPN/ExpressRoute gateways each add one extra
per-gateway connections call) — disclosed in
[docs/troubleshooting.md](docs/troubleshooting.md#azure_get_hybrid_topologyazure_find_network_risksazure_get_network_health-are-slow-or-hit-rbac-errors-on-some-resource-families).

## Independence and guardrail confirmation

`grep -r "aws_cloudops_mcp\|import aws" src/ tests/` returns three
matches, all inside docstrings that name the AWS sibling by name for
architectural-parallel context (e.g. "Mirrors this project's AWS
sibling's `aws_cloudops_mcp.diagnostics`") — never an actual `import`
statement. No AWS/GCP/federation/Aviatrix code exists anywhere in this
repository, and this repository does not require `aws-cloudops-mcp` to
be present, installed, or importable to build, test, or run. No tool,
and no ARM SDK call reachable from a tool, can create, update, or delete
an Azure resource, start a Network Watcher diagnostic run, retrieve a
secret, or run a packet capture.

## Milestone 9 handoff

This milestone deliberately introduces no cross-cloud data contract —
every model field name stays Azure-native
(`resource_group`/`location`/`provisioning_state`, not a forced AWS
vocabulary), matching Milestone 5's own stated boundary. When a future
milestone (named as Milestone 9 in the spec this work was scoped against)
takes on federation across `aws-cloudops-mcp` and this repository, the
natural seam points are:

- `models/responses.py::ToolResponse` (already shaped like the AWS
  sibling's envelope, with Azure-native field names substituted in) as
  the response-shape contract to unify.
- `diagnostics/models.py::Finding` (already structurally identical to
  the AWS sibling's own `Finding` contract — same field set, same
  `confidence: "indeterminate"` guarantee) as the finding-shape contract
  to unify.
- `tools/capabilities.py::capability_meta()` (`{"cloud": "azure", ...}`)
  as the per-tool discovery mechanism a federation layer would query
  without importing either codebase.

No work toward federation itself was started in this milestone, per its
own explicit stop condition ("Do not proceed to federation").
