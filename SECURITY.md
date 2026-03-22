# Security

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for security vulnerabilities.

Report them privately via [GitHub Security Advisories](https://github.com/whitebit-exchange/whitebit-mcp/security/advisories/new).
Include a description of the issue, steps to reproduce, and potential impact.
We will respond within 5 business days.

---

## Credential Model

API keys are passed as parameters in each individual tool call. The server:

- Uses them only to sign the outgoing WhiteBIT API request for that call
- Does not store, log, cache, or persist them in any form
- Does not write them to disk or transmit them to any party other than the WhiteBIT API

Keys exist in memory only for the duration of a single HTTP request.

---

## Recommendations

**Use minimal-permission API keys.** WhiteBIT lets you restrict each key to specific
operations. Examples:

| Use case | Permissions needed |
|---|---|
| Market data only | Any non-empty string (public endpoints do not validate keys) |
| Balance and order queries | Read balance, Read orders |
| Spot order placement | Read balance, Spot trading |
| Full access | All permissions |

**Keep keys out of your repository.** Do not commit API keys to `.env`, `docker-compose.yml`,
or any configuration file. Pass them in conversation when using an AI client.

**Use sub-accounts for automated strategies.** Create a dedicated sub-account with scoped API
keys rather than using your main account keys.
