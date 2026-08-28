# Troubleshooting

## A `azure_list_*`/`azure_get_*` tool returns `success: false`

Check `error.type` in the response (see
[docs/security.md#error-handling](security.md#error-handling)):

| `error.type` | Likely cause | What to check |
|---|---|---|
| `AUTHENTICATION_ERROR` | Missing/expired/invalid credential | Run `az login` (or check the service principal env vars / managed identity config); see [docs/security.md#credential-handling](security.md#credential-handling). |
| `AUTHORIZATION_ERROR` | The configured identity lacks the RBAC action this call needs | Compare against [`azure-custom-role.json`](../azure-custom-role.json) or assign the built-in `Reader` role; check the `azure_error_code` field in server logs for the specific denied action. |
| `SUBSCRIPTION_NOT_ALLOWED` | `AZURE_SUBSCRIPTION_ALLOWLIST`/`AZURE_TENANT_ALLOWLIST` is configured and the requested (or default) subscription/tenant isn't in it | Add the subscription/tenant ID to the allowlist, or pass a different `subscription_id`. |
| `INVALID_CONFIGURATION` | No `subscription_id` was given and `AZURE_DEFAULT_SUBSCRIPTION_ID` isn't set | Pass `subscription_id` explicitly, or set the default. |
| `RESOURCE_NOT_FOUND` | The named resource group/resource doesn't exist, or a 404 from Azure | Check spelling/case of `resource_group` and any named resource (e.g. `virtual_hub_name`, `circuit_name`). |
| `GUARDRAIL_VIOLATION` | A code change attempted to call an unrecognized or mutating Azure SDK method | This should never happen via a normal tool call — if it does, it's an application bug; check server logs for which method name was rejected. |
| `AZURE_SERVICE_ERROR` | Any other Azure API error (including throttling that exhausted the SDK's own retries) | Check server logs for the underlying HTTP status/error code; retry after a delay for throttling. |

## A tool returns `success: true` but `data` is unexpectedly empty

Check `metadata.warnings` in the response first — an empty list is not
necessarily "this subscription/resource group has none of this resource
type." Common warning codes:

- `COLLECTION_FAILED` — a diagnostics-engine snapshot collection call
  failed (RBAC, throttling, unsupported region/API version) and degraded
  to an empty list for that resource family only; the rest of the
  snapshot is unaffected.
- `FANOUT_CAP_REACHED` — a bounded enrichment loop
  (`azure_list_resource_groups`'s `only_with_network_resources`, or
  `azure_get_network_health`'s `include_metrics`) hit its cap
  (`MAX_FANOUT_CALLS` / `MAX_METRIC_RESOURCES`); results beyond the cap
  were skipped, not silently dropped without notice.
- `OUT_OF_SCOPE_TARGET` — a topology edge (from `azure_get_vnet_topology`
  or `azure_get_hybrid_topology`) references a resource outside the
  queried resource group's scope; the edge is still present, just with
  no matching node.

## `azure_explain_network_path` returns `overall_verdict: "partially_evaluated"`

This means at least one of `route_verdict`/`security_verdict` was
`"indeterminate"` — check each `Finding`'s own `limitations` field for
why. Common cases:

- The route's next hop leaves this tool's visibility (`Internet`,
  `VirtualNetworkGateway`, a service endpoint) — this tool cannot trace
  reachability past that hop; it is not a claim of failure.
- No effective NSG rule (custom or default) matched the exact
  protocol/port/destination — check the NIC's NSG association directly
  via `azure_get_effective_network_security_groups`.
- The identity running this server lacks
  `effectiveRouteTable/action` or `effectiveNetworkSecurityGroups/action`
  on the target NIC — see `AUTHORIZATION_ERROR` above.

`overall_verdict` is never silently upgraded to `"allowed"` when either
layer's evidence is incomplete — see
[docs/rule_catalog.md](rule_catalog.md).

## `azure_get_hybrid_topology`/`azure_find_network_risks`/`azure_get_network_health` are slow or hit RBAC errors on some resource families

These three tools all call `diagnostics.snapshot.collect_hybrid_snapshot`,
which fans out across every resource family Milestones 5 and 6 cover for
one resource group (VNets, NSGs, route tables, NICs, public IPs, private
endpoints, Virtual Hubs, VPN gateways/connections, classic gateways/
connections, ExpressRoute circuits/gateways/connections). A resource
group with many of each will make proportionally many Azure API calls.
Each family degrades independently on failure (see the warning codes
above) rather than failing the whole call.

## Metrics come back with `stale: true`

`azure_get_network_metrics` (and `azure_get_network_health` with
`include_metrics=true`) sets `stale: true` on a `MetricQueryResult` when
every series in the response has zero data points across the whole
24-hour lookback window. This usually means the resource is genuinely
idle (no traffic to report) or was created too recently for metrics to
have accumulated — it is not itself an error.

## A collector I expect to exist doesn't have a tool

Check [docs/limitations.md](limitations.md) first — several Azure APIs
this milestone's spec named are deliberately not implemented (Network
Watcher's `begin_get_network_configuration_diagnostic`/
`begin_get_troubleshooting_result`, ExpressRoute circuit authorizations,
Connection Monitor time-series data) with the reasoning documented there.
