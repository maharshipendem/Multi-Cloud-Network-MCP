"""The canonical URN grammar every cross-cloud resource/topology-node
reference in this contract uses.

Full grammar (see ``docs/urn_grammar.md`` for the formal ABNF and worked
examples from all three clouds):

    urn:mcnet:v<major>:<provider>:<scope>:<resource-type>:<native-id>

- ``mcnet`` is this contract's fixed URN namespace identifier (NID).
- ``<major>`` is ``URN_GRAMMAR_VERSION`` -- the grammar's own version,
  independent of the contract content's SemVer (see ``version.py``).
- ``<provider>`` is a lowercase provider slug (``aws``/``azure``/``gcp``,
  extensible to future providers).
- ``<scope>`` is zero or more ``key=value`` pairs, separated by ``,``,
  emitted in a FIXED canonical key order
  (``tenant,account,subscription,project,region,location,zone,
  resource_group``) regardless of which keys are present -- this is what
  makes two encodings of the same logical scope byte-identical. Absent
  keys are omitted entirely, never emitted as ``key=``.
- ``<resource-type>`` is a fixed, kebab-case slug from ``ResourceType``
  (never escaped -- it's drawn from a closed enum, not user data).
- ``<native-id>`` is the provider's own raw identifier (an AWS ARN, an
  Azure Resource ID, a GCP self-link or resource name), percent-encoded.

Escaping: every value we don't fully control (provider slug defensively,
every scope value, and the native ID) is percent-encoded via
``urllib.parse.quote`` with ``safe="/-._~"`` -- ``/`` is left literal
because it's extremely common in Azure Resource IDs and GCP self-links
and is never structurally significant to this grammar (only ``:``,
``,``, ``=``, and ``%`` are field/pair delimiters here, and all four are
always percent-encoded when they appear inside an escaped value). This
keeps a typical URN mostly human-readable while remaining fully
reversible: ``parse_urn(build_urn(...))`` round-trips exactly.

Parsing splits on ``:`` with ``maxsplit=6`` so a percent-encoding gap in
the native ID is never fatal -- the native-id field is simply "everything
after the 6th colon," never itself split further.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote, unquote

from pydantic import BaseModel

from multicloud_network_mcp.contracts.models.enums import ResourceType
from multicloud_network_mcp.contracts.version import URN_GRAMMAR_VERSION

if TYPE_CHECKING:
    from multicloud_network_mcp.contracts.models.common import CloudScope

_NID = "mcnet"
_SAFE = "/-._~"

# Fixed emission order for scope components -- never alphabetical, never
# insertion-order-dependent. See the module docstring's determinism note.
# Deliberately the exact same key names as CloudScope's own fields (minus
# `provider`, which is its own top-level URN field, and `collected_at`,
# which has no place in a stable identifier) -- one vocabulary, not two.
_SCOPE_KEY_ORDER = (
    "tenant_id",
    "account_id",
    "subscription_id",
    "project_id",
    "region",
    "location",
    "zone",
    "resource_group",
)


class ParsedUrn(BaseModel):
    """The decoded form of a ``urn:mcnet:...`` reference."""

    grammar_version: int
    provider: str
    scope: dict[str, str]
    resource_type: str
    native_id: str


def _escape(value: str) -> str:
    return quote(value, safe=_SAFE)


def _unescape(value: str) -> str:
    return unquote(value)


def scope_dict(scope: CloudScope) -> dict[str, str]:
    """Extract ``build_urn``'s ``scope=`` argument from a real
    ``CloudScope`` instance -- so a resource model's ``urn`` field can
    be built with ``build_urn(provider=scope.provider, scope=scope_dict(scope), ...)``
    rather than every call site hand-picking which fields are set."""
    return {
        key: value for key in _SCOPE_KEY_ORDER if (value := getattr(scope, key, None)) is not None
    }


def build_urn(
    *,
    provider: str,
    scope: dict[str, str],
    resource_type: ResourceType | str,
    native_id: str,
) -> str:
    """Mint a URN. ``scope`` may contain any subset of
    ``_SCOPE_KEY_ORDER``'s keys (extra/unknown keys raise -- this
    grammar's scope vocabulary is closed, not free-form, so a typo in a
    caller's scope key fails loudly here rather than silently vanishing
    from the minted URN). ``native_id`` must be non-empty -- an empty
    native ID would make the URN indistinguishable from a
    resource-type-only reference, which this grammar doesn't support."""
    unknown_keys = set(scope) - set(_SCOPE_KEY_ORDER)
    if unknown_keys:
        raise ValueError(f"Unknown scope key(s): {sorted(unknown_keys)}")
    if not native_id:
        raise ValueError("native_id must be non-empty")

    scope_str = ",".join(
        f"{key}={_escape(scope[key])}" for key in _SCOPE_KEY_ORDER if key in scope and scope[key]
    )
    resource_type_str = (
        resource_type.value if isinstance(resource_type, ResourceType) else resource_type
    )
    return (
        f"urn:{_NID}:v{URN_GRAMMAR_VERSION}:{_escape(provider)}:{scope_str}:"
        f"{resource_type_str}:{_escape(native_id)}"
    )


def parse_urn(urn: str) -> ParsedUrn:
    """Decode a URN minted by ``build_urn``. Raises ``ValueError`` on any
    structurally malformed input -- never returns a partially-populated
    result, since a caller that can't tell "parsed" from "half-parsed"
    can't safely act on the result."""
    parts = urn.split(":", 6)
    if len(parts) != 7:
        raise ValueError(f"Malformed URN (expected 7 ':'-delimited fields): {urn!r}")
    literal_urn, nid, version_field, provider, scope_str, resource_type, native_id = parts
    if literal_urn != "urn" or nid != _NID:
        raise ValueError(f"Not a {_NID} URN: {urn!r}")
    if not version_field.startswith("v") or not version_field[1:].isdigit():
        raise ValueError(f"Malformed URN grammar version field: {version_field!r}")

    scope: dict[str, str] = {}
    if scope_str:
        for component in scope_str.split(","):
            if "=" not in component:
                raise ValueError(f"Malformed scope component (no '='): {component!r}")
            key, _, value = component.partition("=")
            if key not in _SCOPE_KEY_ORDER:
                raise ValueError(f"Unknown scope key in URN: {key!r}")
            scope[key] = _unescape(value)

    if not native_id:
        raise ValueError(f"URN has an empty native_id: {urn!r}")

    return ParsedUrn(
        grammar_version=int(version_field[1:]),
        provider=_unescape(provider),
        scope=scope,
        resource_type=resource_type,
        native_id=_unescape(native_id),
    )


__all__ = ["ParsedUrn", "build_urn", "parse_urn", "scope_dict"]
