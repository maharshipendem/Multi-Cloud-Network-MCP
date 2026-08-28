# Integration tests

Tests here are marked `@pytest.mark.integration` and are **excluded by
default** (see `pyproject.toml`'s `addopts = "-m 'not integration'"`).
Run them explicitly with:

```bash
pytest -m integration
```

## Requirements

- Real Application Default Credentials for a **read-only** GCP identity
  — either a `gcloud auth application-default login` session, or
  `GCP_IMPERSONATE_SERVICE_ACCOUNT` pointing at a service account bound
  only to the custom role in [`gcp-custom-role.yaml`](../../gcp-custom-role.yaml).
- `GCP_DEFAULT_PROJECT_ID` (or a `project_id` passed explicitly) naming a
  real project the identity can read.
- Explicit authorization from whoever owns that project/organization
  before running these tests against it — they make real, live GCP API
  calls (all read-only, but still billed/quota-consuming and
  audit-logged).

## What these tests must never do

- Call, or assert the behavior of, any mutating GCP operation.
- Auto-enable a disabled API.
- Assume a specific resource exists in the target project — assert on
  *shape* (a valid response envelope, correctly-typed fields) rather
  than specific values, since the target project's actual inventory is
  environment-specific.
