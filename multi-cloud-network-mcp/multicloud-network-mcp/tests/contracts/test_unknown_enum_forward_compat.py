"""Unknown enum forward compatibility: a normalization-target field
(``severity``, ``confidence``, ``resource_type``, route/firewall/
protocol/state vocabularies, etc.) must accept a value invented by a
FUTURE contract minor version that this code doesn't know about yet --
at both the Pydantic layer (no ValidationError) and the JSON Schema
layer (no ``enum`` constraint narrowing what validates). Structural
enums (``Provider``, ``NodeKind``, ``Completeness``, ``IpVersion``) are
the deliberate exception -- an unrecognized value there IS rejected,
since those represent this contract's own fixed grammar, not a
provider vocabulary that might grow. See ``models/enums.py``'s module
docstring for the full policy this test exists to keep honest.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from multicloud_network_mcp.contracts.models import (
    CloudScope,
    Finding,
    Network,
    Provider,
    TopologyEdge,
)
from multicloud_network_mcp.contracts.urn import build_urn

FRESHNESS = "2026-01-01T00:00:00+00:00"


def _urn() -> str:
    return build_urn(
        provider="aws", scope={"account_id": "1"}, resource_type="network", native_id="vpc-1"
    )


def test_finding_accepts_a_severity_value_this_code_has_never_heard_of() -> None:
    # "catastrophic" is not (and, per the versioning policy, never will
    # retroactively become) a member of this codebase's Severity enum --
    # it stands in for a value a FUTURE contract minor might add.
    finding = Finding(
        rule_id="FUTURE-001",
        rule_version="1.0.0",
        provider="aws",
        severity="catastrophic",
        confidence="high",
        summary="a finding from a newer contract minor",
        freshness=FRESHNESS,
    )
    assert finding.severity == "catastrophic"


def test_finding_accepts_a_confidence_value_this_code_has_never_heard_of() -> None:
    finding = Finding(
        rule_id="FUTURE-002",
        rule_version="1.0.0",
        provider="aws",
        severity="high",
        confidence="near-certain",
        summary="a finding using a newer confidence tier",
        freshness=FRESHNESS,
    )
    assert finding.confidence == "near-certain"


def test_network_accepts_a_resource_type_this_code_has_never_heard_of(
    aws_scope: CloudScope,
) -> None:
    # resource_type is plain str precisely so a payload produced under a
    # contract that added e.g. "service-mesh-endpoint" still parses.
    network = Network(
        urn=_urn(),
        native_id="vpc-1",
        resource_type="service-mesh-endpoint",
        provider=Provider.AWS,
        scope=aws_scope,
        observed_at=FRESHNESS,
        state="available",
    )
    assert network.resource_type == "service-mesh-endpoint"


def test_topology_edge_accepts_an_unrecognized_relationship_string() -> None:
    edge = TopologyEdge(
        source_urn=_urn(),
        target_urn=_urn(),
        relationship="quantum_entangled_with",
        evidence=[{"source": "x", "detail": "y"}],
    )
    assert edge.relationship == "quantum_entangled_with"


def test_normalization_target_field_schemas_have_no_enum_constraint() -> None:
    # The JSON Schema layer must be equally permissive -- a strict
    # `enum: [...]` constraint on severity/confidence would reject a
    # future value even though the Pydantic field itself accepts it.
    schema = Finding.model_json_schema()
    severity_prop = schema["properties"]["severity"]
    confidence_prop = schema["properties"]["confidence"]
    assert "enum" not in severity_prop
    assert "enum" not in confidence_prop
    assert severity_prop["type"] == "string"
    assert confidence_prop["type"] == "string"


def test_structural_enum_field_is_strict_by_contrast(aws_scope: CloudScope) -> None:
    # Provider/NodeKind/Completeness/IpVersion ARE strict -- an
    # unrecognized value here is a genuine structural incompatibility,
    # not a forward-compatible extension. This is the deliberate
    # asymmetry the module docstring describes; assert it holds.
    with pytest.raises(ValidationError):
        Network.model_validate(
            {
                "urn": _urn(),
                "native_id": "vpc-1",
                "resource_type": "network",
                "provider": "not-a-real-provider",
                "scope": aws_scope.model_dump(),
                "observed_at": FRESHNESS,
                "state": "available",
            }
        )


def test_structural_enum_schema_field_does_have_enum_constraint() -> None:
    schema = Network.model_json_schema()
    # `provider` on Network is a $ref into Provider's own $defs entry --
    # resolve it there, where the enum constraint actually lives.
    provider_ref = schema["properties"]["provider"]["$ref"]
    def_name = provider_ref.rsplit("/", 1)[-1]
    provider_def = schema["$defs"][def_name]
    assert "enum" in provider_def
    assert set(provider_def["enum"]) == {"aws", "azure", "gcp"}


def test_a_full_finding_json_payload_with_an_unknown_severity_parses_end_to_end() -> None:
    # Simulates receiving real wire data produced by a newer adapter.
    payload = {
        "rule_id": "NEWRULE-001",
        "rule_version": "2.0.0",
        "provider": "aws",
        "severity": "extreme",
        "confidence": "high",
        "summary": "test",
        "affected_resources": [],
        "evidence": [],
        "reasoning": [],
        "assumptions": [],
        "limitations": [],
        "freshness": FRESHNESS,
        "remediation": None,
    }
    finding = Finding.model_validate_json(json.dumps(payload))
    assert finding.severity == "extreme"
