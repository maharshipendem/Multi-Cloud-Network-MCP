from __future__ import annotations

from unittest.mock import patch

import boto3
from botocore.stub import Stubber

from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.aws.network_insights import (
    get_access_scope_analysis_findings,
    list_network_insights_access_scope_analyses,
    list_network_insights_access_scopes,
    list_network_insights_analyses,
    list_network_insights_paths,
)

# moto does not implement any Reachability Analyzer / Network Access
# Analyzer operation (raises Python NotImplementedError, not a
# botocore ClientError) -- every test here is Stubber-based against the
# real service model instead.


def test_list_network_insights_paths(client_factory: ClientFactory) -> None:
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "describe_network_insights_paths",
        {
            "NetworkInsightsPaths": [
                {
                    "NetworkInsightsPathId": "nip-0123456789abcdef0",
                    "NetworkInsightsPathArn": (
                        "arn:aws:ec2:us-east-1:123456789012:network-insights-path/"
                        "nip-0123456789abcdef0"
                    ),
                    "Source": "eni-0123456789abcdef0",
                    "Destination": "eni-0fedcba9876543210",
                    "Protocol": "tcp",
                    "DestinationPort": 443,
                }
            ]
        },
        {},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        paths = list_network_insights_paths(client_factory, region="us-east-1")

    assert len(paths) == 1
    assert paths[0].network_insights_path_id == "nip-0123456789abcdef0"
    assert paths[0].destination_port == 443
    stubber.assert_no_pending_responses()


def test_list_network_insights_analyses_reports_path_not_found(
    client_factory: ClientFactory,
) -> None:
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "describe_network_insights_analyses",
        {
            "NetworkInsightsAnalyses": [
                {
                    "NetworkInsightsAnalysisId": "nia-0123456789abcdef0",
                    "NetworkInsightsPathId": "nip-0123456789abcdef0",
                    "Status": "succeeded",
                    "NetworkPathFound": False,
                    "WarningMessage": "No path found between source and destination.",
                }
            ]
        },
        {"NetworkInsightsPathId": "nip-0123456789abcdef0"},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        analyses = list_network_insights_analyses(
            client_factory, region="us-east-1", network_insights_path_id="nip-0123456789abcdef0"
        )

    assert len(analyses) == 1
    assert analyses[0].network_path_found is False
    assert "No path found" in (analyses[0].warning_message or "")
    stubber.assert_no_pending_responses()


def test_list_network_insights_access_scopes(client_factory: ClientFactory) -> None:
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "describe_network_insights_access_scopes",
        {
            "NetworkInsightsAccessScopes": [
                {
                    "NetworkInsightsAccessScopeId": "nis-0123456789abcdef0",
                    "NetworkInsightsAccessScopeArn": (
                        "arn:aws:ec2:us-east-1:123456789012:network-insights-access-scope/"
                        "nis-0123456789abcdef0"
                    ),
                }
            ]
        },
        {},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        scopes = list_network_insights_access_scopes(client_factory, region="us-east-1")

    assert len(scopes) == 1
    assert scopes[0].network_insights_access_scope_id == "nis-0123456789abcdef0"
    stubber.assert_no_pending_responses()


def test_list_network_insights_access_scope_analyses_findings_found(
    client_factory: ClientFactory,
) -> None:
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "describe_network_insights_access_scope_analyses",
        {
            "NetworkInsightsAccessScopeAnalyses": [
                {
                    "NetworkInsightsAccessScopeAnalysisId": "nisa-0123456789abcdef0",
                    "NetworkInsightsAccessScopeId": "nis-0123456789abcdef0",
                    "Status": "succeeded",
                    "FindingsFound": "true",
                    "AnalyzedEniCount": 12,
                }
            ]
        },
        {},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        analyses = list_network_insights_access_scope_analyses(client_factory, region="us-east-1")

    assert len(analyses) == 1
    assert analyses[0].findings_found == "true"
    assert analyses[0].analyzed_eni_count == 12
    stubber.assert_no_pending_responses()


def test_get_access_scope_analysis_findings(client_factory: ClientFactory) -> None:
    real_client = boto3.client("ec2", region_name="us-east-1")
    stubber = Stubber(real_client)
    stubber.add_response(
        "get_network_insights_access_scope_analysis_findings",
        {
            "NetworkInsightsAccessScopeAnalysisId": "nisa-0123456789abcdef0",
            "AnalysisStatus": "succeeded",
            "AnalysisFindings": [
                {
                    "NetworkInsightsAccessScopeAnalysisId": "nisa-0123456789abcdef0",
                    "NetworkInsightsAccessScopeId": "nis-0123456789abcdef0",
                    "FindingId": "nisaf-0123456789abcdef0",
                    "FindingComponents": [
                        {
                            "Component": {
                                "Id": "eni-0123456789abcdef0",
                                "Arn": (
                                    "arn:aws:ec2:us-east-1:123456789012:network-interface/"
                                    "eni-0123456789abcdef0"
                                ),
                            }
                        }
                    ],
                }
            ],
        },
        {"NetworkInsightsAccessScopeAnalysisId": "nisa-0123456789abcdef0"},
    )
    stubber.activate()

    client_factory._account_id_cache["__base__"] = "123456789012"
    with patch.object(client_factory, "get_client", return_value=real_client):
        findings = get_access_scope_analysis_findings(
            client_factory,
            region="us-east-1",
            network_insights_access_scope_analysis_id="nisa-0123456789abcdef0",
        )

    assert len(findings) == 1
    assert findings[0].finding_id == "nisaf-0123456789abcdef0"
    assert findings[0].finding_components[0].component_id == "eni-0123456789abcdef0"
    stubber.assert_no_pending_responses()
