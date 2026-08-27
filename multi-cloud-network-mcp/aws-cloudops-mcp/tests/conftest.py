"""Shared pytest fixtures.

Unit tests never touch real AWS credentials or accounts: the
``aws_credentials`` fixture below is autouse and pins fake, obviously-fake
credentials into the environment for every test so nothing can accidentally
fall through to a real credential chain (e.g. a developer's ``~/.aws``
profile). Integration tests that need real credentials live under
``tests/integration`` and are marked ``@pytest.mark.integration``, which is
excluded by default (see ``pyproject.toml``'s ``addopts``).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from aws_cloudops_mcp.auth.session import SessionManager
from aws_cloudops_mcp.aws.client_factory import ClientFactory
from aws_cloudops_mcp.config import Settings


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def settings() -> Settings:
    return Settings(aws_default_region="us-east-1", aws_role_arn=None, aws_profile=None)


@pytest.fixture
def client_factory(settings: Settings) -> Iterator[ClientFactory]:
    yield ClientFactory(settings, SessionManager(settings))
