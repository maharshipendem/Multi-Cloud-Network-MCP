# Architecture

## Layering

```
tools/*.py       MCP tool registration -- parses/validates tool args,
                  delegates the actual work to gcp/*.py, wraps the result
                  in the standard response envelope via tools/_shared.py.

gcp/*.py         Service layer -- one module per resource family. Calls
                  the GCP client library exclusively through
                  gcp/client_factory.py + gcp/readonly.py/pagination.py,
                  normalizes raw proto-plus responses into models/*.py.

models/*.py      Normalized, cloud-native Pydantic response models. The
                  contract between the service layer and the tool layer
                  (and, once serialized, the contract handed to MCP
                  clients).

auth/*.py        ADC resolution (credentials.py) and project/folder/
                  organization allowlist enforcement (session.py).

security/        The read-only guardrail: every GCP client library call
guardrails.py    must pass assert_read_only_operation() first.

config.py        Environment-driven Settings (pydantic-settings).
exceptions.py    The GcpNetworkMCPError hierarchy every error surfaces as.
logging/setup.py Structured JSON logging with correlation IDs.
server.py        MCP transport wiring only -- no business logic.
```

No module outside `gcp/client_factory.py` constructs a
`compute_v1`/`resourcemanager_v3` client. No module outside
`gcp/readonly.py`/`gcp/pagination.py` calls a client method directly —
every call funnels through `security.guardrails.assert_read_only_operation`
first. This is enforced both by convention and by a static test
(`tests/unit/test_no_mutation_calls.py`) that scans every `gcp/*.py`
module's source for a call bypassing that choke point.

## Client scoping: one instance per class, not per project

Unlike Azure's mgmt SDK (where a client is constructed scoped to one
subscription), GCP's `google-cloud-compute`/`google-cloud-resource-manager`
clients are **not** project-scoped at construction — `project` is a
parameter on each individual call (`client.list(project="...", ...)`).
`ClientFactory` therefore caches exactly one instance of each client
class for the whole process, regardless of how many projects this server
ends up querying in a session.

Credential resolution itself is deferred to first use — constructing a
`ClientFactory` never touches `google.auth.default()`; only the first
call that actually needs a client does. This matters because
`google.auth.default()` eagerly validates ADC synchronously (unlike
Azure's `DefaultAzureCredential`, whose constructor is itself already
lazy), so resolving it eagerly at server-build time would mean
`build_server()` fails outside an ADC-configured environment — including
the offline MCP smoke tests.

## Pagination and partial results

`gcp/pagination.py` provides two primitives:

- `paginate()` — for plain `list()`-shaped calls (global resources:
  Networks, Routes, Firewalls, GlobalAddresses, GlobalForwardingRules).
- `paginate_aggregated()` — for `aggregated_list()`-shaped calls
  (regional/zonal resources spanning every scope in one call:
  Subnetworks, Instances, Addresses, ForwardingRules, TargetProxies,
  BackendServices, Routers).

Both walk pages via `.pages` (one real API request per page, counted via
`gcp/collection.py`'s `track_calls()`) and cap total items at
`max_items`. `paginate_aggregated()` additionally surfaces two signals a
naive flatten-and-return would lose:

- Each page's **`unreachables`** (scopes GCP itself could not query).
- Each scope's own **`ScopedList.warning`** — filtered to drop GCP's own
  `NO_RESULTS_ON_PAGE` (a scope genuinely has zero resources — benign),
  while surfacing every other code as a `CollectionWarning`.

A tool result carrying a `CollectionWarning` is never silently treated as
"this project has zero resources of this type" — see
[security.md](security.md#never-treat-disabled-as-empty).

## Topology assembly

`gcp/topology.py::get_vpc_topology()` joins Networks, Subnetworks,
Instance network interfaces, Cloud Routers, and VPC peerings into one
typed node/edge graph, mirroring the AWS/Azure siblings' topology-tool
discipline: raw collection stays fully separate from graph assembly, a
reference this server can't resolve (a different project's peer network,
a permission gap) still produces an edge — with no matching node — plus
an `OUT_OF_SCOPE_TARGET` warning, and the graph's `completeness` field is
`"partial"` whenever any warning was recorded, never silently
`"complete"`. Nodes and edges are always emitted in a stable, sorted
order so repeated calls against unchanged infrastructure produce
byte-identical output.

## Error translation

`gcp/errors.py::translate_gcp_error()` is the single place that decides
whether a `google.api_core.exceptions.Forbidden` means "the caller lacks
IAM permission" (`AuthorizationError`) or "the required GCP API is not
enabled" (`ApiNotEnabledError`) — both surface as the same HTTP 403,
distinguished only by message text. `tools/_shared.py::execute_tool()`
carries a second, module-level translation as a safety net for any raw
`google.api_core`/`google.auth` exception that reaches the tool layer
without having passed through `gcp/pagination.py`/`gcp/readonly.py`
first.
