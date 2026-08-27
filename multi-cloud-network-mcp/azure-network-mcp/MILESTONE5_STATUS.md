# Milestone 5 Status Report — Azure Network MCP Foundation

```
Milestone: 5 — Azure Network MCP Foundation
Status: PASS
Date: 2026-08-27
```

## Scope

Build a fully independent, production-quality, read-only Azure Network
MCP server (`azure-network-mcp`) reusing `aws-cloudops-mcp`'s
*architectural patterns only* — no code import, no dependency on that
project. This is the first milestone in this repository; there is no
prior-milestone re-validation step.

## Implemented

### Foundation

- `config.py` — environment-variable-driven `Settings`
  (`pydantic-settings`), with `AZURE_TENANT_ID`/`AZURE_CLIENT_ID`
  documented as non-secret identity-scoping identifiers, never secrets.
- `logging/setup.py` — structured JSON logging to stderr, with
  `subscription_id`/`resource_group`/`duration_ms`/`status`/
  `azure_error_code` extra fields and a request-ID `ContextVar`.
- `exceptions.py` — `AzureNetworkMCPError` hierarchy
  (`AuthenticationError`, `AuthorizationError`, `AzureServiceError`,
  `SubscriptionNotAllowedError`, `InvalidConfigurationError`,
  `ToolExecutionError`, `GuardrailViolationError`, `ResourceNotFoundError`).
- `auth/credentials.py` — a single, process-wide cached
  `DefaultAzureCredential`, never calling `get_token()` directly and
  never exposing token/secret material.
- `auth/session.py::SubscriptionContext` — subscription resolution
  (explicit value, or `AZURE_DEFAULT_SUBSCRIPTION_ID`) plus
  subscription/tenant allowlist enforcement, the single choke point
  every tool passes through before an ARM client is built.
- `arm/client_factory.py::ClientFactory` — the only place an Azure mgmt
  SDK client is constructed; per-subscription
  `NetworkManagementClient`/`ResourceManagementClient` caching, a
  singleton tenant-scoped `SubscriptionClient`, centralized retry/
  timeout config.
- `security/guardrails.py` — `assert_read_only_operation()`, the single
  choke point every ARM SDK call passes through: allows `get`/`list`
  prefixes plus two explicitly justified `begin_*` exceptions
  (`begin_get_effective_route_table`,
  `begin_list_effective_network_security_groups`), rejects everything
  else via keyword/prefix matching.
- `arm/pagination.py`, `arm/readonly.py`, `arm/collection.py`,
  `arm/tags.py` — shared plumbing: bounded pagination with per-page call
  counting, read-only-asserted dispatch (including LRO-poller
  resolution for the two effective-* operations), a call counter for
  `azure_get_vnet_topology`'s `api_call_count`, and tag normalization.
- `models/common.py` — `AzureResource` base model (full provenance:
  `resource_group`, `location`, `provisioning_state`, `tags`,
  `observed_at`, `source_api`, `collection_completeness`, from day one),
  `parse_resource_id()` (hand-built ARM resource ID parser, verified
  against full/VNet-only/RG-only/malformed IDs, never raises).

### ARM service layer and models

Thirteen `arm/*.py` modules and five `models/*.py` modules covering
every resource type in scope: identity, subscriptions/tenants/locations,
resource groups, virtual networks/subnets, route tables (+ effective
route table), network security groups (+ security rules + effective
NSGs), network interfaces, public IP addresses, VNet peerings, NAT
gateways, load balancers, application gateways, and
`arm/topology.py::get_vnet_topology` joining all of the above into one
graph.

### Tools

| Tool | Purpose | RBAC actions |
|---|---|---|
| `azure_get_caller_identity` | Credential type + tenant/subscription context | none |
| `azure_list_subscriptions` | Subscriptions visible to the identity | `Microsoft.Resources/subscriptions/read` |
| `azure_list_tenants` | Tenants visible to the identity | none |
| `azure_list_locations` | Regions available to a subscription | `Microsoft.Resources/subscriptions/locations/read` |
| `azure_list_resource_groups` | Resource groups, with network-focused filter | `.../resourceGroups/read`, `.../resources/read` |
| `azure_list_virtual_networks` | VNets, address space, peering summaries | `Microsoft.Network/virtualNetworks/read` |
| `azure_list_subnets` | Subnets, associations, endpoints, delegations | `.../virtualNetworks/subnets/read` |
| `azure_list_route_tables` | Route tables and their routes | `Microsoft.Network/routeTables/read` |
| `azure_get_effective_route_table` | Effective route table for one NIC | `.../networkInterfaces/effectiveRouteTable/action` |
| `azure_list_network_security_groups` | NSGs, custom + default rules | `Microsoft.Network/networkSecurityGroups/read` |
| `azure_list_security_rules` | One NSG's custom rules | `.../networkSecurityGroups/securityRules/read` |
| `azure_get_effective_network_security_groups` | Effective NSGs/rules for one NIC | `.../networkInterfaces/effectiveNetworkSecurityGroups/action` |
| `azure_list_network_interfaces` | NICs, IP configs, NSG/VM association | `Microsoft.Network/networkInterfaces/read` |
| `azure_list_public_ip_addresses` | Public IPs, associated resource | `Microsoft.Network/publicIPAddresses/read` |
| `azure_list_virtual_network_peerings` | VNet peerings, connection state | `.../virtualNetworks/virtualNetworkPeerings/read` |
| `azure_list_nat_gateways` | NAT gateways, attached IPs/subnets | `Microsoft.Network/natGateways/read` |
| `azure_list_load_balancers` | Load balancers, rules, pools, probes | `Microsoft.Network/loadBalancers/read` |
| `azure_list_application_gateways` | App gateways, listeners, both state fields | `Microsoft.Network/applicationGateways/read` |
| `azure_get_vnet_topology` | Deterministic single-VNet topology graph | union of the above |

Full I/O schemas are in [docs/tools.md](docs/tools.md). Total tool
count: **19**. Every tool declares `capability_meta()`
(`{"cloud": "azure", "read_only": true, "resource_types": [...]}`) and a
non-empty description — verified by
`tests/unit/test_server.py::test_each_tool_declares_a_description` /
`test_each_tool_declares_read_only_capability_metadata` /
`test_no_tool_name_implies_mutation`.

### Guardrails and independence

- No tool, and no ARM SDK call reachable from a tool, can mutate an
  Azure resource — enforced by `security.guardrails` at the ARM call
  layer, and independently confirmed by
  `tests/unit/test_no_mutation_calls.py`, a static scan of every
  `arm/*.py` and `tools/*.py` source file for a hardcoded mutating
  method-name string literal (not just a runtime-logic test).
- No Network Watcher action that creates a persistent resource, no
  secret/token retrieval, and no AWS/GCP/federation/Aviatrix code exist
  anywhere in this repository — confirmed by inspection; this repository
  imports nothing from `aws-cloudops-mcp`.
- Never recommends `Owner`/`Contributor` — `docs/security.md` and
  `azure-custom-role.json` both scope to read-only actions plus the two
  effective-* `/action` permissions only.
- Partial subscription coverage is never hidden: bounded fan-out
  (`azure_list_resource_groups`'s `only_with_network_resources`) and
  topology out-of-scope references both surface an explicit
  `CollectionWarning` rather than silently omitting data.

## Fixes found and applied during this milestone's own development

Both were caught by this milestone's own test suite before ever reaching
a real deployment — see [CHANGELOG.md](CHANGELOG.md#fixed) for the full
detail:

1. **`auth/credentials.py`**: `DefaultAzureCredential` rejects a unified
   `tenant_id` constructor kwarg outright (a real behavior of the
   installed `azure-identity` SDK version, verified via
   `inspect.getsource`, not a guess) — fixed by passing the tenant to
   each sub-credential's own tenant-scoping kwarg instead.
2. **Every tool with an optional `subscription_id`** originally resolved
   it *before* calling `execute_tool`, so a disallowed/unresolvable
   subscription crashed the MCP tool call with an unhandled exception
   instead of this server's normal structured error envelope — fixed by
   `tools/_shared.py::execute_tool_with_resolved_subscription`, applied
   across all thirteen affected tool functions.

## Validation

```
ruff format --check .    83 files already formatted
ruff check .              All checks passed!
mypy src                  Success: no issues found in 51 source files
pytest -m "not integration" --cov=src --cov-report=term-missing
                           175 passed, 99% line coverage
python -m build            Successfully built azure_network_mcp-0.1.0.tar.gz
                            and azure_network_mcp-0.1.0-py3-none-any.whl
```

`mypy` required adding the `pydantic.mypy` plugin
(`[tool.mypy] plugins = ["pydantic.mypy"]`) — without it, mypy cannot
resolve `pydantic_settings.BaseSettings`'s private constructor kwargs
(`_env_file`, etc.) used throughout the test suite to isolate `Settings`
instances from any real `.env` file; this is a documented mypy/
pydantic-settings interaction, reproduced and confirmed independent of
this project's own configuration.

An offline MCP smoke test (`tests/unit/test_mcp_smoke.py`) exercises the
real `MCPServer.call_tool()` path — not just the ARM service layer — for
all 19 tools, by monkeypatching the SDK client classes
(`NetworkManagementClient`, `ResourceManagementClient`,
`SubscriptionClient`) before `build_server()` constructs its own
`ClientFactory`. This includes: a successful call for every tool, an
error envelope (not a crash) for a disallowed subscription, an error
envelope for a missing default subscription, and rejection of an unknown
tool name.

**`docker build` was not run** — the Docker daemon is unavailable in this
sandbox (`docker info` fails), the same constraint disclosed in this
project's AWS sibling's own status reports. The `Dockerfile` and
`docker-compose.yml` are present and structurally mirror the AWS
sibling's working configuration (non-root user, credentials supplied
only at runtime, `ENTRYPOINT ["azure-network-mcp"]`), but have not been
built or run in this environment. Building and running them in an
environment with Docker available is recommended before relying on the
container image in production.

## Test coverage detail

175 unit tests, 99% line coverage of `src/azure_network_mcp/`
(1121 statements, 10 missed — all in thin tool-wrapper error branches
and `server.py`'s `if __name__ == "__main__"` guard). Coverage areas:

- Credential selection, caching, and the `tenant_id`-kwarg failure mode
  (`test_credentials.py`)
- Subscription/tenant allowlist enforcement, including fail-closed
  behavior when a tenant allowlist is configured but the tenant is
  unknown (`test_session.py`)
- Client caching per subscription, tenant-allowlist enforcement at
  `ClientFactory.__init__` time (`test_client_factory.py`)
- Pagination call-counting, one record per page (`test_pagination.py`)
- Guardrail allow/block matrix, including every documented mutating
  keyword and the two explicit `begin_*` exceptions (`test_guardrails.py`)
- Static no-hardcoded-mutating-method-name scan across `arm/`/`tools/`
  (`test_no_mutation_calls.py`)
- Every resource normalizer: VNets/subnets (service endpoints,
  delegations, unassociated subnets), route tables (every UDR next-hop
  type: `VirtualAppliance`/`VnetLocal`/`Internet`/`None`/
  `VirtualNetworkGateway`), NSGs (custom vs. default rules kept
  separate, priorities), NICs (IP configs, primary flag, public IP
  association), public IPs (associated vs. unattached), peerings (every
  `peering_state`: `Initiated`/`Connected`/`Disconnected`), NAT gateways,
  load balancers/application gateways (including the
  `http_listeners`-vs-`listeners` SDK field fallback, and
  `operational_state` vs. `provisioning_state`)
- Topology assembly: full graph construction, VNet-not-found error,
  out-of-scope subnet reference warning, orphan peering warning,
  deterministic ordering across repeated calls, `api_call_count`
- `execute_tool`/`execute_tool_with_resolved_subscription`: every error
  type translated (401/403/404, `CredentialUnavailableError`,
  `ClientAuthenticationError`, `ServiceRequestError`, unexpected
  exception never leaking internal detail), `CollectionResult`
  unwrapping, distinct request IDs per call
- Full MCP tool registration and `call_tool()` end-to-end smoke coverage

## Known limitations (disclosed, not hidden)

- Per-subscription tenant allowlist enforcement is not possible via the
  installed `azure-mgmt-subscription` SDK (`Subscription` has no
  `tenant_id` field) — the tenant allowlist is enforced once, against
  the statically-configured credential tenant, documented in
  `arm/client_factory.py` and `docs/security.md`.
- `docker build`/`docker run` were not exercised in this sandbox (no
  Docker daemon available) — see Validation above.
- Integration tests (`tests/integration/`, `@pytest.mark.integration`)
  were written for structure but not run against a real Azure
  subscription in this session (none was available); they are excluded
  from the default `pytest` run via `pyproject.toml`'s `addopts`.

## Independence confirmation

`grep -r "aws_cloudops_mcp\|import aws" src/ tests/` returns no matches.
This repository has its own `pyproject.toml`, its own dependency set,
and does not require `aws-cloudops-mcp` to be present, installed, or
importable to build, test, or run.
