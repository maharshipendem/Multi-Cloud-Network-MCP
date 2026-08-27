"""AWS service layer: STS identity operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cloudops_mcp.aws.readonly import call_readonly
from aws_cloudops_mcp.models.common import CallerIdentity

if TYPE_CHECKING:
    from aws_cloudops_mcp.aws.client_factory import ClientFactory


def get_caller_identity(
    client_factory: ClientFactory, *, role_arn: str | None = None
) -> CallerIdentity:
    """Call sts:GetCallerIdentity and return the normalized identity."""
    client = client_factory.get_client("sts", role_arn=role_arn)
    response = call_readonly(client, "get_caller_identity")
    return CallerIdentity(
        account_id=response["Account"],
        arn=response["Arn"],
        user_id=response["UserId"],
    )
