"""Service-layer functions for Network Management Connectivity Tests --
reads *existing* tests and their last-computed reachability result only.
This server never calls ``create_connectivity_test``/
``rerun_connectivity_test``/``update_connectivity_test``/
``delete_connectivity_test`` (see security/guardrails.py's
``BLOCKED_ACTIONS``); a test's ``reachability_details`` reflects whenever
it was last (re)run by someone else, not a fresh probe this call
triggers."""

from __future__ import annotations

from google.cloud import network_management_v1 as nm

from gcp_network_mcp.gcp.client_factory import ClientFactory
from gcp_network_mcp.gcp.collection import CollectionResult, now_iso
from gcp_network_mcp.gcp.pagination import paginate_with_unreachable
from gcp_network_mcp.gcp.readonly import call_readonly
from gcp_network_mcp.models.connectivity_test import (
    ConnectivityTest,
    ConnectivityTestEndpoint,
    ConnectivityTestResult,
    ConnectivityTestStepSummary,
    ConnectivityTestTraceSummary,
)


def _normalize_endpoint(endpoint: nm.Endpoint) -> ConnectivityTestEndpoint | None:
    if endpoint is None:
        return None
    return ConnectivityTestEndpoint(
        ip_address=endpoint.ip_address or None,
        port=endpoint.port or None,
        instance=endpoint.instance or None,
        network=endpoint.network or None,
        project_id=endpoint.project_id or None,
    )


def _normalize_step(step: nm.Step) -> ConnectivityTestStepSummary:
    state_name = step.state.name
    return ConnectivityTestStepSummary(
        state=state_name,
        causes_drop=step.causes_drop,
        detail=state_name,
    )


def _normalize_reachability_details(details: nm.ReachabilityDetails) -> ConnectivityTestResult:
    return ConnectivityTestResult(
        result=details.result.name if "result" in details else None,
        verify_time=details.verify_time.rfc3339() if "verify_time" in details else None,
        error=details.error.message if "error" in details else None,
        traces=[
            ConnectivityTestTraceSummary(
                endpoint_info=str(trace.endpoint_info) if "endpoint_info" in trace else None,
                steps=[_normalize_step(s) for s in trace.steps],
            )
            for trace in details.traces
        ],
    )


def normalize_connectivity_test(test: nm.ConnectivityTest, *, project_id: str) -> ConnectivityTest:
    return ConnectivityTest(
        name=test.name,
        project_id=project_id,
        display_name=test.display_name or None,
        description=test.description or None,
        protocol=test.protocol or None,
        source=_normalize_endpoint(test.source) if "source" in test else None,
        destination=_normalize_endpoint(test.destination) if "destination" in test else None,
        round_trip=test.round_trip,
        reachability_details=(
            _normalize_reachability_details(test.reachability_details)
            if "reachability_details" in test
            else None
        ),
        create_time=test.create_time.rfc3339() if "create_time" in test else None,
        update_time=test.update_time.rfc3339() if "update_time" in test else None,
        observed_at=now_iso(),
    )


def list_connectivity_tests(client_factory: ClientFactory, *, project_id: str) -> CollectionResult:
    raw, warnings = paginate_with_unreachable(
        client_factory.connectivity_tests(),
        "list_connectivity_tests",
        resource_type="connectivity_test",
        project_id=project_id,
        items_field="resources",
        parent=f"projects/{project_id}/locations/global",
    )
    return CollectionResult(
        data=[normalize_connectivity_test(t, project_id=project_id) for t in raw], warnings=warnings
    )


def get_connectivity_test(
    client_factory: ClientFactory, *, project_id: str, test_name: str
) -> ConnectivityTest:
    test = call_readonly(
        client_factory.connectivity_tests(),
        "get_connectivity_test",
        name=f"projects/{project_id}/locations/global/connectivityTests/{test_name}",
    )
    return normalize_connectivity_test(test, project_id=project_id)


__all__ = ["get_connectivity_test", "list_connectivity_tests", "normalize_connectivity_test"]
