# URN grammar

Every resource, topology node, and finding-affected-resource in this
contract is addressed by one stable, deterministic URN. The
implementation is `src/multicloud_network_mcp/contracts/urn.py`
(`build_urn()`/`parse_urn()`/`scope_dict()`); this document is the
formal grammar and worked examples that file's own docstring
summarizes.

## Grammar (ABNF)

```abnf
urn-ref        = "urn" ":" nid ":" grammar-version ":" provider ":"
                  scope ":" resource-type ":" native-id

nid            = "mcnet"
grammar-version = "v" 1*DIGIT
provider       = 1*(ALPHA / DIGIT / "-")            ; lowercase
scope          = [ scope-component *("," scope-component) ]
scope-component = scope-key "=" pct-value
scope-key      = "tenant_id" / "account_id" / "subscription_id" /
                 "project_id" / "region" / "location" / "zone" /
                 "resource_group"
resource-type  = 1*(ALPHA / DIGIT / "-")            ; kebab-case, from ResourceType
native-id      = pct-value                           ; the provider's own raw identifier

pct-value      = *( unreserved / "/" / pct-encoded )
unreserved     = ALPHA / DIGIT / "-" / "." / "_" / "~"
pct-encoded    = "%" HEXDIG HEXDIG
```

## Design decisions

- **`scope-key` is a closed vocabulary, not free-form.** It is exactly
  `CloudScope`'s own field names (minus `provider`, which is its own
  top-level URN field, and `collected_at`, which has no place in a
  stable identifier) — one vocabulary, not two independently-maintained
  ones. `build_urn()` raises on an unrecognized scope key rather than
  silently dropping it.
- **Scope components are always emitted in a fixed key order**
  (`tenant_id, account_id, subscription_id, project_id, region,
  location, zone, resource_group`), regardless of which subset is
  present. This is what makes two encodings of the same logical scope
  byte-identical — a URN is not just unique, it's *reproducible*.
- **Escaping is minimal but total.** Every value this grammar doesn't
  fully control (the provider slug, every scope value, the native ID)
  is percent-encoded via `urllib.parse.quote(value, safe="/-._~")`.
  `/` is left unescaped because it's extremely common in Azure Resource
  IDs and GCP self-links and is never structurally significant to this
  grammar; `:`, `,`, `=`, and `%` are always percent-encoded when they
  appear inside a value, since those four characters are this grammar's
  own field/pair delimiters.
- **Parsing never needs to guess where the native ID ends.** `parse_urn`
  splits on `:` with `maxsplit=6`, so the native-id field is simply
  "everything after the 6th colon" — an unescaped `:` deep inside a
  native ID (which this implementation always escapes anyway, but a
  hand-written URN might not) still parses correctly rather than
  corrupting the split.
- **The URN grammar version (`v1`) is independent of the contract's own
  SemVer** (`CONTRACT_VERSION` in `version.py`). The grammar can stay
  stable across many contract content releases; it only needs its own
  bump if this ABNF itself changes shape — a much rarer event than a
  new resource field being added.

## Worked examples, one per provider

**AWS VPC**, scoped to an account and region, native ID is the short
resource ID (no ARN was available for this resource type — see
`docs/normalization.md`'s AWS ID-handling note):

```
urn:mcnet:v1:aws:account_id=123456789012,region=us-east-1:network:vpc-0abc123def456789
```

**Azure Virtual Network**, scoped to a subscription, resource group, and
location, native ID is the full ARM Resource ID (`/` left unescaped for
readability):

```
urn:mcnet:v1:azure:subscription_id=1e2d3c4b-5a69-4788-9f01-234567890abc,location=eastus,resource_group=rg-networking:network:/subscriptions/1e2d3c4b-5a69-4788-9f01-234567890abc/resourceGroups/rg-networking/providers/Microsoft.Network/virtualNetworks/vnet-prod
```

Note `location` is emitted before `resource_group` — the fixed key
order (`region, location, zone, resource_group`) puts every
geography-scoping key ahead of the org-scoping `resource_group`, per the
canonical order in `urn.py::_SCOPE_KEY_ORDER`.

**GCP Network**, scoped to a project (GCP networks are global, so no
`region`/`zone`/`location`), native ID is the full self-link:

```
urn:mcnet:v1:gcp:project_id=my-gcp-project-123:network:https%3A//www.googleapis.com/compute/v1/projects/my-gcp-project-123/global/networks/default
```

Only the `:` immediately after `https` is percent-encoded (to `%3A`,
since `:` is always escaped — it's this grammar's own field delimiter);
every `/` in the self-link stays literal, since `/` is in the "safe" set
`_escape()` never touches. Verified directly against `build_urn()`/
`parse_urn()` — this is the actual output, not a hand-computed example.

## Round-tripping

`parse_urn(build_urn(...))` always recovers exactly the original
`provider`, `scope`, `resource_type`, and `native_id` — this is a hard
guarantee, verified in `tests/contracts/test_urn.py` (including a
percent-sign, colon, and non-ASCII character embedded directly inside a
native ID, and a scope with zero, one, and every possible component
populated).
