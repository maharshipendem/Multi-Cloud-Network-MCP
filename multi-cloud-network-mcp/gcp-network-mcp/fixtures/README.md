# Fixtures

## `demo_vpc_topology.json` (Milestone 7)

A sanitized example of `gcp_get_vpc_topology`'s output shape — a
`VpcTopology` node/edge graph. No fictitious real project ID or
customer-identifying data; every identifier is `demo-*`/`other-*`.

## `hybrid_diagnostics_scenarios.json` (Milestone 8)

A sanitized `HybridNetworkSnapshot` — the *input* to the diagnostics
engine (`gcp_find_network_risks`/`gcp_get_hybrid_topology`/
`gcp_get_network_health`, and offline via `diagnostics.offline.analyze_offline_snapshot()`),
not a tool's output. It packs one instance of every scenario category
the milestone spec asked fixtures to cover into a single project,
`scenario-net-project`:

| Scenario | Where in the snapshot | Rule(s) triggered |
|---|---|---|
| Shared VPC | `shared_vpc_host_status` (`xpn_project_status="HOST"`) | — |
| VPC peering route import/export limitation | `peerings[0]` (`exchange_subnet_routes`/`import_custom_routes`/`export_custom_routes` all `false`) | `PEER-001` |
| Hierarchical Firewall Policy visibility gap | `hierarchical_firewall_policies` deliberately empty | `FW-002` (indeterminate advisory) |
| Overlapping CIDR routes | `routes` — `static-a` (`10.20.0.0/16`) and `static-b` (`10.20.4.0/24`) overlap | `ROUTE-002` |
| Unknown next hop | `routes` — `mystery-route` has no `next_hop_*` field set | (feeds route resolution; no dedicated rule fires on it alone) |
| Cloud NAT egress blocked | `routers[0].nats[0]` — `MANUAL_ONLY` allocation, zero IPs, plus a low `min_ports_per_vm` | `NAT-001` (critical + a second, lower-severity finding) |
| BGP route preference / degraded session | `router_statuses[0].bgp_peer_status` — one healthy peer with 12 learned routes, one `UP` peer with zero | `HYBRID-003` |
| Network Connectivity Center propagation | `ncc_hubs`/`ncc_spokes` — one `ACTIVE` spoke, one `INACTIVE` with a `PENDING_REVIEW` reason | `NCC-001` |
| HA VPN redundancy | `vpn_gateway_statuses[0]` — `CONNECTION_REDUNDANCY_NOT_MET`; `vpn_tunnels` — one `ESTABLISHED`, one `FAILED` | `HYBRID-001` |
| Interconnect states | `interconnects` — one `OS_ACTIVE`, one `OS_UNPROVISIONED`; `interconnect_diagnostics` — a `DOWN` link | `HYBRID-002` |
| Public forwarding rule exposure | `forwarding_rules[0]` — `EXTERNAL` scheme, no protecting firewall rule for its port | `EXPOSE-001` |
| Split-horizon DNS | `dns_zones` — one zone with name servers (forwarding-chain aspect always `indeterminate`, by design), one with none (`high` confidence) | `DNS-001` |
| Partial IAM / API-disabled / throttling / stale monitoring data | `warnings` — four representative `CollectionWarning` entries with realistic codes/messages | — (collection-time conditions, not rule findings) |

**Redaction is proven, not just claimed**: the raw inputs set a
`shared_secret` on one VPN tunnel and a `pairing_key` on the
Interconnect attachment; neither string appears anywhere in the fixture
JSON — confirm with `grep -c "never-returned" hybrid_diagnostics_scenarios.json`
(returns `0`).

### Regenerating

Built by `scripts/build_hybrid_diagnostics_fixture.py`, which constructs
real GCP SDK objects and runs them through the actual `gcp/*.py`
normalizers — never hand-authored JSON that could drift from the real
model shapes:

```bash
PYTHONPATH=src python scripts/build_hybrid_diagnostics_fixture.py
```

Regenerating changes every per-resource `observed_at` timestamp (each
normalizer stamps its own `now_iso()`) but not the underlying scenario
data, so the findings a re-run produces should be identical.

### Golden test

`tests/unit/test_diagnostics_offline.py::test_hybrid_diagnostics_scenarios_fixture_produces_the_expected_findings`
loads this fixture through `analyze_offline_snapshot()` (the same
offline entrypoint an external caller with no live GCP access would use)
and asserts on the exact set of rule IDs, severities, and confidence
levels it's expected to produce — a regression test for the rule
catalog's reasoning, not just its wiring.
