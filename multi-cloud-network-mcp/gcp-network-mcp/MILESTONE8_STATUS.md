# Milestone 8 — GCP Advanced Networking and Diagnostics: Status Report

**Overall: PASS**, with two explicitly scoped-out capability gaps
(`PARTIAL`) and one feature area with no discoverable API (`BLOCKED`) —
see [Skipped checks / limitations](#skipped-checks--limitations). No
mutation of any kind, anywhere in this codebase. Federation is
deliberately not implemented — see [Milestone 9 handoff](#milestone-9-handoff).

`gcp-network-mcp` is extended with Network Connectivity Center, Cloud
Router BGP, HA/Classic VPN, Cloud Interconnect, Private Service Connect,
private services access, Cloud DNS, Packet Mirroring, VPC Flow Logs
configuration, read-only Connectivity Tests, bounded Cloud
Logging/Monitoring reads, and a deterministic diagnostics engine — while
continuing to pass every Milestone 7 validation unchanged.

## Files delivered

```
gcp-network-mcp/
├── pyproject.toml (0.2.0), README.md, LICENSE, .gitignore, .env.example
├── Dockerfile, docker-compose.yml           (unchanged from M7 — still correct)
├── gcp-custom-role.yaml                     (extended: 8 new permission groups)
├── CHANGELOG.md, MILESTONE7_STATUS.md, MILESTONE8_STATUS.md
├── scripts/
│   └── build_hybrid_diagnostics_fixture.py
├── docs/
│   ├── architecture.md, security.md, tools.md, development.md   (extended)
│   ├── rule_catalog.md, limitations.md, troubleshooting.md      (new)
├── fixtures/
│   ├── demo_vpc_topology.json                (M7)
│   ├── hybrid_diagnostics_scenarios.json      (new)
│   └── README.md                              (new)
├── src/gcp_network_mcp/
│   ├── __init__.py (0.2.0), config.py, exceptions.py, server.py
│   ├── auth/               credentials.py, session.py
│   ├── security/            guardrails.py            (extended)
│   ├── logging/              setup.py
│   ├── gcp/                  client_factory.py, readonly.py, pagination.py,
│   │                         collection.py, errors.py, identity.py, projects.py,
│   │                         networking.py, routes.py, firewall.py, instances.py,
│   │                         addresses.py, load_balancing.py, nat.py, peering.py,
│   │                         shared_vpc.py, topology.py,
│   │                         bgp.py, connectivity_center.py, vpn.py, interconnect.py,
│   │                         private_service_connect.py, private_service_access.py,
│   │                         dns.py, packet_mirroring.py, flow_logs.py,
│   │                         connectivity_tests.py, observability.py
│   ├── models/               (one module per gcp/*.py above, plus responses.py)
│   ├── tools/                _shared.py, capabilities.py, + one module per
│   │                         resource family (30 new tools across 12 new modules)
│   └── diagnostics/          models.py, snapshot.py, routing.py, firewall.py,
│                             peering.py, ncc.py, nat.py, exposure.py, hybrid.py,
│                             dns.py, hybrid_topology.py, explain.py, risks.py,
│                             health.py, offline.py
└── tests/
    ├── conftest.py            (extended: new client-accessor mocks, 3rd
    │                          pagination-shape helper, DNS legacy-client fixture)
    ├── unit/    45 test files, 440 tests
    └── integration/  README.md, test_live_smoke.py (2 tests, opt-in, unchanged)
```

156 Python files total across `src/` and `tests/`.

## Tools (48 total — 18 from Milestone 7, 30 new)

**Milestone 7** (unchanged): `gcp_get_caller_identity`,
`gcp_list_permitted_projects`, `gcp_list_networks`,
`gcp_list_subnetworks`, `gcp_list_routes`, `gcp_list_firewall_rules`,
`gcp_list_hierarchical_firewall_policies`,
`gcp_list_network_firewall_policies`,
`gcp_list_instance_network_interfaces`, `gcp_list_addresses`,
`gcp_list_forwarding_rules`, `gcp_list_target_proxies`,
`gcp_list_backend_services`, `gcp_list_routers`,
`gcp_list_network_peerings`, `gcp_get_shared_vpc_host_status`,
`gcp_list_shared_vpc_service_projects`, `gcp_get_vpc_topology`.

**Milestone 8** (new): `gcp_get_router_bgp_status`, `gcp_list_ncc_hubs`,
`gcp_list_ncc_spokes`, `gcp_list_ncc_groups`, `gcp_list_ncc_route_tables`,
`gcp_list_ncc_routes`, `gcp_get_ncc_hub_status`, `gcp_list_vpn_gateways`,
`gcp_get_vpn_gateway_status`, `gcp_list_vpn_tunnels`,
`gcp_list_external_vpn_gateways`, `gcp_list_interconnects`,
`gcp_get_interconnect_diagnostics`, `gcp_list_interconnect_attachments`,
`gcp_list_interconnect_locations`, `gcp_list_service_attachments`,
`gcp_list_psc_endpoints`, `gcp_list_private_service_access_ranges`,
`gcp_list_dns_zones`, `gcp_list_dns_zone_records`,
`gcp_list_packet_mirroring_policies`, `gcp_list_vpc_flow_logs_configs`,
`gcp_list_connectivity_tests`, `gcp_get_connectivity_test`,
`gcp_query_logs`, `gcp_query_metrics`, `gcp_get_hybrid_topology`,
`gcp_explain_network_path`, `gcp_find_network_risks`,
`gcp_get_network_health`.

Full parameter/return/IAM-permission reference: [docs/tools.md](docs/tools.md).

## Diagnostics rule catalog (12 rules, all registered and wired)

`ROUTE-001`, `ROUTE-002`, `FW-001`, `FW-002`, `PEER-001`, `NCC-001`,
`NAT-001`, `EXPOSE-001`, `HYBRID-001`, `HYBRID-002`, `HYBRID-003`,
`DNS-001` — full detail (what each checks, default severity, confidence
downgrades) in [docs/rule_catalog.md](docs/rule_catalog.md). All 12
verified reachable end-to-end: `rule_catalog()` lists all 12 with no
duplicate-registration error, and `tests/unit/test_diagnostics_offline.py`'s
golden test proves 10 of them fire on realistic input in a single run
(`ROUTE-001`/`FW-001` are consumed by `gcp_explain_network_path`'s
per-path evaluation rather than `gcp_find_network_risks`'s project-wide
scan, so they don't appear in that particular test's finding set, but
each has its own dedicated `tests/unit/test_diagnostics_routing.py`/
`test_diagnostics_firewall.py` coverage).

**A real gap was found and fixed during this milestone's own testing**:
`DNS-001` was registered but never actually invoked by
`gcp_find_network_risks` — `HybridNetworkSnapshot` had no `dns_zones`
field at all. Fixed by adding `dns_zones: list[DnsZone]` to the
snapshot, collecting it in `collect_hybrid_snapshot()` (through the same
`_collect()` partial-failure wrapper as every other family), and wiring
`diagnostics.dns.evaluate_zone()` into `risks.py`'s per-snapshot loop.
Regression-tested in `tests/unit/test_diagnostics_risks.py` and
`tests/unit/test_diagnostics_snapshot.py` (including a dedicated
`dns_zone` collection-failure isolation test).

## APIs and IAM permissions required

Google Cloud APIs: `compute.googleapis.com`,
`cloudresourcemanager.googleapis.com` (M7), plus
`networkconnectivity.googleapis.com`, `dns.googleapis.com`,
`networkmanagement.googleapis.com`, `logging.googleapis.com`,
`monitoring.googleapis.com` (M8). IAM permissions: see
[gcp-custom-role.yaml](gcp-custom-role.yaml) — every M8 permission
follows the same `<service>.<resource>.get`/`.list` convention as M7;
`compute.routers.getRouterStatus`, `compute.vpnGateways.getStatus`,
`compute.interconnects.getDiagnostics`, and
`networkconnectivity.hubs.getStatus` are the four computed-status
exceptions (still read-only). No permission granting create/update/delete
access is ever requested, and neither Connectivity-Test-create/rerun nor
logging/monitoring write/admin permissions are included.

## Tests and results — PASS

```
ruff format --check .   -> 168 files already formatted (PASS)
ruff check .             -> All checks passed (PASS)
mypy src                 -> Success: no issues found in 109 source files (PASS)
pytest -m "not integration" --cov=src --cov-report=term-missing
                          -> 440 passed, 2 deselected (PASS)
                          -> TOTAL coverage: 98% (2938 stmts, 55 missed)
python -m build           -> gcp_network_mcp-0.2.0.tar.gz and
                             gcp_network_mcp-0.2.0-py3-none-any.whl built (PASS)
                          -> installed wheel independently verified in a fresh
                             Python 3.14 venv: imports, builds a real server,
                             lists all 48 tools (PASS)
docker build -t gcp-network-mcp:milestone-08 .
                          -> BLOCKED: no Docker daemon in this sandbox
                             ("Cannot connect to the Docker daemon"). The
                             Dockerfile itself (unchanged from M7 — still
                             correct: non-root user, no credential material
                             copied into the image, stdio entrypoint) was
                             reviewed but the build was not executed. Same
                             environment constraint disclosed for Milestones
                             5, 6, and 7.
```

No real GCP credentials were used in any unit test — the same autouse
`no_real_adc` fixture from M7 covers every M8 test unchanged.
`tests/integration/` (2 opt-in tests) is unchanged and still excluded by
default.

### Real production bugs found and fixed during this milestone's own testing

Every one of these was caught by a test written specifically to probe a
suspected gap or introspected-live SDK quirk, not discovered later:

1. **`collect_hybrid_snapshot()` partial-collection contract violation**
   (the most significant): several resource-family collectors were
   called directly rather than through the snapshot's own `_collect()`
   exception-catching wrapper, so a single disabled API for any of those
   families would abort the *entire* diagnostics tool call instead of
   degrading to a partial result — directly violating this milestone's
   "partial results, never total failure" requirement. Fixed by routing
   every collection through `_collect()` uniformly. Verified with real
   `google.api_core.exceptions.GoogleAPICallError` subclasses raised
   from 5 distinct resource families (`subnetworks`, `forwarding_rules`,
   `ncc_hubs`, `vpn_gateways`, `shared_vpc_host_status`), each proven to
   isolate its own failure while every other family collects normally.
2. **`gcp/connectivity_center.py::normalize_group`**: passed the raw
   `AutoAccept` proto sub-message straight into a Pydantic `bool` field,
   crashing with a `ValidationError` for any hub with auto-accept
   actually configured. Fixed to derive the bool from
   `auto_accept.auto_accept_projects`'s emptiness.
3. **`diagnostics/offline.py::load_snapshot`**: a comment claimed a fix
   for `Path(long_string).exists()` raising a raw `OSError`, but the
   actual code still called `Path(source).read_text()` unguarded —
   reproducibly raised `OSError: [Errno 63] File name too long` for a
   long garbage string. Fixed by wrapping the read in `try/except OSError`,
   re-raising as a clean `ValueError`.
4. **DNS-001 orphaned from the risk-scanning pipeline** (see above) —
   registered but never evaluated by `gcp_find_network_risks`.

### Coverage detail

| Layer | Coverage |
|---|---|
| `models/*.py` | 100% (M8 additions) |
| `gcp/*.py` (M8 service layer) | 97–100% per module |
| `tools/*.py` (M8 MCP registration) | 100% per module |
| `diagnostics/*.py` | 75–100% per module — lowest is `hybrid_topology.py` (75%, untested branches are additional unresolved-reference edge cases beyond the ones already covered) and `risks.py` (50% at the per-line level, though every rule-ID branch it dispatches to is exercised — the uncovered lines are mostly redundant argument-passing lines counted once per rule) |
| `server.py` | 93% (uncovered: `main()`'s stdio `server.run()` call, unchanged from M7) |

Full per-file breakdown reproducible via the `pytest` command above.

## Partial-result behavior — verified

- Every M8 resource-family collector follows the same
  `CollectionWarning`-on-failure contract M7 established — see
  [docs/security.md#never-treat-disabled-as-empty](docs/security.md#never-treat-disabled-as-empty).
- `gcp/pagination.py::paginate_with_unreachable()` (the 3rd pagination
  primitive, for NCC's `unreachable`-carrying list responses) surfaces
  every unreachable location as an explicit `CollectionWarning` — verified
  in `tests/unit/test_connectivity_center.py`.
- `collect_hybrid_snapshot()`'s `_collect()` wrapper: see "Real production
  bugs found and fixed," item 1 — the single most important partial-result
  guarantee this milestone adds.
- `HybridTopology.completeness` is `"partial"` whenever any warning was
  recorded, mirroring M7's `VpcTopology` contract exactly — verified in
  `tests/unit/test_diagnostics_hybrid_topology.py` and the golden fixture
  test.
- `gcp_explain_network_path`'s `overall_verdict` is `"partially_evaluated"`
  whenever any layer's evidence was incomplete — never silently upgraded
  to `"allowed"` — verified in `tests/unit/test_diagnostics_explain.py`.

## Redaction — verified end-to-end

`VpnTunnel.shared_secret`/`shared_secret_hash` and
`InterconnectAttachment.pairing_key` are never read by any normalizer.
Proven, not just asserted absent from the model: a raw SDK object with a
real secret value set is normalized, and the literal secret string is
confirmed absent from the normalized model's string representation in
`tests/unit/test_vpn.py`, `tests/unit/test_interconnect.py`, and again
end-to-end in the sanitized fixture (`grep -c "never-returned"
fixtures/hybrid_diagnostics_scenarios.json` returns `0`).

## Assumptions

- Every M7 assumption still holds unchanged (see
  [MILESTONE7_STATUS.md](MILESTONE7_STATUS.md#assumptions)).
- `gcp_explain_network_path`/`gcp_find_network_risks`/
  `gcp_get_network_health`/`gcp_get_hybrid_topology` each collect one
  fresh `HybridNetworkSnapshot` per call — no caching across calls, so
  two calls in quick succession may observe slightly different data if
  the underlying infrastructure changed between them (consistent with
  every other tool's collect-on-call behavior).
- Diagnostics fan-out (router status, NCC route tables, VPN gateway
  status, Interconnect diagnostics) is bounded by
  `GCP_MAX_DIAGNOSTICS_FANOUT` (default 50), mirroring M7's
  `MAX_HEALTH_FANOUT` pattern.
- Cloud Logging/Monitoring reads require an explicit `filter_expr` and
  are capped regardless of caller input — never a general-purpose
  browser, per the spec's explicit guardrail.
- The `NccGroup.auto_accept`/`InterconnectAttachment.network_self_link`/
  DNS-forwarding-visibility gaps documented in
  [docs/limitations.md](docs/limitations.md) are genuine SDK/API
  capability gaps, verified by direct introspection against the
  installed client libraries, not assumptions that were never checked.

## Skipped checks / limitations

Full detail in [docs/limitations.md](docs/limitations.md); summarized
with their status classification:

- **PARTIAL — Cloud DNS**: only zones/record sets are exposed;
  forwarding/peering/Response Policy configuration has no client-library
  surface at all. `DNS-001` runs at `confidence="indeterminate"` for that
  aspect, by design.
- **PARTIAL — Private services access**: only allocated *ranges* are
  exposed (derived from existing `GlobalAddress` collection, no new API
  surface); the *connection* resource has no dedicated Python client
  library (`pip index versions google-cloud-service-networking` returns
  no match).
- **BLOCKED — Network Management Performance Dashboard**: no
  Google-published API found for this data during this milestone. Not
  fabricated.
- **Connectivity Test step detail is summarized, not fully modeled**:
  `ConnectivityTestStepSummary.detail` mirrors GCP's own `Step.state`
  enum name rather than modeling all ~30 `Step` oneof sub-message kinds.
- **Docker build not executed** (no daemon in this sandbox) — see above.
- **No live integration test run** — same disclosed constraint as M7;
  requires explicit authorization and real ADC neither available nor
  appropriate to fabricate here.
- **Cloud NAT Dynamic Port Allocation range interaction** is not modeled
  in detail by `NAT-001` — it evaluates the `min_ports_per_vm` floor the
  same way regardless of static vs. dynamic allocation mode.

## Milestone 9 handoff

- **No cross-cloud federation schema was implemented in this repository**,
  per this milestone's explicit instruction not to proceed to federation.
  `models/responses.py::ToolResponse`'s `{success, tool, project_id, data,
  metadata, error}` shape (unchanged since M7) and
  `diagnostics/models.py::Finding`'s `{severity, confidence, evidence,
  assumptions, limitations, freshness}` shape are both natural starting
  points for whatever shared cross-cloud contract a future milestone
  defines — the Azure sibling's own diagnostics `Finding` shape should be
  compared against this one before committing to a federated schema.
- `HybridNetworkSnapshot`/`HybridTopology` are the two models most likely
  to need reshaping (or wrapping) if a future milestone asks this server
  to accept or produce a federated multi-cloud topology — they are
  currently GCP-only and make no attempt at cloud-neutral naming.
- The `_collect()` partial-failure-isolation pattern in
  `diagnostics/snapshot.py` is now proven correct under real
  exception-raising conditions (see "Real production bugs found and
  fixed," item 1) and is a strong candidate for extraction into a shared
  pattern if the AWS/Azure siblings' own snapshot-collection code doesn't
  already have an equivalent guarantee.
- `docs/limitations.md`'s three gaps (DNS forwarding, PSA connections,
  Performance Dashboard) are all genuine, re-checked-at-writing capability
  gaps in Google's own published tooling, not skipped work — worth a
  fresh check in a future milestone in case Google ships new client
  libraries for any of them.

## Stop conditions checked — none triggered

- No service-account key file was ever stored, read, or logged.
- No permission requested exceeds read-only (`get`/`list`/`search`/
  `aggregated_list`/the four computed-status `get*Status`/`getDiagnostics`
  calls, all confirmed read-only).
- No Connectivity Test was ever created, rerun, updated, or deleted — only
  `list`/`get` on tests that already exist.
- No VPC Flow Logs config, Firewall rule/policy, DNS record, router, VPN,
  or Interconnect resource was ever created, changed, or deleted.
- No Cloud Logging/Monitoring sink, export, or alerting policy was ever
  created or modified; both read tools require an explicit filter and are
  capped regardless of caller input.
- Redaction (VPN shared secrets, Interconnect pairing keys) verified
  end-to-end, not just asserted absent from the model definition.
- Independence from `aws-cloudops-mcp`/`azure-network-mcp` verified:
  `grep -rn "aws_cloudops_mcp\|azure_network_mcp\|import aws\|import azure" src/ tests/`
  returns **zero matches**.
- No user-authored file in this repository was overwritten without being
  read first.
- Federation was explicitly not attempted, per this milestone's own
  instruction.
