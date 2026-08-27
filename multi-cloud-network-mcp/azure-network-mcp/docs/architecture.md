# Architecture

## Layered design

```
AI / MCP Client
       |
       v
Azure Network MCP
       |
       +--- MCP Tool Layer
       |
       +--- Security Guardrails
       |
       +--- ARM Service Layer
       |
       +--- ARM Client Factory
       |
       +--- Authentication
       |
       v
Azure Resource Manager APIs
```

Each layer has one job and depends only on the layer(s) beneath it:

| Layer | Package | Responsibility |
|---|---|---|
| MCP Tool Layer | `azure_network_mcp.tools` | Defines MCP tool schemas (name, inputs, description); translates a tool call into a service-layer call; never touches the Azure SDK directly |
| Security Guardrails | `azure_network_mcp.security` | Rejects any Azure ARM operation that isn't recognizably read-only, regardless of which tool tried to call it |
| ARM Service Layer | `azure_network_mcp.arm` (`networking.py`, `route_tables.py`, `network_security_groups.py`, ...) | Calls specific ARM operation groups, applies pagination, normalizes responses into `azure_network_mcp.models` |
| ARM Client Factory | `azure_network_mcp.arm.client_factory` | The **only** place an Azure mgmt SDK client is constructed; owns subscription scoping, retry/timeout config, per-subscription client caching |
| Authentication | `azure_network_mcp.auth` (`credentials.py`, `session.py`) | Resolves the shared `DefaultAzureCredential`, enforces subscription/tenant allowlists |

The MCP transport (`azure_network_mcp.server`) only wires these layers
together and starts the stdio transport — it contains no Azure logic.

This mirrors the layered design this project's AWS sibling
(`aws-cloudops-mcp`) established, adapted to Azure's own SDK shape — this
repository does not import from, depend on, or share code with that
project; the parallel is architectural only.

### Why this separation matters

- A new tool can only reach Azure through the service layer, which can
  only reach Azure through the client factory, which enforces consistent
  subscription/timeout/retry handling.
- Every ARM SDK call — paginated or not — is funneled through
  `security.guardrails`, so a new tool cannot introduce a mutating call
  without an explicit, auditable change to the guardrail allowlist logic.
- The tool layer is a thin adapter. It can be tested, replaced, or
  extended (e.g. to support a different transport) without touching Azure
  logic.

## Request flow (example: `azure_list_virtual_networks`)

```
MCP Client
     |
     v
azure_list_virtual_networks(subscription_id=None)     [tools/networking.py]
     |
     v
execute_tool_with_resolved_subscription(...)           [tools/_shared.py]
     |  - generates a correlation/request ID
     |  - resolves subscription_id (explicit, or
     |    AZURE_DEFAULT_SUBSCRIPTION_ID), validated
     |    against the configured allowlist            [auth/session.py]
     v
networking.list_virtual_networks(client_factory, ...)  [arm/networking.py]
     |  - paginates VirtualNetworksOperations.list_all/list
     |  - normalizes address space, subnets, peerings
     v
client_factory.get_network_client(subscription_id)      [arm/client_factory.py]
     |  - returns a cached NetworkManagementClient, or builds one
     |  - applies retry/timeout config
     v
azure-mgmt-network -> Azure Resource Manager -> Azure Network API
     |
     v
ToolResponse.ok(data=[...], subscription_id=..., metadata={...})
```

`execute_tool_with_resolved_subscription` (not just `execute_tool`) is
used by every tool that accepts an optional `subscription_id`, because
subscription resolution itself can fail (no default configured, or an
explicitly-requested subscription outside the allowlist) — routing that
resolution through the same guarded call ensures a bad `subscription_id`
produces this server's normal structured error envelope instead of an
unhandled crash. See [`tools/_shared.py`](../src/azure_network_mcp/tools/_shared.py).

## Subscription and resource-group scoping

Unlike AWS's per-region `ec2.Client`, Azure Resource Manager's network
management clients are **subscription-scoped**: one `NetworkManagementClient`
per subscription serves every Azure region within it. Most `list_*` tools
therefore take an optional `subscription_id` (falling back to
`AZURE_DEFAULT_SUBSCRIPTION_ID`) and an optional `resource_group` — omit
`resource_group` to list across the whole subscription (`list_all`),
or pass it to scope to one resource group (`list`).

`SubscriptionClient` (used only for `azure_list_subscriptions`,
`azure_list_tenants`, and `azure_list_locations`) is tenant-scoped, not
subscription-scoped, so `ClientFactory` caches exactly one instance of it
regardless of how many subscriptions this server operates against.

## Bounded fan-out

`azure_list_resource_groups`'s `only_with_network_resources` filter needs
one extra `Resources.list_by_resource_group` call per resource group,
since ARM has no single call that answers "which resource groups contain
a `Microsoft.Network` resource." This fan-out is capped by
`Settings.max_fanout_calls` (default 50) — resource groups beyond the cap
are still returned unfiltered, with a `FANOUT_CAP_REACHED`
`CollectionWarning` in the response metadata, rather than silently
truncating the result list.

## Topology assembly (`azure_get_vnet_topology`)

`arm/topology.py` builds a deterministic node/edge graph for one virtual
network, scoped to that VNet's own resource group:

1. Pre-fetches every NSG, route table, NAT gateway, NIC, and public IP in
   the resource group into lookup dictionaries (one `list` call per
   resource type).
2. Joins subnets to their NSG/route-table/NAT-gateway associations by
   resource ID (case-insensitively, via `normalize_resource_id`).
3. Joins NICs to the subnet they reside in (via IP configuration) and any
   attached public IP.
4. Adds VNet peerings, with an orphan `peers_with_vnet` edge (plus an
   `OUT_OF_SCOPE_TARGET` warning) for a peering whose remote VNet has no
   node in this graph.

A reference to a resource **outside** the VNet's resource group (a subnet
whose NSG lives in a different resource group, a peering to a remote
VNet) still produces an edge — with no matching node — and a
`CollectionWarning` explaining the gap, rather than a silently dropped
edge or a node with no data behind it. Joining across resource groups
unboundedly would make this tool's cost unpredictable, so the scope
boundary is explicit and disclosed, not hidden.

Nodes are sorted by `(node_type, node_id)` and edges by
`(source_id, target_id, relationship)` before being returned, so two
calls against the same (unchanged) VNet produce byte-identical output —
required for any diffing or caching a client might do against this graph.

## Error translation

`azure.core.exceptions.HttpResponseError` (and its `ClientAuthenticationError`/
`ResourceNotFoundError` subclasses), `azure.identity.CredentialUnavailableError`,
and `azure.core.exceptions.ServiceRequestError` are translated into this
server's own `AzureNetworkMCPError` hierarchy in `tools/_shared.py`,
classified by HTTP status code (401/403/404) or exception type. No raw
Azure SDK exception, stack trace, or request URL ever reaches an MCP
client — see [docs/security.md#error-handling](security.md#error-handling).

## What this milestone does not do

- No mutation of any kind — see [docs/security.md](security.md).
- No reachability analysis. `azure_get_vnet_topology` is a configuration
  and attachment graph, not a proof that traffic can flow between two
  nodes — see [docs/security.md#no-reachability-claims](security.md#no-reachability-claims).
- No cross-cloud abstraction. Field names stay Azure-native
  (`resource_group`/`location`/`provisioning_state`) rather than being
  coerced into AWS's vocabulary; a future milestone may add a unifying
  layer across `aws-cloudops-mcp` and this repository, but this milestone
  deliberately does not attempt that.
