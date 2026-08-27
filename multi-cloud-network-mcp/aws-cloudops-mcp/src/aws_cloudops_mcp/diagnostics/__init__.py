"""Deterministic, read-only AWS network diagnostics.

This package is intentionally independent of both the MCP transport
(``aws_cloudops_mcp.tools``, ``aws_cloudops_mcp.server``) and boto3/botocore
(``aws_cloudops_mcp.aws``). It consumes only the already-normalized,
plain-pydantic models from ``aws_cloudops_mcp.models`` -- assembled into a
:class:`~aws_cloudops_mcp.diagnostics.snapshot.NetworkSnapshot`, which is
either collected live (``aws_cloudops_mcp.aws.snapshot``) or loaded from a
saved fixture file for the offline dry-run mode.

Every diagnostic is a pure function: ``NetworkSnapshot`` (+ a small amount
of query context, e.g. a source/destination pair) in, a list of
:class:`~aws_cloudops_mcp.diagnostics.models.Finding` out. No network I/O,
no randomness, no wall-clock reads (other than what is already stamped on
the input snapshot) -- the same snapshot always produces the same findings,
which is what makes this package testable without an LLM and safe to golden-
test.
"""
