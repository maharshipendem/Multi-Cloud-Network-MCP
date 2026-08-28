# Normalization specification

How a provider-native fact maps onto this contract's canonical shape,
and — just as importantly — where that mapping is lossy, inferred, or
simply doesn't exist. This document is the single place every
"unavoidable semantic difference" this milestone asks to be documented
actually lives; every claim below was verified against the three cloud
repos' own real Pydantic models (`aws-cloudops-mcp`, `azure-network-mcp`,
`gcp-network-mcp`) as of Milestone 9, not guessed.

## The core guardrail: never silently coerce unknown data

Every canonical resource model extends `ExtensibleModel`
(`models/common.py`), carrying `extensions: dict[str, dict[str, Any]]`,
namespaced by provider slug. **A fact a provider actually returned must
never be discarded merely because this contract has no first-class field
for it.** An adapter mapping raw data:

1. Populates every canonical field it genuinely, losslessly can.
2. Puts everything else — provider-specific mechanism fields, nested
   structures unique to one provider, the untouched raw value behind a
   *lossy* canonical mapping — into `extensions[provider]`.
3. Never invents a canonical value it didn't actually observe (see
   "inference vs. observation" below) and never narrows a real value to
   fit a closed vocabulary without also preserving the original.

`tests/contracts/test_extensions_preserved.py` enforces this is more
than a stated policy for at least one concrete case per resource family.

## CIDR / IP normalization

All three providers already return CIDR ranges as plain strings in a
compatible format — the only real work is: canonicalizing a bare host
address to `/32` (or `/128` for IPv6), and determining IP version.
`normalization/cidr.py::normalize_cidr()`/`ip_version_of()` do this and
raise `ValueError` on genuinely malformed input, never silently
returning an empty/default value.

## Protocol normalization

| Canonical `Protocol` | AWS (`SecurityGroupRule.ip_protocol`/`NetworkAclEntry.protocol`) | Azure (`SecurityRule.protocol`) | GCP (`Firewall.allowed[].I_p_protocol`) |
|---|---|---|---|
| `tcp` | `"tcp"` | `"Tcp"` | `"tcp"` |
| `udp` | `"udp"` | `"Udp"` | `"udp"` |
| `icmp` | `"icmp"` | `"Icmp"` | `"icmp"` |
| `icmpv6` | (raw number `58`) | (raw number `58`) | `"icmpv6"` |
| `esp` | (raw number `50`) | `"Esp"` | `"esp"` |
| `ah` | (raw number `51`) | `"Ah"` | `"ah"` |
| `gre` | (raw number `47`) | (raw number `47`) | (raw number `47`) |
| `all` | `"-1"` | `"*"` | (no explicit "all" keyword at this granularity — GCP firewall rules enumerate protocols explicitly per `allowed`/`denied` entry) |
| `other` | any other raw IANA number | any other raw IANA number | any other raw IANA number |

`normalization/protocol.py::normalize_protocol()` implements this table
plus a raw-IANA-number fallback; an unrecognized value normalizes to
`"other"` with the original string preserved on `NormalizedProtocol.raw`
— never silently dropped, per the core guardrail above.

## Port range normalization

- AWS: two separate nullable integers (`from_port`/`to_port`); "all
  ports" is both `None`.
- Azure: a string (`"80"`/`"80-443"`/`"*"`), with a plural
  `destination_port_ranges` field for discontiguous ranges.
- GCP: a list of strings (`["80", "8080-8090"]`); empty/absent means
  "all ports for this protocol."

Canonical form: a single string (`"80"` or `"80-443"`), or `None` for
"all ports" — matching what a human would type into any of the three
consoles. `normalization/port_range.py::normalize_port_range()`
(singular) / `normalize_port_ranges()` (plural, for Azure/GCP's
multi-range fields) implement this, raising `ValueError` on an
out-of-range or malformed port rather than silently clamping.

## Route origin/state normalization

**GCP has no `origin` or `state` field on `Route` at all** — the single
largest gap in this table, not an oversight. See
`normalization/route.py`'s full docstring.

| Canonical `RouteOrigin` | AWS `Route.origin` | Azure `EffectiveRoute.source` | GCP |
|---|---|---|---|
| `system` | `"CreateRouteTable"` | `"Default"` | *(no field — inferable only, never observed)* |
| `static` | `"CreateRoute"` | `"User"` | *(same)* |
| `dynamic` | `"EnableVgwRoutePropagation"` | `"VirtualNetworkGateway"` | *(same)* |
| `unknown` | anything else / `None` | anything else / `None` | always, since GCP has no field to read |

| Canonical `RouteState` | AWS `Route.state` | Azure `EffectiveRoute.state` | GCP |
|---|---|---|---|
| `active` | `"active"` | `"Active"` | *(no field)* |
| `blackhole` | `"blackhole"` | *(no direct equivalent)* | *(no field)* |
| `inactive` | *(n/a)* | `"Invalid"` | *(no field)* |
| `unknown` | anything else | anything else | always |

An adapter MAY infer GCP route origin/state from other collected facts
(e.g. a `0.0.0.0/0` route with `next_hop_gateway` set to the well-known
default-internet-gateway URI is almost certainly `system`-origin) — but
that is **inference, not observation**, and must be presented as such
(e.g. surfaced only through a `Finding`'s `reasoning`/`confidence`
fields, never written directly into `Route.origin`/`Route.state` as if
it were a directly-observed fact). This contract's normalization
functions themselves never perform this kind of inference — they only
map a raw field that actually exists.

GCP does have something AWS/Azure don't: an explicit `priority` integer
on every route, used for real tie-breaking. AWS/Azure both use
longest-prefix-match with no documented tie-break field at all when two
routes have equal prefix length — `Route.priority` stays `None` for
both, and this is a genuine capability asymmetry, not a mapping gap.

## Firewall rule normalization — AWS's dual-mechanism gap

AWS is the only provider with **two** distinct firewall mechanisms
mapping onto the one canonical `FirewallRule` type:

- **Security Group rules** (`SecurityGroupRule`): stateful, referenced
  by ID, evaluated as an allow-list (no explicit deny).
- **Network ACL entries** (`NetworkAclEntry`): stateless, ordered by
  `rule_number`, explicit `rule_action` of `allow`/`deny`.

Azure (`SecurityRule`, NSG-attached) and GCP (`Firewall`, network-wide
with two implied defaults) each have exactly one stateful mechanism.
The canonical `FirewallRule.stateful: bool` field exists specifically to
keep this distinction visible rather than flattening AWS's two
mechanisms into something indistinguishable from Azure/GCP's one — see
`contracts/examples/aws/`'s two separate `firewall-rule.*.json` examples
(one `stateful: true` from a Security Group rule, one `stateful: false`
from a NACL entry).

GCP additionally has two *implied* default rules per network
(`allow-egress`/`deny-ingress`) that GCP's own list API doesn't return —
`gcp-network-mcp` synthesizes these itself already; an adapter exporting
GCP firewall data should include them, with `native_id` reflecting their
synthetic (not GCP-API-returned) origin.

## NodeKind — formalizing three different informal conventions

| Provider | How "can't fully resolve" is represented today |
|---|---|
| AWS | An `external_endpoint` node-type string for a genuinely non-AWS boundary; an undocumented "orphan edge" convention (an edge whose `target_id` has no matching node) for an in-scope-domain resource outside collection scope. Neither is schema-enforced — both are docstring-only conventions in `aws-cloudops-mcp/src/aws_cloudops_mcp/models/hybrid_topology.py`. |
| Azure | A free-form `node_type` string (no reserved value) plus a `CollectionWarning` explaining the gap — also convention, not schema. |
| GCP | A dedicated `OUT_OF_SCOPE_TARGET` warning code, with **no node emitted at all** for the unresolved reference — the edge exists, pointing at a `target_id` with no matching node. |

Canonical: `TopologyNode.kind` (`RESOURCE`/`EXTERNAL`/`UNRESOLVED`,
`models/enums.py::NodeKind`) makes this explicit and required on every
node, rather than optional/convention-based. An adapter mapping AWS's
`external_endpoint` → `EXTERNAL`; AWS's orphan-edge / GCP's
no-node-at-all pattern → either omit the node entirely (matching GCP's
existing behavior, edge still present) or emit an `UNRESOLVED` node (the
richer option, giving a consumer something to attach a label/warning
to) — this contract recommends the richer `UNRESOLVED`-node form for new
adapter code, but doesn't require re-architecting an existing collector
that currently drops the node.

## Diagnostics — the one area needing almost no mapping

All three cloud repos' own diagnostics engines already independently
converged on an essentially identical `Finding` shape (`rule_id`,
`rule_version`, `severity`, `confidence` with an explicit
`"indeterminate"` value, `summary`, `affected_resources`, `evidence`,
`reasoning`, `assumptions`, `limitations`, `freshness`, `remediation`).
`normalization/severity.py` exists mostly for forward-compatibility
(see its own docstring) rather than because a real mapping is needed
today. The one required change when exporting a `Finding`: rewrite
`affected_resources`/`evidence[].source` from raw provider-native IDs to
this contract's `urn` scheme.

**Rule IDs are deliberately NOT unified across providers.** AWS's
`CONSIST-001` and GCP's `NAT-001` check genuinely different things — a
consumer correlates findings by `affected_resources`/`severity`/
`confidence`, never by assuming the same `rule_id` string means the same
check across two providers.

## Load balancer — granularity mismatch

AWS (`LoadBalancer` from ELBv2) and Azure (`LoadBalancer`/
`ApplicationGateway`) both model a load balancer as one resource with
nested listeners/backend pools. GCP's own model is finer-grained
(`ForwardingRuleSummary` + a separate backend service + target proxy) —
an adapter exporting a canonical `LoadBalancer` for GCP is aggregating
across what GCP itself treats as several independent resources, which
is a synthesis, not a 1:1 export; document this per-example in that
adapter's own notes (see `contracts/examples/gcp/NOTES.md`).

## Address — AWS has no first-class resource

Azure (`PublicIpAddress`) and GCP (`Address`, including Private Service
Access ranges from `GlobalAddress`) both have a first-class address
resource. AWS does not — Elastic IP-equivalent data only exists nested
inside `NatGatewayAddress`/`NetworkInterface.public_ip`. A canonical
`Address` example for AWS is therefore synthesized from one of those
nested locations, not a direct 1:1 export — see
`contracts/examples/aws/NOTES.md` for exactly which nested field a given
example was built from.

## DNS resolver/rule — GCP has neither

Azure (`DnsResolver`+`DnsResolverInboundEndpoint`/`OutboundEndpoint`,
`DnsForwardingRule`) and AWS (`ResolverEndpoint`, `ResolverRule`) both
have real resolver/rule concepts. **GCP's Cloud DNS client library
exposes neither** — confirmed directly against `gcp-network-mcp`'s own
`docs/limitations.md`, written during that repo's own Milestone 8: "no
available Google client library exposes [DNS forwarding/peering/policy]
configuration." A GCP adapter should simply not emit `dns-resolver`/
`dns-rule` examples or capability-manifest entries for these two types,
rather than fabricating them.

## VPN/Interconnect — redaction is universal, never provider-specific

All three source repos already independently arrived at the same rule:
never read a VPN tunnel's shared secret / Interconnect's pairing key
into their own models, ever. This contract's `VpnTunnel`/`Interconnect`/
`InterconnectAttachment` carry `redacted: bool = True` as a **permanent
guarantee, not a toggle** — there is no field on any of these three
models that could hold such a secret even by adapter-author mistake.
`ObservedState`'s vocabulary (`up`/`down`/`degraded`/`provisioning`/
`unknown`) is the canonical `status`; each provider's own much richer
raw status string (GCP's `"ESTABLISHED"`, Azure's `"Connected"`, AWS's
`"UP"`) is preserved verbatim on `native_status` rather than lost to the
coarser mapping.

## Ownership vs. scope

`Ownership` (`models/common.py`) is populated only when a resource's
owner genuinely differs from the scope it was *collected* under — a
cross-account VPC peering accepter, a cross-subscription hub connection,
a GCP Shared VPC service project referencing a host project's network.
The overwhelmingly common case (owner == collector) leaves `Ownership`
entirely absent rather than redundantly restating the same scope twice.
