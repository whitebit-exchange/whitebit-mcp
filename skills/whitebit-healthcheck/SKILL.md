---
name: whitebit-healthcheck
description: >
  Verifies that the WhiteBit MCP server is reachable and all tool categories respond correctly.
  Runs automatically before any trading skill if tools are unavailable.
  Use when the user says "is WhiteBit MCP running", "check connection", "ping WhiteBit",
  "are tools available", or when any WhiteBit MCP tool call fails unexpectedly.
metadata:
  type: task
---

# WhiteBit Healthcheck

Verify the WhiteBit MCP server is alive and tools are functional.

## When This Skill Activates

- Any WhiteBit MCP tool returns an unexpected error
- User asks if the MCP is running or available
- Before starting a long-running workflow (DCA bot, TWAP) to avoid mid-run failures
- Claude Code session starts and WhiteBit tools should be available

## Tools

| Tool | Category tested |
|------|----------------|
| `server__ping` | Server connectivity |
| `server__get_time` | Server clock sync |
| `market__get_markets` | Public API (no auth) |
| `account_trade__get_balance` | Authenticated API |

## Instructions

### Step 1 — Ping the server

Call `server__ping`.
- Success → proceed to Step 2.
- Failure (timeout / connection refused) → MCP server is down. Call `whitebit-setup` and stop.

> **Recursion guard**: If this healthcheck was already triggered by `whitebit-setup`, do NOT call `whitebit-setup` again — report the failure directly to the user instead. Max 1 level of recursion.

### Step 2 — Check server time

Call `server__get_time`.
Compare to local time. If diff > 30 seconds, warn:
"Server clock drift detected ({n}s). This may cause signature errors on authenticated calls."

### Step 3 — Test public API

Call `market__get_markets`.
- Success (list of markets returned) → public API is healthy.
- Failure → WhiteBit exchange API is unreachable. Report and stop — do not attempt trades.

### Step 4 — Test authenticated API

Call `account_trade__get_balance` with no ticker filter.
- Success → API keys are valid, auth is working.
- Error "invalid signature" or "unauthorized" → API keys are wrong or expired. Ask user to reconfigure via `whitebit-setup` Step 3.
- Error "permission denied" → API key lacks trading permission. Ask user to regenerate with correct permissions.

### Step 5 — Report

```
WhiteBit MCP Healthcheck

Server:       ✓ reachable
Clock drift:  +2s (OK)
Public API:   ✓ 312 markets available
Auth API:     ✓ credentials valid

Status: HEALTHY — all systems operational
```

Or if something fails:
```
WhiteBit MCP Healthcheck

Server:       ✗ not reachable (connection refused :8080)
Public API:   — skipped
Auth API:     — skipped

Status: DOWN — run whitebit-setup to start the server
```

### Step 6 — Auto-remediation

| Failure | Auto-action |
|---------|------------|
| Server not reachable | Call `whitebit-setup` |
| Auth error | Ask user for new API keys, update `.env` |
| Exchange API down | Wait 60s, retry once. If still down: "WhiteBit exchange is experiencing issues — check status.whitebit.com" |

## Composability

Calls: `whitebit-setup` (if server is down).
Called by: `whitebit-dca-bot` (pre-flight before loop starts), `whitebit-algo-orders` (before TWAP), any skill that fails unexpectedly.

## Definition of Done

- [ ] `server__ping` called first
- [ ] Server time drift checked
- [ ] Public API verified with `market__get_markets`
- [ ] Authenticated API verified with `account_trade__get_balance`
- [ ] Structured report produced (HEALTHY / DEGRADED / DOWN)
- [ ] Auto-remediation triggered when server is down
