# Troubleshooting

## A tool returns `success: true` but `metadata.warnings` is non-empty

This is expected, not an error — see
[security.md#never-treat-disabled-as-empty](security.md#never-treat-disabled-as-empty).
Read each warning's `resource_type`/`code`/`message`/`scope` to identify
which resource family and location was affected, most commonly:

- `code="COLLECTION_FAILED"` — a resource family's underlying GCP API
  call raised (frequently `ApiNotEnabledError`, see below). The rest of
  the response is still populated from every resource family that
  succeeded.
- `code="UNREACHABLE"` — GCP itself reported a region/scope as
  unreachable during the call. Retry, or scope the query to a region
  known to be healthy.
- Any other code — a non-benign per-scope warning GCP's own API surfaced
  (excludes `NO_RESULTS_ON_PAGE`, which is filtered as benign since it
  just means "this scope has zero resources").

## `ApiNotEnabledError` for a Milestone 8 resource family

Network Connectivity Center, VPN, Interconnect, PSC, Cloud DNS, Network
Management, and Cloud Monitoring/Logging are each their own GCP API that
must be individually enabled on the target project:

```
gcloud services enable networkconnectivity.googleapis.com \
  compute.googleapis.com \
  dns.googleapis.com \
  networkmanagement.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  --project=YOUR_PROJECT_ID
```

This server **never enables an API on the caller's behalf** — see
[security.md](security.md#what-this-server-will-never-do). A disabled
API surfaces as a `CollectionWarning` (in diagnostics tools) or a
translated `ApiNotEnabledError` tool-level error (in a single-resource
tool like `gcp_list_ncc_hubs`), never a silent empty result.

## `gcp_get_hybrid_topology`/`gcp_explain_network_path`/`gcp_find_network_risks`/`gcp_get_network_health` seem incomplete

1. Check `metadata.warnings` first (see above) — a partial snapshot is
   the most common cause, and every diagnostics tool is built to degrade
   gracefully rather than fail outright when one resource family is
   inaccessible.
2. If you expect hierarchical Firewall Policy findings (`FW-002`) and see
   `confidence="indeterminate"` instead, you likely omitted
   `hierarchical_firewall_parent_id` — that parameter is required to
   collect real org/folder policy data; see
   [limitations.md](limitations.md#hierarchical-firewall-policy-visibility-requires-an-explicit-parameter).
3. If you expect DNS forwarding/peering/policy findings, see
   [limitations.md#cloud-dns](limitations.md#cloud-dns) — that data is
   not available through any Google-published client library, by design,
   not a bug in this server.
4. Diagnostics fan-out (router status, NCC route tables, VPN gateway
   status, Interconnect diagnostics) is bounded by
   `GCP_MAX_DIAGNOSTICS_FANOUT` (default 50) — a project with more
   routers/hubs/gateways than that will see a truncated (but still
   labeled, never silently dropped) subset. Raise the setting if you
   need full fan-out on a very large project.

## `gcp_query_logs`/`gcp_query_metrics` return fewer results than expected

Both are deliberately capped regardless of what you request —
`GCP_MAX_LOG_ENTRIES`/`GCP_MAX_LOG_QUERY_WINDOW_HOURS` and
`GCP_MAX_TIME_SERIES_POINTS`/`GCP_MAX_METRIC_QUERY_WINDOW_HOURS`. This is
intentional (see
[security.md#bounded-observability-reads](security.md#bounded-observability-reads)),
not a bug — narrow your `filter_expr` rather than expecting a wider
window or larger result set from these two tools.

## A `VpnTunnel`/`InterconnectAttachment` response has no secret field

Correct, and permanent — see
[security.md#redaction-by-omission-milestone-8](security.md#redaction-by-omission-milestone-8).
There is no configuration flag to re-enable returning
`shared_secret`/`pairing_key`; retrieve those directly from the GCP
Console or `gcloud` if you need them for gateway configuration, not
through this server.

## `mypy`/`ruff` failures after pulling this milestone

Run the exact validation sequence from the milestone spec:

```bash
ruff format --check .
ruff check .
mypy src
pytest -m "not integration" --cov=src --cov-report=term-missing
```

If `mypy` complains about `google.cloud.dns` or `google.logging.type`
imports, confirm `pyproject.toml`'s `[[tool.mypy.overrides]]` entries for
those two modules are present — both ship without a `py.typed` marker.

## `docker build` fails or hangs in this environment

Expected in a sandbox with no Docker daemon available — this is a
disclosed, known constraint of the development environment this
milestone was built in, not a defect in the `Dockerfile`. See
`MILESTONE8_STATUS.md`'s validation section for the exact command that
was attempted and its outcome.
