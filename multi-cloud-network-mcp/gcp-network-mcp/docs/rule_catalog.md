# Diagnostics rule catalog

Every rule below is a pure function over an already-collected
`HybridNetworkSnapshot` (see
[architecture.md#diagnostics-engine](architecture.md#diagnostics-engine)),
registered exactly once at import time via `diagnostics/models.py::register_rule()`
— a duplicate `rule_id` raises immediately, so this table can never
silently drift from what actually runs. Call `diagnostics.models.rule_catalog()`
to get this same data live from the running server.

Each rule's `default_severity` is a starting point, not a fixed output —
several rules downgrade severity or set `confidence="indeterminate"` for
specific sub-cases (noted below). Every `Finding` a rule returns carries
`severity`, `confidence`, `evidence`, `assumptions`, and `limitations` —
never just a summary string.

| Rule ID | Title | Module | Default severity | Checks |
|---|---|---|---|---|
| `ROUTE-001` | Route resolution | `diagnostics/routing.py` | — (informational) | Resolves the route a network would use to reach a destination IP via longest-prefix match, ties broken by GCP's own `priority` field (lower wins); classifies the next hop. |
| `ROUTE-002` | CIDR overlap | `diagnostics/routing.py` | — (per-pair) | Detects overlapping destination CIDR ranges across a network's own custom static routes, which makes the lower-priority route partially/fully unreachable for the overlap. Two ordinary `0.0.0.0/0` default routes are excluded from this check — that pairing is normal, not a misconfiguration. |
| `FW-001` | Firewall rule evaluation | `diagnostics/firewall.py` | — (per-verdict) | Evaluates network-level firewall rules (plus GCP's two implied default rules) in priority order for one 5-tuple, first-match-wins — GCP's real evaluation semantics. |
| `FW-002` | Hierarchical firewall policy interaction | `diagnostics/firewall.py` | — (per-verdict) | Whether an organization/folder Firewall Policy could override a network-level verdict — hierarchical policies evaluate **before** VPC rules for ingress, **after** them for egress. `confidence="indeterminate"` whenever no `hierarchical_firewall_parent_id` was supplied (no org/folder-level data was collected to evaluate against). |
| `PEER-001` | VPC Network Peering limitations | `diagnostics/peering.py` | medium | Non-`ACTIVE` peering state; `exchange_subnet_routes=false`; `import_custom_routes`/`export_custom_routes` both `false`; the general non-transitivity of VPC peering (A↔B and B↔C does not imply A↔C). |
| `NCC-001` | Network Connectivity Center propagation | `diagnostics/ncc.py` | medium | An inactive NCC spoke, using GCP's own reported state reasons; PSC propagation errors surfaced by a hub's own status computation. Returns no finding for a healthy `ACTIVE` spoke. |
| `NAT-001` | Cloud NAT egress | `diagnostics/nat.py` | medium | `MANUAL_ONLY` IP allocation with zero assigned NAT IPs (egress fully blocked — escalates above the default severity to `critical`); a low per-VM port allocation (`min_ports_per_vm` < 64) that risks port exhaustion under load (at reduced confidence). |
| `EXPOSE-001` | Public forwarding rule exposure | `diagnostics/exposure.py` | medium | An `EXTERNAL`/`EXTERNAL_MANAGED` forwarding rule, cross-referenced against `FW-001`'s evaluation using `peer_ip="0.0.0.0"` as the internet-at-large worst case, to determine whether the exposed IP is actually reachable. |
| `HYBRID-001` | Degraded HA VPN | `diagnostics/hybrid.py` | high | A VPN tunnel not in `ESTABLISHED` status; an HA VPN connection not meeting GCP's redundancy requirement. |
| `HYBRID-002` | Degraded Interconnect | `diagnostics/hybrid.py` | high | An Interconnect not operationally up; a diagnostics link reporting a non-up operational status. |
| `HYBRID-003` | Degraded BGP session | `diagnostics/hybrid.py` | high | A BGP peer session not `UP`; a session that is `UP` but has learned zero routes (at reduced confidence — could be a genuinely empty route table, not necessarily a fault). |
| `DNS-001` | DNS forwarding chain | `diagnostics/dns.py` | — (per-aspect) | The one fact this rule can check at full confidence: whether a managed zone has zero assigned name servers. Every forwarding/peering/policy aspect is `confidence="indeterminate"` by design — no Google-published client library for Cloud DNS exposes that configuration (see [limitations.md](limitations.md#cloud-dns)). |

## How rules combine into the four diagnostics tools

- **`gcp_find_network_risks`** runs all 12 rules against the snapshot and
  returns every `Finding`, unfiltered — including every
  `confidence="indeterminate"` one.
- **`gcp_get_network_health`** aggregates `gcp_find_network_risks`'s
  output into `finding_counts_by_severity` and one `overall_status`
  (`"critical"` if any `critical` finding exists, else `"degraded"` for
  `high`, `"attention_needed"` for `medium`, else `"healthy"`).
- **`gcp_explain_network_path`** runs only `ROUTE-001`, `FW-001`, and
  `FW-002` for one source-network/destination-IP pair and derives a
  single `overall_verdict`: `"allowed"` only if every layer independently
  concluded so, `"blocked"` if any layer did (a hierarchical `DENY`
  override takes precedence over a VPC-level `ALLOW`, matching GCP's real
  evaluation order), `"partially_evaluated"` if any layer's evidence was
  incomplete — never silently upgraded to `"allowed"`.
- **`gcp_get_hybrid_topology`** does not run the rule catalog at all — it
  is a pure graph-assembly function (`build_hybrid_topology()`), included
  here only because it shares the same `HybridNetworkSnapshot` input.

## Versioning

Every rule carries a `version` (currently `"1.0.0"` for all 12). A future
change to a rule's logic that could change its verdict on unchanged input
should bump this version, so a caller diffing findings across server
versions can distinguish "the network changed" from "the rule changed."
