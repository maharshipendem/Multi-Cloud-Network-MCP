"""JSON structured logging with correlation-id propagation.

Every tool invocation is logged as a single structured record so the output
can be shipped as-is to CloudWatch Logs, Splunk, Datadog, or an ELK stack.
Credentials and full AWS API payloads are never logged -- only normalized,
operationally-relevant fields.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_EXTRA_FIELDS = (
    "tool_name",
    "account_id",
    "region",
    "duration_ms",
    "status",
    "aws_error_code",
)

_CONFIGURED = False


class JSONFormatter(logging.Formatter):
    """Renders log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger for JSON structured output on stderr.

    Logs are written to stderr (not stdout) because stdout is reserved for
    the MCP stdio transport's protocol messages.
    """
    global _CONFIGURED
    root = logging.getLogger()
    root.setLevel(level.upper())

    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JSONFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
