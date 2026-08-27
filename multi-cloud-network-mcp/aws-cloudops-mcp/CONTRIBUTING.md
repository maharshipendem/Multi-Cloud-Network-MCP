# Contributing

Thanks for your interest in aws-cloudops-mcp.

## Ground rules

- **Milestone 1 is read-only.** Do not add code that calls a mutating AWS
  API (anything that isn't `Describe*`/`Get*`/`List*`), and do not weaken
  `src/aws_cloudops_mcp/security/guardrails.py` to allow one. See
  [docs/security.md](docs/security.md).
- Keep the layered architecture in [docs/architecture.md](docs/architecture.md):
  tool code never calls boto3 directly; it goes through the AWS service
  layer and client factory.
- No AWS credentials, account IDs, ARNs, or other real/internal identifiers
  in code, tests, docs, or commit messages — use the placeholder patterns
  already present in the codebase (e.g. `123456789012`,
  `vpc-0123456789abcdef0`).
- Do not build Azure or GCP functionality in this repository. This project
  is one server in a planned multi-cloud family; each cloud gets its own
  repository.

## Development setup

See [docs/development.md](docs/development.md).

## Before opening a pull request

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

All four must pass. Add unit tests for new behavior (mocked AWS via moto —
no real credentials required). If you add a new MCP tool, update
[docs/tools.md](docs/tools.md), including its required IAM permission and
an entry in the example policy.

## Commit style

Keep commits focused and descriptive. Conventional-commit-style prefixes
(`feat:`, `fix:`, `docs:`, `test:`, `chore:`) are appreciated but not
required.

## Reporting security issues

Do not open a public issue for a security vulnerability — see
[SECURITY.md](SECURITY.md).
