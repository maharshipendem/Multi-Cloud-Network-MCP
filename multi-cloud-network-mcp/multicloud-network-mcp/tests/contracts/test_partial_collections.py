"""Partial collections: a disabled API, missing permission, or bounded
fan-out cap must always surface as a ``CollectionWarning`` and force
``completeness`` to ``"partial"`` -- enforced by construction, not just
convention. See ``models/envelope.py::PartialResultMetadata`` and
``models/topology.py::TopologyGraph``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from multicloud_network_mcp.contracts.models import (
    CollectionWarning,
    PartialResultMetadata,
    TopologyGraph,
)


def _warning() -> CollectionWarning:
    return CollectionWarning(
        resource_type="network", code="COLLECTION_FAILED", message="API disabled"
    )


def test_partial_result_metadata_defaults_to_complete_with_no_warnings() -> None:
    metadata = PartialResultMetadata()
    assert metadata.completeness == "complete"
    assert metadata.warnings == []


def test_partial_result_metadata_accepts_partial_with_warnings() -> None:
    metadata = PartialResultMetadata(completeness="partial", warnings=[_warning()])
    assert metadata.completeness == "partial"
    assert len(metadata.warnings) == 1


def test_partial_result_metadata_rejects_complete_with_warnings_present() -> None:
    with pytest.raises(ValidationError, match="must be PARTIAL"):
        PartialResultMetadata(completeness="complete", warnings=[_warning()])


def test_partial_result_metadata_rejects_default_completeness_with_warnings() -> None:
    # The most realistic mistake: a caller populates warnings but
    # forgets to also set completeness="partial", relying on the
    # default -- that must still be caught, not silently accepted.
    with pytest.raises(ValidationError, match="must be PARTIAL"):
        PartialResultMetadata(warnings=[_warning()])


def test_topology_graph_rejects_complete_with_warnings_present(aws_scope) -> None:
    with pytest.raises(ValidationError, match="must be PARTIAL"):
        TopologyGraph(scope=aws_scope, completeness="complete", warnings=[_warning()])


def test_topology_graph_accepts_partial_with_warnings(aws_scope) -> None:
    graph = TopologyGraph(scope=aws_scope, completeness="partial", warnings=[_warning()])
    assert graph.completeness == "partial"


def test_topology_graph_defaults_to_complete_with_no_warnings(aws_scope) -> None:
    graph = TopologyGraph(scope=aws_scope)
    assert graph.completeness == "complete"
    assert graph.api_call_count == 0


def test_collection_warning_carries_resource_type_code_message() -> None:
    warning = _warning()
    assert warning.resource_type == "network"
    assert warning.code == "COLLECTION_FAILED"
    assert warning.message == "API disabled"
    assert warning.resource_type_hint is None
    assert warning.scope is None


def test_collection_warning_resource_type_is_free_text_not_closed() -> None:
    # A warning can legitimately be about something outside the 21
    # canonical resource kinds (e.g. a metrics query, a Shared VPC host
    # status lookup) -- resource_type must not be validated against the
    # closed ResourceType enum.
    warning = CollectionWarning(
        resource_type="shared_vpc_host_status", code="COLLECTION_FAILED", message="denied"
    )
    assert warning.resource_type == "shared_vpc_host_status"
