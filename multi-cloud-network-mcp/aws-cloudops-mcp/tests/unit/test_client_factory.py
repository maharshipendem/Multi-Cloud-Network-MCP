from __future__ import annotations

from unittest.mock import patch

from moto import mock_aws

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws import accounts as accounts_module
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.config import Settings


@mock_aws
def test_get_client_applies_region_and_config(settings: Settings) -> None:
    factory = ClientFactory(settings, SessionManager(settings))
    client = factory.get_client("ec2", region="eu-west-1")

    assert client.meta.region_name == "eu-west-1"
    # botocore normalizes max_attempts (retry attempts) into total_max_attempts
    # (max_attempts + the initial call) once a retry "mode" is set.
    assert client.meta.config.retries["total_max_attempts"] == settings.aws_max_attempts + 1
    assert client.meta.config.retries["mode"] == "standard"
    assert client.meta.config.connect_timeout == settings.aws_connect_timeout
    assert client.meta.config.read_timeout == settings.aws_read_timeout


@mock_aws
def test_get_client_defaults_to_configured_region(settings: Settings) -> None:
    factory = ClientFactory(settings, SessionManager(settings))
    client = factory.get_client("ec2")
    assert client.meta.region_name == settings.aws_default_region


@mock_aws
def test_get_account_id_is_cached_across_calls(settings: Settings) -> None:
    factory = ClientFactory(settings, SessionManager(settings))

    with patch.object(
        accounts_module, "get_caller_identity", wraps=accounts_module.get_caller_identity
    ) as spy:
        first = factory.get_account_id()
        second = factory.get_account_id()

    assert first == second
    assert spy.call_count == 1


@mock_aws
def test_get_account_id_returns_moto_default_account(settings: Settings) -> None:
    factory = ClientFactory(settings, SessionManager(settings))
    account_id = factory.get_account_id()
    assert account_id == "123456789012"
