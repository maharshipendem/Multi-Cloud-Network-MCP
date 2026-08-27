from __future__ import annotations

import pytest

from aws_cloudops_mcp.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_ROLE_ARN", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.app_name == "aws-cloudops-mcp"
    assert settings.log_level == "INFO"
    assert settings.aws_default_region == "us-east-1"
    assert settings.aws_role_arn is None
    assert settings.aws_profile is None
    assert settings.aws_session_name == "aws-cloudops-mcp"
    assert settings.aws_max_attempts == 3
    assert settings.aws_connect_timeout == 5
    assert settings.aws_read_timeout == 20
    assert settings.max_page_results == 1000


def test_env_var_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    monkeypatch.setenv("AWS_ROLE_ARN", "arn:aws:iam::123456789012:role/example")
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "7")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.aws_default_region == "eu-west-2"
    assert settings.aws_role_arn == "arn:aws:iam::123456789012:role/example"
    assert settings.aws_max_attempts == 7
    assert settings.log_level == "DEBUG"


def test_explicit_kwargs_take_precedence_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    settings = Settings(aws_default_region="ap-southeast-2", _env_file=None)  # type: ignore[call-arg]
    assert settings.aws_default_region == "ap-southeast-2"
