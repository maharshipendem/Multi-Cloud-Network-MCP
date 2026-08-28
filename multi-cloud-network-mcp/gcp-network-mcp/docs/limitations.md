# Known limitations

Every gap below is a **deliberate, documented scope decision**, not an
oversight — each was reached by exhausting the available Google-published
client libraries first, and choosing to leave a genuine capability gap
honestly documented rather than fabricate data, reach into an
undocumented private API, or introduce a third client-library
architecture this late in the milestone. A tool response never claims
certainty it doesn't have — the sub-sections below map directly onto
`confidence="indeterminate"` findings and `BLOCKED`/`PARTIAL` status
lines in `MILESTONE8_STATUS.md`.

## Cloud DNS

`google.cloud.dns` (the only Google-published Python client for Cloud
DNS) exposes managed zones and record sets only. It has **no API for**:

- DNS forwarding configuration (Cloud DNS forwarding zones/policies).
- DNS peering configuration.
- Response Policies and Response Policy Rules.
- Split-horizon (private-vs-public) resolution behavior.

`gcp_list_dns_zones`/`gcp_list_dns_zone_records` therefore return only
zone metadata and record set summaries — never forwarding/peering/policy
configuration. `DNS-001` (see [rule_catalog.md](rule_catalog.md))
evaluates this honestly: `confidence="indeterminate"` for every
forwarding-chain aspect, full confidence only for the one fact directly
observable (whether a zone has zero assigned name servers).

## Private services access — connections, not just ranges

"Private services access" (VPC peering to Google-managed services, used
by Cloud SQL, Memorystore, etc.) has two halves: allocated **ranges**
(`compute.googleapis.com` `GlobalAddress` resources with
`purpose=VPC_PEERING`) and the **connection** resource itself (the
`servicenetworking.googleapis.com` `Connection`, which records which
service is peered and its own status). This server implements only the
range half — `gcp_list_private_service_access_ranges` derives entirely
from `gcp_list_addresses`'s existing collection, no new API surface.

The connection half has **no dedicated Python client library**
(`pip index versions google-cloud-service-networking` returns no match
as of this milestone) — the only way to read it would be a generic
`googleapiclient.discovery` client, a different construction/auth
pattern than every other client this server uses. Rather than
introducing that third architecture this late, the connection resource
is left unimplemented and undocumented-by-Google, not fabricated.

## Network Management Performance Dashboard

The spec calls for exposing Performance Dashboard results where they
already exist. No Google-published API for Performance Dashboard data
was found during this milestone (searched across
`network_management_v1` and the Cloud Monitoring/Logging surfaces this
server already integrates). **Status: `BLOCKED`** — not implemented,
not fabricated. If Google ships a client library for this in the future,
it would slot into `gcp/connectivity_tests.py`'s neighborhood.

## Connectivity Test step detail

`network_management_v1`'s `Trace.Step` is a `oneof` across roughly 30
distinct sub-message kinds (`instance`, `firewall`, `route`,
`forwarding_rule`, `vpn_gateway`, `vpc_connector`, ...). Modeling all 30
would add a large amount of surface for marginal value; instead,
`ConnectivityTestStepSummary.detail` mirrors GCP's own `Step.state` enum
name — the same overall verdict a human reading the Cloud Console trace
would see, without a bespoke sub-model per step kind. The full raw step
detail is not currently surfaced.

## Hierarchical Firewall Policy visibility requires an explicit parameter

`FW-002` (hierarchical policy interaction) can only evaluate real
organization/folder policy data when a caller supplies
`hierarchical_firewall_parent_id` — GCP's hierarchical Firewall Policies
are org/folder-scoped, and this server has no way to discover the
correct parent ID on the caller's behalf without an extra
Resource-Manager-ancestry call this milestone doesn't make. Omitting the
parameter is not an error; it produces a `confidence="indeterminate"`
finding rather than silently skipping the interaction check or assuming
no override exists.

## Cloud NAT — Dynamic Port Allocation detail

`NAT-001` evaluates `min_ports_per_vm` (the floor) but does not currently
model GCP's Dynamic Port Allocation min/max range interaction in detail
— a NAT gateway using dynamic allocation is evaluated the same way as
one using static allocation, which may understate headroom in a
dynamically-scaling configuration. Flagged here rather than silently
assumed correct.

## What is intentionally NOT built

Per the milestone's explicit scope boundary: **no cross-cloud federation
schema** — this repository normalizes only to `gcp_network_mcp`'s own
Pydantic models, with no shared AWS/Azure/GCP response contract. That is
scoped to a future milestone, tracked in `MILESTONE8_STATUS.md`'s
handoff section.
