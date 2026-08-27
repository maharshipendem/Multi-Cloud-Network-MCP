# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in aws-cloudops-mcp, please report
it privately rather than opening a public GitHub issue. Open a
[GitHub Security Advisory](../../security/advisories/new) for this
repository, or contact the maintainers directly if that is unavailable.

Please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal example is ideal)
- The version/commit affected

We will acknowledge reports as promptly as possible and aim to provide a
fix or mitigation before public disclosure.

## Scope

aws-cloudops-mcp is intentionally **read-only** in its current milestone
(see [docs/security.md](docs/security.md)). Reports of highest interest:

- Any code path that could cause a mutating AWS API call
- Any way credentials, access keys, secret keys, or session tokens could be
  logged, leaked, or exposed via an MCP response
- Any way the read-only guardrail layer (`security/guardrails.py`) could be
  bypassed
- Any way one configured AWS identity's data could be returned under
  another identity's context

## Supported versions

This project is pre-1.0 and under active early development. Security fixes
are applied to the latest release only.

## Out of scope

- Vulnerabilities requiring an attacker to already have write access to the
  AWS account/credentials this server is configured with — IAM is the
  authoritative permission boundary, not this application (see
  [docs/security.md](docs/security.md)).
- Denial-of-service via excessive AWS API usage by an operator who already
  controls the server's configuration.
