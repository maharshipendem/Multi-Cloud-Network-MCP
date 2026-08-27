"""AWS client factory and service layer.

Business logic for talking to specific AWS services lives here (accounts,
regions, networking), always going through ``client_factory`` for client
construction and ``security.guardrails`` for read-only enforcement. Tool
modules under ``aws_cloudops_mcp.tools`` should never construct a boto3
client directly.
"""
