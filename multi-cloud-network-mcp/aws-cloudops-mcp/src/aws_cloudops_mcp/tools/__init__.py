"""MCP tool layer.

Tool modules translate MCP tool calls into calls against the AWS service
layer (``aws_cloudops_mcp.aws``). They must never construct a boto3 client
or call botocore directly -- that responsibility belongs to the AWS service
layer and the client factory.
"""
