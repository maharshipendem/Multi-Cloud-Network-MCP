# Security

## Credential handling

This server **never accepts, constructs from, stores, or logs** a raw
credential — a service account key file's private key, an access token,
a refresh token. It calls `google.auth.default()` exactly once per
process (cached) and lets Google's own ADC resolution chain find real
credential material, in order:

1. `GOOGLE_APPLICATION_CREDENTIALS` pointing at a key file, if a
   deployment chooses that path (**discouraged** — see below).
2. A user's `gcloud auth application-default login` session (the
   standard path for local development).
3. The metadata server's attached service account, when running on
   Compute Engine/GKE/Cloud Run with workload identity.

`GCP_IMPERSONATE_SERVICE_ACCOUNT` (a non-secret target-principal
identifier, never a credential) wraps the resolved base credentials in
`google.auth.impersonated_credentials.Credentials`, scoped to the same
`cloud-platform.read-only` OAuth scope. This is the **recommended safer
alternative** to a downloaded JSON key file for a deployment that needs
to act as a specific service account: the key material never leaves
Google's infrastructure, the impersonation grant is revocable
independently of any key rotation, and it's fully auditable via Cloud
Audit Logs (`impersonateServiceAccount` calls are logged distinctly from
the base identity's own actions).

**Why key files are discouraged**: a downloaded JSON key file is a
long-lived, unrotatable-without-manual-intervention secret that, once
exfiltrated, grants its holder everything the service account can do
until someone notices and revokes it. Workload identity federation and
service account impersonation both avoid ever materializing that secret
at rest.

Nothing in this codebase calls `credentials.token` directly or otherwise
touches resolved token material — callers of the credentials object (the
GCP client libraries themselves) attach them to outgoing requests
internally.

## Read-only enforcement

`security/guardrails.py::assert_read_only_operation()` is the single
choke point every GCP client library call passes through
(`gcp/readonly.py::call_readonly()`, and therefore every caller of
`gcp/pagination.py::paginate()`/`paginate_aggregated()`). Unlike Azure's
SDK (where a long-running mutation and a long-running *read* computation
can share the same `begin_` prefix, requiring an explicit per-method
exception list), the Google Cloud client libraries generated from
Google's API definitions follow a clean, consistent convention: every
read operation is named `get`, `list`, `aggregated_list`, or `search`;
every mutating operation is named `insert`, `delete`, `patch`, `update`,
or a verb-prefixed action (`set_*`, `add_*`, `remove_*`, `enable_*`,
`disable_*`, `request_*`, `cancel_*`, `resize_*`, `start_*`, `stop_*`,
`reset_*`, `attach_*`, `detach_*`, `move_*`, `expand_*`, `suspend_*`,
`resume_*`, `simulate_*`, `switch_*`, `bulk_insert`). No method any
tool in this milestone calls needs a special-case exception.

This is a **defense-in-depth control, not the authoritative security
boundary**. The authoritative boundary is IAM: the identity this server
runs as should hold only a read-only role — a custom role scoped to
exactly the `*.get`/`*.list` permissions this milestone's tools need (see
[gcp-custom-role.yaml](../gcp-custom-role.yaml)), never `roles/editor` or
`roles/owner`. Even if this module were bypassed or had a bug, a
correctly scoped IAM role still prevents any mutation at the GCP API
layer itself.

`tests/unit/test_no_mutation_calls.py` statically scans every `gcp/*.py`
module's source for a hardcoded mutating method-name literal passed to
the guardrail-dispatching functions, and for any direct client-method
call that bypasses them entirely — so a future service-layer function
that skips the choke point still gets caught by CI, not only in a live
GCP project.

## Never treat disabled as empty

A disabled API or a missing IAM permission for one resource type must
**never** be silently treated as "this project has zero instances of
that resource type." `gcp/errors.py::translate_gcp_error()` distinguishes
`ApiNotEnabledError` (message contains a disabled-API marker) from
`AuthorizationError` (any other 403); `gcp/pagination.py::paginate_aggregated()`
surfaces every non-benign per-scope warning and every unreachable scope
as an explicit `CollectionWarning` rather than an empty list. A tool
response carrying any warning always reports its data as partial —
`VpcTopology.completeness` is `"partial"`, never silently `"complete"`,
whenever a warning was recorded during collection.

## Least-privilege IAM

Grant the identity this server runs as the custom role in
[gcp-custom-role.yaml](../gcp-custom-role.yaml) — never a broad
predefined `roles/editor`/`roles/owner`/`roles/viewer` grant. Scope the
role binding to exactly the projects/folders/organization this server
needs to read, not organization-wide, unless the hierarchical firewall
policy tools genuinely need org-wide visibility.

## Allowlists are a second, independent boundary

`GCP_PROJECT_ALLOWLIST`/`GCP_FOLDER_ALLOWLIST`/`GCP_ORGANIZATION_ALLOWLIST`
are optional, server-enforced restrictions independent of IAM — even if
the configured identity's IAM bindings could reach a wider set of
projects, an allowlisted deployment will reject a tool call naming
anything outside it (`auth/session.py::ResourceContext`), before any GCP
API call is made. Leaving them unset means "whatever the configured
identity's IAM bindings permit," matching how this project's AWS/Azure
siblings default to IAM/RBAC-only scoping.

## What this server will never do

- Call `insert`/`delete`/`patch`/`update`/`set_*`/`add_*`/`remove_*`/
  `enable_*`/`disable_*` on any GCP resource.
- Auto-enable a disabled API on the caller's behalf.
- Recommend or require `roles/editor`/`roles/owner` for the identity it
  runs as.
- Store, log, or return a service account key, access token, or refresh
  token.
- Import or depend on `aws-cloudops-mcp` or `azure-network-mcp`.
