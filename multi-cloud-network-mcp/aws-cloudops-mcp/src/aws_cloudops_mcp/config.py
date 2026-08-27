"""Application configuration, sourced from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the aws-cloudops-mcp server.

    Values are resolved from process environment variables first, falling
    back to a local ``.env`` file if present. Nothing here may hold a real
    secret value by default -- credentials are always resolved through the
    standard AWS credential chain, never stored in configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "aws-cloudops-mcp"
    log_level: str = "INFO"

    # AWS authentication / session
    aws_profile: str | None = None
    aws_default_region: str = "us-east-1"
    aws_role_arn: str | None = None
    aws_external_id: str | None = None
    aws_session_name: str = "aws-cloudops-mcp"

    # boto3/botocore client tuning
    aws_max_attempts: int = 3
    aws_connect_timeout: int = 5
    aws_read_timeout: int = 20

    # Safety limit on paginated AWS API results returned by a single tool call
    max_page_results: int = 1000

    # Safety limit on the number of *extra, per-item* AWS API calls a single
    # tool invocation may make for optional enrichment or joins that AWS does
    # not expose as a single batch call (e.g. per-VPC DNS attributes, per-
    # target-group target health, per-prefix-list entries, topology
    # assembly). Items beyond this cap are skipped with a recorded warning
    # rather than silently omitted.
    max_fanout_calls: int = 50


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
