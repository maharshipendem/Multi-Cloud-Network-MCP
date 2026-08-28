from __future__ import annotations

from gcp_network_mcp.diagnostics.peering import evaluate_peering
from gcp_network_mcp.models.peering import NetworkPeering

FRESHNESS = "2026-08-27T00:00:00Z"
OWNING_NETWORK = "https://www.googleapis.com/compute/v1/projects/p/global/networks/vpc-1"
PEER_NETWORK = "https://www.googleapis.com/compute/v1/projects/p/global/networks/vpc-2"


def _peering(
    *,
    state: str | None = "ACTIVE",
    exchange_subnet_routes: bool | None = True,
    import_custom_routes: bool | None = True,
    export_custom_routes: bool | None = True,
) -> NetworkPeering:
    return NetworkPeering(
        name="peer-1",
        owning_network_self_link=OWNING_NETWORK,
        network=PEER_NETWORK,
        state=state,
        exchange_subnet_routes=exchange_subnet_routes,
        import_custom_routes=import_custom_routes,
        export_custom_routes=export_custom_routes,
    )


def test_healthy_active_peering_is_info_severity() -> None:
    finding = evaluate_peering(peering=_peering(), freshness=FRESHNESS)
    assert finding.severity == "info"
    assert finding.confidence == "high"
    assert finding.evidence
    # non-transitivity caveat is always surfaced, even for the healthy case
    assert finding.limitations


def test_non_active_state_is_flagged_high_severity() -> None:
    finding = evaluate_peering(peering=_peering(state="INACTIVE"), freshness=FRESHNESS)
    assert finding.severity == "high"
    assert finding.confidence == "high"
    assert "INACTIVE" in finding.summary
    assert finding.evidence
    assert finding.remediation is not None


def test_exchange_subnet_routes_false_is_flagged_independently() -> None:
    finding = evaluate_peering(
        peering=_peering(state="ACTIVE", exchange_subnet_routes=False), freshness=FRESHNESS
    )
    assert finding.severity == "medium"
    assert finding.confidence == "high"
    assert "exchange_subnet_routes=false" in finding.summary
    assert finding.evidence


def test_custom_routes_both_disabled_is_flagged_independently() -> None:
    finding = evaluate_peering(
        peering=_peering(
            state="ACTIVE",
            exchange_subnet_routes=True,
            import_custom_routes=False,
            export_custom_routes=False,
        ),
        freshness=FRESHNESS,
    )
    assert finding.severity == "low"
    assert finding.confidence == "medium"
    assert finding.evidence
    assert finding.limitations


def test_one_sided_custom_routes_is_not_flagged_as_both_disabled() -> None:
    """Only import OR only export disabled is not the 'both disabled'
    limitation case -- the peering falls through to the healthy branch."""
    finding = evaluate_peering(
        peering=_peering(
            state="ACTIVE",
            exchange_subnet_routes=True,
            import_custom_routes=True,
            export_custom_routes=False,
        ),
        freshness=FRESHNESS,
    )
    assert finding.severity == "info"


def test_severities_differ_across_distinct_limitations() -> None:
    non_active = evaluate_peering(peering=_peering(state="SUSPENDED"), freshness=FRESHNESS)
    no_subnet_exchange = evaluate_peering(
        peering=_peering(state="ACTIVE", exchange_subnet_routes=False), freshness=FRESHNESS
    )
    no_custom_routes = evaluate_peering(
        peering=_peering(
            state="ACTIVE",
            exchange_subnet_routes=True,
            import_custom_routes=False,
            export_custom_routes=False,
        ),
        freshness=FRESHNESS,
    )
    severities = {non_active.severity, no_subnet_exchange.severity, no_custom_routes.severity}
    assert severities == {"high", "medium", "low"}


def test_null_state_does_not_trigger_non_active_check() -> None:
    """peering.state=None is falsy, so the `state != ACTIVE` branch is
    skipped entirely -- it falls through toward the healthy/other checks
    rather than being reported as a non-ACTIVE state."""
    finding = evaluate_peering(peering=_peering(state=None), freshness=FRESHNESS)
    assert finding.severity != "high"
