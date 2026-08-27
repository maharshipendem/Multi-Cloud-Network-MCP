# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - Milestone 1 - Foundation

### Added

- MCP server foundation (stdio transport) with a layered architecture
  separating MCP transport, tool layer, security guardrails, AWS service
  layer, AWS client factory, and authentication.
- boto3-based AWS client factory with centralized region/retry/timeout
  configuration and session caching.
- AWS authentication supporting the standard boto3 credential chain
  (environment, shared config/credentials files, SSO profiles, IAM roles)
  plus optional cross-account `sts:AssumeRole` with automatic credential
  refresh.
- Structured JSON logging with per-request correlation IDs.
- Application-level read-only security guardrails, independent of IAM.
- Five MCP tools: `aws_get_caller_identity`, `aws_list_regions`,
  `aws_list_vpcs`, `aws_list_subnets`, `aws_list_route_tables`.
- Standard tool response envelope and custom exception hierarchy with
  AWS-error-to-client-error translation.
- Reusable AWS pagination helper and tag normalizer.
- Unit test suite (mocked AWS via moto) and an opt-in integration test
  suite marked `@pytest.mark.integration`.
- Dockerfile and docker-compose for local development.
- README, architecture/security/tools/development documentation, example
  least-privilege IAM policy, `.env.example`.

[Unreleased]: https://github.com/example/aws-cloudops-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/example/aws-cloudops-mcp/releases/tag/v0.1.0
