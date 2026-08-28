# Limitations Matrix

Every limitation below is a deliberate, disclosed scope boundary — not a
silent gap. Where a limitation affects a diagnostics `Finding`, it
appears in that finding's own `limitations` field at the moment it's
relevant, not only here.

## Scope decisions (Milestone 6)

| Area | Limitation | Why |
|---|---|---|
| Network Watcher diagnostics | `begin_get_network_configuration_diagnostic` and `begin_get_troubleshooting_result` are not implemented | Ambiguous mutation semantics: `begin_get_troubleshooting` (no `_result`) *starts* a new troubleshooting run and must never be called, while `begin_get_troubleshooting_result` only *retrieves* an already-run result — both share a `begin_get_troubleshooting*` name shape closely enough that a future maintainer could confuse them. Per this milestone's own stop condition ("an SDK operation has unclear mutation semantics"), neither is implemented; "existing diagnostic result retrieval" is instead covered by flow log status / NSG flow log metadata retrieval (`azure_list_flow_logs`), which this milestone does implement unambiguously. |
| Connection Monitor data | Only configuration and last-known `monitoring_status` are returned, never per-check time-series data points | Time-series check results live in Azure Monitor Logs (Log Analytics), a distinct capability from the Network Watcher Connection Monitor resource this milestone reads. Out of scope for this milestone. |
| ExpressRoute circuit authorizations | Never collected at all (no `arm/` collector calls `ExpressRouteCircuitAuthorizationsOperations`) | That operation group's list/get responses embed the circuit's authorization key — the same secret-shaped field this milestone redacts by omission everywhere else. Since authorizations carry no other useful inventory data, the simplest and safest choice is not calling that operation group at all. |
| VPN/ExpressRoute shared keys and authorization keys | Never read from any SDK response (`shared_key`, `site_key`, `authorization_key`, `service_key`) | Redaction by omission — see [docs/security.md#redaction](security.md#redaction). Statically enforced by `tests/unit/test_no_mutation_calls.py::test_no_arm_module_ever_reads_a_secret_shaped_field`. |
| Firewall policy rules | Individual rules are summarized to a count per rule collection, never enumerated | Response-size limits, per this milestone's explicit "rule summaries with response limits" requirement. |
| Private DNS record sets | Bounded by `MAX_PAGE_RESULTS`, values included as a flat summary | Record values are already-public zone data an operator with read access has direct visibility into; this is a summary, not a raw zone-file dump. |
| Azure Route Server | Modeled as a filtered view over Virtual Hub (`sku="Standard"`, no `virtual_wan`) | Azure has no dedicated Route Server ARM resource type or operation group — this is the actual underlying representation Azure itself uses. |
| Azure Monitor metrics | Fixed catalog per resource type (`arm/monitor.py::KNOWN_NETWORK_METRICS`), 24-hour lookback, 5-minute granularity, 288 datapoints/series max | Never open-ended metric discovery, mirroring this project's AWS sibling's bounded CloudWatch integration. |
| `azure_get_network_health` metrics | Capped to the first 5 gateway/circuit resources found (`diagnostics.health.MAX_METRIC_RESOURCES`); resources beyond the cap are skipped with a `FANOUT_CAP_REACHED` warning | Bounded fan-out — never a silent truncation. |
| Diagnostics engine scope | `HybridNetworkSnapshot` (and therefore `azure_get_hybrid_topology`/`azure_find_network_risks`/`azure_get_network_health`) is scoped to one resource group per call | Matches this milestone's resource-group-scoped tool design; cross-resource-group joins surface as `OUT_OF_SCOPE_TARGET` warnings with an edge still emitted, never a silently dropped relationship. |
| `azure_explain_network_path` offline mode | Not available in `diagnostics.offline` | Depends on per-NIC effective route/NSG data (`diagnostics.snapshot.collect_nic_effective_state`), which is intentionally excluded from `HybridNetworkSnapshot` (fetching it for every NIC in a resource group would be an unbounded fan-out) and has no saved-fixture equivalent in this milestone. |
| `EXPOSE-001` | Evaluates a NIC's *configured* NSG rules, not Azure's per-NIC effective-rule computation | Calling the effective-NSG computation for every internet-facing NIC in a resource group would be an unbounded fan-out; the assumption this introduces (a subnet-level rule could be overridden by a NIC-level association not captured) is disclosed on every `EXPOSE-001` finding's `assumptions` field. |
| Region/API version support | Not independently verified against every Azure region | A resource type unsupported in a given region/subscription degrades to an empty collection plus a `COLLECTION_FAILED` warning (see `diagnostics.snapshot.collect_hybrid_snapshot`'s per-family try/except) rather than failing the whole snapshot — see `tests/unit/test_diagnostics_snapshot.py::test_collect_hybrid_snapshot_degrades_gracefully_on_unsupported_region`. |
| Throttling | No client-side backoff/retry beyond the Azure SDK's own default retry policy (`AZURE_MAX_RETRIES`) | A 429 that exhausts the SDK's own retries degrades that one resource family to an empty list plus a warning, the same as any other collection failure — see `test_collect_hybrid_snapshot_degrades_gracefully_on_throttling`. |
| Partial RBAC | No attempt to distinguish "this resource type has zero instances" from "the identity lacks permission to list it" beyond the collection warning's message text | A 403 on one resource family degrades that family to an empty list plus a `COLLECTION_FAILED` warning carrying the underlying error message — a caller inspecting `snapshot.warnings` can tell the two cases apart, but no separate `error_type` field distinguishes them programmatically in this milestone. |

## Inherited from Milestone 5

See [docs/security.md#known-limitations](security.md) (tenant allowlist
enforcement limited by the SDK's missing per-subscription `tenant_id`
field) — unchanged by this milestone.

## Federation

Per this milestone's explicit guardrail, no cross-cloud data contract
(shared field names/schemas with `aws-cloudops-mcp`) is introduced here.
Milestone 9 is the named point where that federation work happens, if at
all — this repository stays Azure-native in every model field name
through Milestone 6.
