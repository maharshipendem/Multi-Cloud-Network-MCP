"""Versioning constants for the multi-cloud network contract.

Three distinct version axes exist here, deliberately kept separate
(conflating them is a common source of silent breakage in cross-service
contracts):

- ``CONTRACT_VERSION``: the SemVer of this whole contracts package's
  *content* (models + schemas + normalization tables together). A minor
  bump adds optional fields/enum values without breaking an existing
  consumer; a patch bump fixes a description/example without changing
  any type; a major bump is the only kind of change that can break an
  existing consumer, and requires the deprecation process in
  ``docs/versioning.md``.
- ``URN_GRAMMAR_VERSION``: the version embedded in every minted URN
  (``urn:mcnet:v<URN_GRAMMAR_VERSION>:...``). Independent of
  ``CONTRACT_VERSION`` -- the URN *grammar* (how identifiers are
  constructed) can stay stable across many contract content releases,
  and only needs its own bump if the grammar itself changes shape.
- ``SCHEMA_ID_VERSION``: the path segment embedded in every JSON Schema
  ``$id`` (``.../schemas/v<SCHEMA_ID_VERSION>/...``). Tracks the major
  version of ``CONTRACT_VERSION`` -- a new major contract version gets a
  new schema directory (``schemas/v2/``) published *alongside* the old
  one (``schemas/v1/``), never overwriting it in place, so a consumer
  pinned to an old ``$id`` keeps resolving to the schema it was built
  against.
"""

from __future__ import annotations

CONTRACT_VERSION = "1.0.0"
URN_GRAMMAR_VERSION = 1
SCHEMA_ID_VERSION = 1

SCHEMA_BASE_URI = "https://schemas.multicloud-network-mcp.dev"
"""Base URI every schema's ``$id`` is rooted at. Not resolved over the
network by anything in this package -- ``contracts validate`` and every
test load schemas from local files under ``contracts/schemas/v<N>/``.
The URI exists only to give each schema a globally unique, stable
identity for ``$ref`` resolution and for consumers who *do* want to
publish these schemas at a real URL later."""


def contract_major_version() -> int:
    return int(CONTRACT_VERSION.split(".", 1)[0])


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_BASE_URI",
    "SCHEMA_ID_VERSION",
    "URN_GRAMMAR_VERSION",
    "contract_major_version",
]
