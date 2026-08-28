"""Golden contract tests over ``contracts/examples/``.

**This test is designed to be copied into each cloud repo's own test
suite**, pointed at that repo's own exported fixtures instead of the
example files here -- the only two things a copy needs to change are
(1) the ``_EXAMPLES_DIR`` constant below, pointed at wherever that repo
keeps its own contract-conformant fixtures, and (2) making
``multicloud_network_mcp`` a dev/test-only dependency there (never a
runtime one -- see ``docs/adr/0001-no-runtime-coupling.md``) purely so
its own CI can run this exact validation without hand-duplicating
schema logic. Everything else -- the assertions, the parametrization --
is meant to travel unchanged.

This file also doubles as this milestone's own proof that
``contracts/examples/{aws,azure,gcp}/`` are collectively valid, which
is what ``python -m multicloud_network_mcp.contracts validate
contracts/examples`` checks from the CLI side; this test checks the
same thing from pytest, plus extra structural assertions the CLI
doesn't make (e.g. "every provider has at least N examples," "no two
examples share a URN").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from multicloud_network_mcp.contracts.urn import parse_urn
from multicloud_network_mcp.contracts.validate import validate_directory

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "contracts" / "examples"
_PROVIDERS = ["aws", "azure", "gcp"]


def _example_files(provider: str) -> list[Path]:
    return sorted((_EXAMPLES_DIR / provider).glob("*.json"))


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_every_example_passes_both_schema_and_model_validation(provider: str) -> None:
    files = _example_files(provider)
    assert files, f"no example files found for provider={provider!r}"
    report = validate_directory(_EXAMPLES_DIR / provider)
    failures = [f"{r.path.name}: {r.errors}" for r in report.results if not r.passed]
    assert not failures, "\n".join(failures)


def test_validate_directory_covers_the_whole_examples_tree() -> None:
    report = validate_directory(_EXAMPLES_DIR)
    assert report.results, "no examples found under contracts/examples at all"
    failures = [f"{r.path}: {r.errors}" for r in report.results if not r.passed]
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_every_example_urn_is_well_formed_and_matches_its_own_provider(provider: str) -> None:
    for path in _example_files(provider):
        if path.name == "NOTES.md":
            continue
        data = json.loads(path.read_text())
        urn = data.get("urn")
        if urn is None:
            # Non-resource examples (finding, path-explanation,
            # response-envelope, provider-capability-manifest,
            # topology-graph, collection-warning) don't carry a
            # top-level urn field themselves.
            continue
        parsed = parse_urn(urn)
        assert parsed.provider == provider, (
            f"{path.name}: urn provider {parsed.provider!r} != {provider!r}"
        )


def test_no_two_examples_share_a_urn_across_the_whole_tree() -> None:
    seen: dict[str, Path] = {}
    for provider in _PROVIDERS:
        for path in _example_files(provider):
            if path.name == "NOTES.md":
                continue
            data = json.loads(path.read_text())
            urn = data.get("urn")
            if urn is None:
                continue
            assert urn not in seen, f"duplicate URN {urn!r} in {path} and {seen[urn]}"
            seen[urn] = path


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_each_provider_has_a_capability_manifest_example(provider: str) -> None:
    matches = [
        p for p in _example_files(provider) if p.name.startswith("provider-capability-manifest.")
    ]
    assert len(matches) == 1, f"expected exactly one capability manifest example for {provider!r}"
    data = json.loads(matches[0].read_text())
    assert data["provider"] == provider


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_each_provider_has_a_topology_graph_example_with_all_three_node_kinds(
    provider: str,
) -> None:
    matches = [p for p in _example_files(provider) if p.name.startswith("topology-graph.")]
    assert len(matches) == 1, f"expected exactly one topology-graph example for {provider!r}"
    data = json.loads(matches[0].read_text())
    kinds = {node["kind"] for node in data["nodes"]}
    assert kinds == {"resource", "external", "unresolved"}, (
        f"{provider}'s topology-graph example doesn't demonstrate all three "
        f"NodeKind values: {kinds}"
    )
