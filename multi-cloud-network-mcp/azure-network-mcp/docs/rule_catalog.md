# Diagnostics Rule Catalog

The deterministic diagnostics engine (`azure_network_mcp.diagnostics`) is
built from a small set of versioned rules. Every rule is registered
exactly once, at import time, via
`diagnostics.models.register_rule()` — the catalog can never silently
drift from what actually runs (a duplicate `rule_id` raises at import
time). This document is the human-readable mirror of that catalog.

Every rule produces a `Finding`
(`severity`, `confidence`, `summary`, `affected_resources`, `evidence`,
`reasoning`, `assumptions`, `limitations`, `freshness`, `remediation`) —
see [docs/architecture.md](architecture.md#diagnostics-engine) for the
full contract and
[docs/security.md#deterministic-evidence-bound-diagnostics](security.md#deterministic-evidence-bound-diagnostics)
for the guarantees behind it (never claims certainty with incomplete
data, always deterministic Python logic, `remediation` is always
advisory and never executed).

| Rule ID | Module | Title | Default severity | Used by |
|---|---|---|---|---|
| `ROUTE-001` | `diagnostics.routing` | Effective route resolution | info | `azure_explain_network_path` |
| `SEC-001` | `diagnostics.security` | Effective NSG rule evaluation | info | `azure_explain_network_path` |
| `EXPOSE-001` | `diagnostics.exposure` | Network interface internet exposure | medium | `azure_find_network_risks` |
| `CONSIST-001` | `diagnostics.consistency` | Degraded or failed resource/connection state | high | `azure_find_network_risks`, `azure_get_network_health` |
| `CONSIST-002` | `diagnostics.consistency` | Blackhole or orphaned user-defined route | medium | `azure_find_network_risks`, `azure_get_network_health` |

## ROUTE-001 — Effective route resolution

Resolves the effective route (from Azure's own merged system/UDR/BGP
route computation, `azure_get_effective_route_table`) a source NIC would
use to reach a destination IP, via longest-prefix match, and classifies
the next hop:

- `next_hop_type="None"` (a deliberate blackhole) → `route_verdict="blocked"`, severity `high`.
- No matching route at all → `route_verdict="blocked"`, severity `medium`.
- `next_hop_type` in `{Internet, VirtualNetworkGateway, VirtualNetworkServiceEndpoint, HyperNetGateway}`
  (a hop this rule cannot trace further without visibility into that
  target) → `route_verdict="indeterminate"`.
- Anything else (`VnetLocal`, `VirtualAppliance` with a resolvable next
  hop, etc.) → `route_verdict="routable"`.

Unlike this project's AWS sibling (which reimplements route-table
longest-prefix-match and static-vs-propagated tie-breaking from scratch),
this rule leverages Azure's own effective route table computation — Azure
has already merged system routes, user-defined routes, and BGP-propagated
routes (including vWAN hub route-map/routing-intent effects) before this
rule ever runs.

## SEC-001 — Effective NSG rule evaluation

Evaluates the effective NSG rules (from Azure's own merged subnet/NIC
association and Application Security Group expansion,
`azure_get_effective_network_security_groups`) Azure actually applies to
a source NIC's **outbound** traffic toward a destination IP/port/
protocol, in priority order (lowest number first), first match wins:

- A matching `Allow` rule → `security_verdict="allowed"`.
- A matching `Deny` rule → `security_verdict="blocked"`, severity `medium`.
- No rule (custom or default) matches → `security_verdict="indeterminate"`.

NSGs are stateful (like AWS security groups): only the initiating
direction is evaluated — the automatic stateful return path is not
itself a separate rule to evaluate.

## EXPOSE-001 — Network interface internet exposure

Flags a network interface that has a public IP attached and is protected
by an NSG (evaluated from its **configured** rules — custom + default, as
collected in a resource-group snapshot, not a per-NIC effective-rule
computation, which would be an unbounded fan-out across every NIC) with a
broad (`0.0.0.0/0`, `*`, or `Internet`) inbound `Allow` rule. Severity is
`high` if the matched rule covers a sensitive port (22, 3389, 3306, 1433,
5432, 6379, 27017), otherwise `medium`. If no NSG association can be
found for an internet-facing NIC, the finding is `confidence="indeterminate"`
rather than silently treated as "not exposed."

This is *potential* exposure (a permissive rule exists), never a
proven-reachable claim — see
[docs/security.md#no-reachability-claims](security.md#no-reachability-claims).

## CONSIST-001 — Degraded or failed resource/connection state

Flags any collected resource (VNet, NSG, route table, VPN gateway,
Virtual Network Gateway, ExpressRoute circuit, ExpressRoute gateway) with
`provisioning_state` other than `Succeeded`, and any VPN or classic
gateway connection with `connection_status` in
`{Disconnected, NotConnected, Degraded, Unknown}`.

## CONSIST-002 — Blackhole or orphaned user-defined route

Scans every collected route table's routes (a standing consistency check
across the whole resource group, not tied to one `azure_explain_network_path`
query) for:

- `next_hop_type="None"` (a deliberate drop) → severity `medium`,
  confidence `high`.
- `next_hop_type="VirtualAppliance"` whose `next_hop_ip_address` matches
  no network interface collected in this resource group → severity
  `medium`, confidence `indeterminate` (the appliance may legitimately
  live in a different resource group or subscription outside this
  snapshot's scope — this is a signal to check, not proof of breakage).

## Adding a new rule

1. Pick the right domain prefix (`ROUTE-*`, `SEC-*`, `EXPOSE-*`,
   `CONSIST-*`) and the next available number in that domain.
2. Call `register_rule(rule_id=..., version="1.0.0", title=..., description=...,
   default_severity=...)` at module import time — a duplicate `rule_id`
   raises immediately.
3. Every `Finding` the rule produces must set all of `severity`,
   `confidence`, `summary`, `evidence`, `freshness`; use
   `confidence="indeterminate"` (never omit the finding) when required
   evidence is missing.
4. Bump `rule_version` (semver) when the rule's *logic* changes — a
   wording-only summary/remediation edit does not require a bump.
5. Add this rule to the table at the top of this document.
