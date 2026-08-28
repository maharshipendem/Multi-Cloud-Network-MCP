# Milestone 7 — GCP Network MCP Foundation: Status Report

**Overall: PASS**

`gcp-network-mcp` is a complete, independent, read-only MCP server for
Google Cloud network operations, built to the same rigor as the `aws-cloudops-mcp`
and `azure-network-mcp` siblings in this family, without importing or
depending on either.

## Files delivered

```
gcp-network-mcp/
├── pyproject.toml, README.md, LICENSE, .gitignore, .env.example
├── Dockerfile, docker-compose.yml
├── gcp-custom-role.yaml
├── CHANGELOG.md, MILESTONE7_STATUS.md
├── docs/
│   ├── architecture.md, security.md, tools.md, development.md
├── fixtures/
│   └── demo_vpc_topology.json
├── src/gcp_network_mcp/
│   ├── __init__.py, config.py, exceptions.py, server.py
│   ├── auth/            credentials.py, session.py
│   ├── security/         guardrails.py
│   ├── logging/           setup.py
│   ├── gcp/               client_factory.py, readonly.py, pagination.py,
│   │                      collection.py, errors.py, identity.py, projects.py,
│   │                      networking.py, routes.py, firewall.py, instances.py,
│   │                      addresses.py, load_balancing.py, nat.py, peering.py,
│   │                      shared_vpc.py, topology.py
│   ├── models/            common.py, identity.py, projects.py, networking.py,
│   │                      routes.py, firewall.py, instances.py, addresses.py,
│   │                      load_balancing.py, nat.py, peering.py, shared_vpc.py,
│   │                      topology.py, responses.py
│   └── tools/              _shared.py, capabilities.py, identity.py, projects.py,
│                           networking.py, routes.py, firewall.py, instances.py,
│                           addresses.py, load_balancing.py, nat.py, peering.py,
│                           shared_vpc.py, topology.py
└── tests/
    ├── conftest.py
    ├── unit/    18 test files, 145 tests
    └── integration/  README.md, test_live_smoke.py (2 tests, opt-in)
```

81 Python files total across `src/` and `tests/`.

## Tools (18)

`gcp_get_caller_identity`, `gcp_list_permitted_projects`,
`gcp_list_networks`, `gcp_list_subnetworks`, `gcp_list_routes`,
`gcp_list_firewall_rules`, `gcp_list_hierarchical_firewall_policies`,
`gcp_list_network_firewall_policies`, `gcp_list_instance_network_interfaces`,
`gcp_list_addresses`, `gcp_list_forwarding_rules`, `gcp_list_target_proxies`,
`gcp_list_backend_services`, `gcp_list_routers`, `gcp_list_network_peerings`,
`gcp_get_shared_vpc_host_status`, `gcp_list_shared_vpc_service_projects`,
`gcp_get_vpc_topology`.

Full parameter/return/IAM-permission reference: [docs/tools.md](docs/tools.md).

**Deliberately out of scope for this milestone** (per the spec's explicit
instruction): no advanced hybrid-connectivity diagnostics engine
analogous to the Azure sibling's Milestone 6 (`azure_get_hybrid_topology`/
`azure_find_network_risks`/etc.) — this milestone is foundational
inventory + one deterministic topology tool only.

## APIs and IAM permissions required

Google Cloud APIs: `compute.googleapis.com`, `cloudresourcemanager.googleapis.com`.
IAM permissions: see [gcp-custom-role.yaml](gcp-custom-role.yaml) — every
permission follows the `<service>.<resource>.get`/`.list` convention;
no permission granting create/update/delete access is ever requested.

## Tests and results — PASS

```
ruff format --check .   -> 88 files already formatted (PASS)
ruff check .             -> All checks passed (PASS)
mypy src                 -> Success: no issues found in 59 source files (PASS)
pytest -m "not integration" --cov=src --cov-report=term-missing
                          -> 145 passed, 2 deselected (PASS)
                          -> TOTAL coverage: 99% (1236 stmts, 18 missed)
python -m build           -> gcp_network_mcp-0.1.0.tar.gz and
                             gcp_network_mcp-0.1.0-py3-none-any.whl built (PASS)
docker build -t gcp-network-mcp:milestone-07 .
                          -> BLOCKED: no Docker daemon in this sandbox
                             ("Cannot connect to the Docker daemon"). The
                             Dockerfile itself was reviewed for correctness
                             (non-root user, no credential material copied
                             into the image, stdio entrypoint) but the
                             build was not executed. Same environment
                             constraint disclosed for Milestones 5 and 6.
```

No real GCP credentials were used in any unit test — `tests/conftest.py`'s
autouse `no_real_adc` fixture makes an accidental real ADC call fail
loudly. `tests/integration/` (2 opt-in tests) requires real, explicitly
authorized read-only ADC and is excluded by default.

### Coverage detail

| Layer | Coverage |
|---|---|
| `models/*.py` | 100% |
| `auth/*.py`, `security/guardrails.py`, `exceptions.py` | 100% |
| `gcp/*.py` (service layer) | 94–100% per module |
| `tools/*.py` (MCP registration) | 93–100% per module |
| `server.py` | 91% (uncovered: `main()`'s stdio `server.run()` call — not exercised by unit tests, by design) |

Full per-file breakdown reproducible via the `pytest` command above.

## Partial-result behavior — verified

- `gcp/pagination.py::paginate_aggregated()` filters GCP's own
  `NO_RESULTS_ON_PAGE` warning as benign, surfaces every other per-scope
  warning code and every `unreachables` entry as an explicit
  `CollectionWarning` — verified in
  `tests/unit/test_pagination_and_common_models.py`.
- `gcp/errors.py::translate_gcp_error()` distinguishes a disabled-API 403
  (`ApiNotEnabledError`) from a permission-gap 403 (`AuthorizationError`)
  by message-text marker — verified in `tests/unit/test_guardrails_and_errors.py`.
- `gcp_get_vpc_topology`'s `completeness` field is `"partial"` whenever
  any warning was recorded during collection (an unresolvable peer
  network, a subnetwork referencing a network outside this project's
  visible set, an unreachable scope), never silently `"complete"` —
  verified in `tests/unit/test_topology.py` (6 scenarios, including two
  distinct orphan-reference cases: a subnetwork→network edge that gets
  no fabricated node vs. a peering→network edge that does get an
  `external_network` node, matching how much information is actually
  knowable in each case).
- `gcp_list_backend_services`: a `get_health` failure for one backend
  group becomes a `CollectionWarning`, not an exception that aborts the
  whole tool call — verified in `tests/unit/test_load_balancing.py`.
- `gcp_list_permitted_projects` (allowlist mode): an unreadable
  allowlisted project becomes a warning, the readable ones still return
  — verified in `tests/unit/test_projects.py`.

## Assumptions

- "Permitted projects" without an allowlist means whatever
  `resourcemanager.projects.searchProjects` returns for the configured
  identity — the same "IAM-bindings-define-scope" default the AWS/Azure
  siblings use.
- Cloud NAT is exposed only via its parent Router (`Router.nats`) — GCP
  has no separate NAT-listing API, so `gcp_list_routers` is this
  server's NAT-inventory tool, per the spec's explicit allowance for
  this pattern.
- Backend service health fan-out is bounded at `MAX_HEALTH_FANOUT` (20)
  backend groups per service per call, to keep a single tool invocation
  from triggering an unbounded number of `get_health` requests against a
  backend service with many groups.
- The custom IAM role in `gcp-custom-role.yaml` lists permissions by
  GCP's documented naming convention; its module docstring explicitly
  flags that the exact list should be verified against GCP's live IAM
  permissions reference before granting in a production organization,
  since a static list cannot self-verify against a real project's
  current permission set.

## Global vs. regional/zonal handling

- **Global-only** (plain `list(project=)`, no aggregated variant):
  Networks, Routes, Firewalls, GlobalAddresses, GlobalForwardingRules.
- **Regional/zonal, collected via `aggregated_list(project=)`** (spans
  every scope in one call): Subnetworks, Instances, Addresses,
  ForwardingRules, TargetHttpProxies, TargetHttpsProxies,
  BackendServices, Routers.
- **Org/folder-scoped, not project-scoped at all**: hierarchical
  Firewall Policies (`FirewallPoliciesClient.list` takes `parent_id`, no
  `project` parameter) — `gcp_list_hierarchical_firewall_policies`
  requires an explicit `parent_id`, distinct from every other tool's
  optional `project_id`.
- Every normalized model's `region`/`zone` fields are derived from
  parsing the resource's own `self_link` (`models/common.py::parse_self_link()`),
  not assumed from the calling context — verified for global (`scope="global"`),
  regional (`scope="regions/..."`), and zonal (`scope="zones/..."`)
  self-links in `tests/unit/test_pagination_and_common_models.py`.

## Skipped checks / limitations

- **Docker build not executed** (no daemon in this sandbox) — see above.
- **No live integration test run** — `tests/integration/` exists and is
  structurally correct (verified to be properly deselected by default),
  but was not run against a real GCP project in this session; that
  requires explicit authorization and real ADC neither available nor
  appropriate to fabricate here.
- **Regional backend service health** is fetched via
  `RegionBackendServicesClient.get_health`, distinct from the global
  `BackendServicesClient.get_health` — both paths are implemented and
  unit-tested for the global case; the regional dispatch branch itself
  (client selection based on the backend service's parsed region) is
  exercised in `tests/unit/test_load_balancing.py`'s health tests
  indirectly through the shared `_fetch_health` helper, but no test
  constructs a genuinely regional `BackendService` end-to-end — a minor
  gap, not a correctness concern (the branch logic is a single `if
  region:` on an already-tested `parse_self_link()` call).
- **Asset Inventory** was deliberately never made a dependency for any
  tool, per the spec — every tool works from the standard Compute
  Engine/Resource Manager APIs alone.

## Milestone 8 handoff

- This server exposes `models/responses.py::ToolResponse` with the same
  `{success, tool, <scope>_id, data, metadata, error}` shape as the
  AWS/Azure siblings (scoped by `project_id` here, `account_id`/
  `subscription_id` there) — ready for a future cross-cloud contract
  pass without needing a response-shape migration first.
- `models/common.py::CollectionWarning` already carries the same fields
  (`resource_type`, `code`, `message`) as the AWS/Azure siblings'
  equivalents, plus GCP-specific `project_id`/`scope` — a natural
  reference point for whatever shared partial-result contract Milestone
  9 defines.
- `gcp/topology.py`'s node/edge/evidence shape
  (`TopologyNode`/`TopologyEdge` with a mandatory `evidence` string per
  edge) matches the AWS/Azure siblings' topology tools' contract
  precisely enough that a future federated topology tool could
  plausibly merge all three without reshaping any of them first.
- Not yet done, deliberately out of this milestone's scope: any
  diagnostics/reasoning engine (route/firewall path explanation, risk
  findings) analogous to the Azure sibling's Milestone 6 — a natural
  candidate for whichever milestone extends GCP to parity with Azure's
  diagnostics surface.

## Stop conditions checked — none triggered

- No service-account key file was ever stored, read, or logged.
- No permission requested exceeds read-only (`get`/`list`/`search`/
  `aggregated_list`).
- Independence from `aws-cloudops-mcp`/`azure-network-mcp` verified:
  `grep -rn "aws_cloudops_mcp\|azure_network_mcp\|import aws\|import azure" src/ tests/`
  returns **zero matches**.
- No user-authored file in this repository was overwritten without
  being read first.
