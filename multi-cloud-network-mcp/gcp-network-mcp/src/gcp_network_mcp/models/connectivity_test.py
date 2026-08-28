"""Normalized models for Network Management Connectivity Tests --
reads *existing* tests and their last-computed reachability result only.
This server never creates, reruns, updates, or deletes a Connectivity
Test (see security/guardrails.py's ``BLOCKED_ACTIONS``)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConnectivityTestEndpoint(BaseModel):
    ip_address: str | None = None
    port: int | None = None
    instance: str | None = None
    network: str | None = None
    project_id: str | None = None


class ConnectivityTestStepSummary(BaseModel):
    """One step of a trace's evaluated path. ``state`` is GCP's own
    step-kind enum (e.g. ``"APPLY_INGRESS_FIREWALL_RULE"``,
    ``"DROP"``, ``"ARRIVE_AT_INSTANCE"``) -- already descriptive enough
    that this server doesn't re-model each of the ~30 possible oneof
    step-detail sub-messages (firewall rule matched, route matched, ...)
    GCP's API defines; ``detail`` currently mirrors ``state`` and is kept
    as its own field so a future milestone can enrich it with the
    oneof-selected sub-message's content without a model change."""

    state: str | None = None
    causes_drop: bool = False
    detail: str


class ConnectivityTestTraceSummary(BaseModel):
    endpoint_info: str | None = None
    steps: list[ConnectivityTestStepSummary] = Field(default_factory=list)


class ConnectivityTestResult(BaseModel):
    """From ``ConnectivityTest.reachability_details`` -- the last time
    this test was (re)run, never triggered by this server."""

    result: str | None = None
    verify_time: str | None = None
    error: str | None = None
    traces: list[ConnectivityTestTraceSummary] = Field(default_factory=list)


class ConnectivityTest(BaseModel):
    name: str
    project_id: str
    display_name: str | None = None
    description: str | None = None
    protocol: str | None = None
    source: ConnectivityTestEndpoint | None = None
    destination: ConnectivityTestEndpoint | None = None
    round_trip: bool | None = None
    reachability_details: ConnectivityTestResult | None = None
    create_time: str | None = None
    update_time: str | None = None
    observed_at: str
    source_api: str = "ReachabilityServiceClient.list_connectivity_tests"


__all__ = [
    "ConnectivityTest",
    "ConnectivityTestEndpoint",
    "ConnectivityTestResult",
    "ConnectivityTestStepSummary",
    "ConnectivityTestTraceSummary",
]
