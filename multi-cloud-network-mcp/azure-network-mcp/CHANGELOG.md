# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
