from __future__ import annotations

from moto import mock_aws

from aws_cloudops_mcp.aws.accounts import get_caller_identity
from aws_cloudops_mcp.aws.client_factory import ClientFactory


@mock_aws
def test_get_caller_identity_returns_normalized_fields(client_factory: ClientFactory) -> None:
    identity = get_caller_identity(client_factory)

    assert identity.account_id == "123456789012"
    assert identity.arn.startswith("arn:aws:")
    assert identity.user_id
