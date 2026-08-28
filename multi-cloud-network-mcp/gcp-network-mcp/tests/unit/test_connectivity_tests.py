from __future__ import annotations

import datetime
from types import SimpleNamespace

from google.cloud import network_management_v1 as nm
from google.rpc import status_pb2
from tests.conftest import PROJECT_ID, FakePager

from gcp_network_mcp.gcp.connectivity_tests import (
    _normalize_endpoint,
    _normalize_reachability_details,
    _normalize_step,
    get_connectivity_test,
    list_connectivity_tests,
    normalize_connectivity_test,
)

# --- _normalize_endpoint -------------------------------------------------------


def test_normalize_endpoint_returns_none_for_none() -> None:
    assert _normalize_endpoint(None) is None


def test_normalize_endpoint_maps_fields() -> None:
    endpoint = nm.Endpoint(
        ip_address="10.0.0.5",
        port=443,
        instance="projects/p/zones/z/instances/vm-1",
        network="projects/p/global/networks/vpc-1",
        project_id="other-project",
    )
    normalized = _normalize_endpoint(endpoint)
    assert normalized.ip_address == "10.0.0.5"
    assert normalized.port == 443
    assert normalized.instance == "projects/p/zones/z/instances/vm-1"
    assert normalized.network == "projects/p/global/networks/vpc-1"
    assert normalized.project_id == "other-project"


def test_normalize_endpoint_degrades_unset_fields_to_none() -> None:
    normalized = _normalize_endpoint(nm.Endpoint())
    assert normalized.ip_address is None
    assert normalized.port is None
    assert normalized.instance is None
    assert normalized.network is None
    assert normalized.project_id is None


# --- _normalize_step -------------------------------------------------------------


def test_normalize_step_drop_state() -> None:
    step = nm.Step(state=nm.Step.State.DROP, causes_drop=True)
    summary = _normalize_step(step)
    assert summary.state == "DROP"
    assert summary.detail == "DROP"
    assert summary.causes_drop is True


def test_normalize_step_arrive_at_instance_state() -> None:
    step = nm.Step(state=nm.Step.State.ARRIVE_AT_INSTANCE, causes_drop=False)
    summary = _normalize_step(step)
    assert summary.state == "ARRIVE_AT_INSTANCE"
    assert summary.detail == "ARRIVE_AT_INSTANCE"
    assert summary.causes_drop is False


# --- _normalize_reachability_details ---------------------------------------------


def test_normalize_reachability_details_maps_all_fields() -> None:
    verify_time = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    details = nm.ReachabilityDetails(
        result=nm.ReachabilityDetails.Result.UNREACHABLE,
        verify_time=verify_time,
        error=status_pb2.Status(code=7, message="permission denied"),
        traces=[
            nm.Trace(
                endpoint_info=nm.EndpointInfo(source_ip="1.1.1.1", destination_ip="2.2.2.2"),
                steps=[
                    nm.Step(state=nm.Step.State.START_FROM_INSTANCE, causes_drop=False),
                    nm.Step(state=nm.Step.State.DROP, causes_drop=True),
                ],
            )
        ],
    )
    result = _normalize_reachability_details(details)
    assert result.result == "UNREACHABLE"
    assert result.verify_time == details.verify_time.rfc3339()
    assert result.error == "permission denied"
    assert len(result.traces) == 1
    assert "1.1.1.1" in result.traces[0].endpoint_info
    assert len(result.traces[0].steps) == 2
    assert result.traces[0].steps[0].state == "START_FROM_INSTANCE"
    assert result.traces[0].steps[1].state == "DROP"
    assert result.traces[0].steps[1].causes_drop is True


def test_normalize_reachability_details_handles_unset_optional_fields() -> None:
    result = _normalize_reachability_details(nm.ReachabilityDetails())
    assert result.result is None
    assert result.verify_time is None
    assert result.error is None
    assert result.traces == []


# --- normalize_connectivity_test --------------------------------------------------


def test_normalize_connectivity_test_maps_full_fields() -> None:
    test = nm.ConnectivityTest(
        name="projects/p/locations/global/connectivityTests/t1",
        display_name="my test",
        description="a description",
        protocol="TCP",
        source=nm.Endpoint(ip_address="10.0.0.1"),
        destination=nm.Endpoint(ip_address="10.0.0.2", port=443),
        round_trip=True,
        reachability_details=nm.ReachabilityDetails(result=nm.ReachabilityDetails.Result.REACHABLE),
        create_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        update_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC),
    )
    normalized = normalize_connectivity_test(test, project_id=PROJECT_ID)
    assert normalized.name == "projects/p/locations/global/connectivityTests/t1"
    assert normalized.project_id == PROJECT_ID
    assert normalized.display_name == "my test"
    assert normalized.description == "a description"
    assert normalized.protocol == "TCP"
    assert normalized.source.ip_address == "10.0.0.1"
    assert normalized.destination.ip_address == "10.0.0.2"
    assert normalized.round_trip is True
    assert normalized.reachability_details.result == "REACHABLE"
    assert normalized.create_time is not None
    assert normalized.update_time is not None
    assert normalized.observed_at
    assert normalized.source_api == "ReachabilityServiceClient.list_connectivity_tests"


def test_normalize_connectivity_test_minimal_leaves_optional_fields_none() -> None:
    test = nm.ConnectivityTest(name="projects/p/locations/global/connectivityTests/t2")
    normalized = normalize_connectivity_test(test, project_id=PROJECT_ID)
    assert normalized.display_name is None
    assert normalized.description is None
    assert normalized.protocol is None
    assert normalized.source is None
    assert normalized.destination is None
    assert normalized.reachability_details is None
    assert normalized.create_time is None
    assert normalized.update_time is None


# --- list_connectivity_tests ----------------------------------------------------


def test_list_connectivity_tests_flattens_and_normalizes(client_factory) -> None:
    test1 = nm.ConnectivityTest(name="projects/p/locations/global/connectivityTests/t1")
    test2 = nm.ConnectivityTest(name="projects/p/locations/global/connectivityTests/t2")
    page = SimpleNamespace(resources=[test1, test2], unreachable=[])
    client_factory.connectivity_tests().list_connectivity_tests.return_value = FakePager([page])

    result = list_connectivity_tests(client_factory, project_id=PROJECT_ID)

    assert [t.name for t in result.data] == [
        "projects/p/locations/global/connectivityTests/t1",
        "projects/p/locations/global/connectivityTests/t2",
    ]
    assert result.warnings == []
    client_factory.connectivity_tests().list_connectivity_tests.assert_called_once_with(
        parent=f"projects/{PROJECT_ID}/locations/global"
    )


def test_list_connectivity_tests_surfaces_unreachable_locations(client_factory) -> None:
    page = SimpleNamespace(resources=[], unreachable=["projects/p/locations/us-central1"])
    client_factory.connectivity_tests().list_connectivity_tests.return_value = FakePager([page])

    result = list_connectivity_tests(client_factory, project_id=PROJECT_ID)

    assert result.data == []
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "UNREACHABLE"
    assert "projects/p/locations/us-central1" in result.warnings[0].message


def test_list_connectivity_tests_empty(client_factory) -> None:
    page = SimpleNamespace(resources=[], unreachable=[])
    client_factory.connectivity_tests().list_connectivity_tests.return_value = FakePager([page])

    result = list_connectivity_tests(client_factory, project_id=PROJECT_ID)
    assert result.data == []
    assert result.warnings == []


# --- get_connectivity_test ------------------------------------------------------


def test_get_connectivity_test_builds_full_resource_name(client_factory) -> None:
    test = nm.ConnectivityTest(name="projects/p/locations/global/connectivityTests/t1")
    client_factory.connectivity_tests().get_connectivity_test.return_value = test

    result = get_connectivity_test(client_factory, project_id=PROJECT_ID, test_name="t1")

    assert result.name == "projects/p/locations/global/connectivityTests/t1"
    client_factory.connectivity_tests().get_connectivity_test.assert_called_once_with(
        name=f"projects/{PROJECT_ID}/locations/global/connectivityTests/t1"
    )
