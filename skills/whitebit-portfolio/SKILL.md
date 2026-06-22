---
name: whitebit-portfolio
description: >
  Reads account balances, open orders, positions, and trade history from WhiteBit MCP.
  Use before any trade decision or when reporting current account state.
  Use when the user says "my balance", "what do I have", "show my portfolio",
  "open orders", "my positions", "P&L", "trade history", or "how much USDT do I have".
metadata:
  type: task
---

# WhiteBit Portfolio

Read current account state from WhiteBit. All tools are read-only.

## When This Skill Activates

- User asks about balance, holdings, or available funds
- User asks about open orders or current positions
- User asks for P&L or trade history
- Any other skill needs pre-trade state (balance, open positions)

## Tools

| Tool | Purpose |
|------|---------|
| `account_trade__get_balance` | Spot wallet balances per asset |
| `main_account__get_balance` | Main (deposit) account balance |
| `account_trade__get_orders` | Open orders for a market |
| `account_trade__get_history` | Order history |
| `account_trade__get_executed_history` | Filled deal history |
| `account_collateral__get_balance` | Futures wallet balance |
| `account_collateral__get_open_positions` | Current open futures positions |
| `account_collateral__get_summary_balance` | Collateral account summary |
| `deals__get_trade_history` | Full trade history (one row per fill) |

## Instructions

### Step 1 — Choose the right scope

```
User asks "my balance"?          → account_trade__get_balance
User asks about specific asset?  → account_trade__get_balance (ticker: "BTC")
User asks about futures balance?  → account_collateral__get_balance
User asks about open orders?     → account_trade__get_orders (per market)
User asks about open positions?  → account_collateral__get_open_positions
User asks for trade history?     → account_trade__get_executed_history
User asks for full portfolio?    → steps 2–4 below
```

### Step 2 — Full portfolio snapshot

When user says "show my portfolio" with no filter:
1. `account_trade__get_balance` — all spot balances (skip assets with `available = 0` and `freeze = 0`)
2. `account_collateral__get_open_positions` — futures positions + `unrealized_pnl`
3. `account_trade__get_orders` — open orders for each active market

Report non-zero balances, open positions with unrealized P&L, and open order count.

### Step 3 — Balance fields

`available` = free to trade.
`freeze` = locked in open orders.
Always show both. Never conflate them.

### Step 4 — Paginated history

`account_trade__get_executed_history` and `deals__get_trade_history` use `limit`/`offset`.
Default `limit=50`. Fetch multiple pages if user asks for "all" trades or a long date range.

### Step 5 — Handle errors

| Error | Action |
|-------|--------|
| Empty balance response | Report "no assets found in spot wallet" |
| No open orders | Report count as 0, not an error |
| History empty for date range | State "no trades in this period" |

## Composability

Called by: `whitebit-order-execution` (balance check), `whitebit-trade-review` (raw history), `whitebit-dca-bot` (cycle balance check), `whitebit-earn` (idle balance detection).

## Definition of Done

- [ ] Correct tool selected for the query scope
- [ ] `available` and `freeze` reported separately
- [ ] Unrealized P&L included for futures positions
- [ ] Paginated history fetches all pages when "all" requested
- [ ] Zero-balance assets filtered from full snapshot
