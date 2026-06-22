---
name: whitebit-trade-review
description: >
  Analyzes closed WhiteBit trades and computes win rate, net P&L, R:R ratio, fee drag,
  and behavioral patterns from trade history.
  Use when the user wants to understand their trading performance over a period.
  Use when the user says "review my trades", "win rate", "how did I do", "P&L this month",
  "my biggest losses", "trading performance", or "weekly report".
metadata:
  type: review
---

# WhiteBit Trade Review

Compute performance metrics from WhiteBit trade history.

## When This Skill Activates

- User asks for a performance review of their trading
- User wants win rate, R:R, or P&L for a period
- User wants to find their biggest mistakes or best trades
- Scheduled weekly or monthly report

## Tools

| Tool | Purpose |
|------|---------|
| `account_trade__get_executed_history` | Filled spot orders (paginated) |
| `deals__get_trade_history` | Granular fills — one row per execution |
| `account_trade__get_history` | Order-level history |
| `account_collateral__get_positions_history` | Closed futures positions + realized PnL |

## Instructions

### Step 1 — Establish scope

Ask if not provided: date range, specific pair filter (optional).
Convert relative dates to absolute: "this month" → `2026-05-01` to `2026-05-27`.

### Step 2 — Fetch all trades

Call `account_trade__get_executed_history` with `limit=50`. Paginate with `offset` until result count < limit.
Call `account_collateral__get_positions_history` for any closed futures positions in the same period.
Record total trade count before computing.

### Step 3 — Compute core metrics

| Metric | Formula |
|--------|---------|
| **Win rate** | winning closed trades / total closed trades × 100% |
| **Average win** | mean P&L of profitable trades (USDT) |
| **Average loss** | mean P&L of losing trades (USDT, positive number) |
| **R:R ratio** | average win / average loss |
| **Net P&L** | sum of all trade P&Ls (realized only) |
| **Fee drag** | total fees / gross P&L × 100% |
| **Profit factor** | gross profit / gross loss |

Count only closed trades in win rate. Exclude open orders.

### Step 4 — Group by pair

Compute win rate and net P&L per market pair. Sort by net P&L descending.
Surface the best pair (highest P&L) and worst pair (lowest P&L).

### Step 5 — Find behavioral patterns

Scan for:
- Losses concentrated in specific UTC hours
- Repeated losses on the same pair
- Overtrading days (days with > 2× the session's daily average trade count)
- Average loss size vs average win size (asymmetry flag if loss > 1.5× win)

### Step 6 — Report

```
May 2026 — 47 trades across 6 pairs

Win rate:     61.7%  (29W / 18L)
Net P&L:     +$820.90  (after $21.40 fees)
Fee drag:      2.5%
R:R ratio:     1.8
Profit factor: 2.3
Best pair:    BTC_USDT  +$540  (72% WR)
Worst pair:   DOGE_USDT −$184  (33% WR)

Patterns
· 72% of losses opened 02:00–05:00 UTC
· Average DOGE loss 2.3× larger than average DOGE win
· 6 overtrading days (>8 trades/day)
```

### Step 7 — Warnings

Emit warnings when:
- Fee drag > 30% of gross P&L → "High fee drag — consider larger sizes or lower frequency"
- R:R < 1.0 → "Average loss exceeds average win — adjust TP/SL ratios"
- Win rate < 40% → "Below breakeven for this R:R — review entry criteria"

### Step 8 — Handle errors

| Error | Action |
|-------|--------|
| No trades in period | "No closed trades found for this period." — do not fabricate data |
| Partial data (API limit) | State: "Showing {n} trades — full history may require additional pages" |

## Composability

Calls: `whitebit-portfolio` (raw history via `account_trade__get_executed_history`).

## Definition of Done

- [ ] Date range and trade count stated at top of report
- [ ] All 6 core metrics computed
- [ ] By-pair breakdown included
- [ ] Behavioral patterns checked
- [ ] Applicable warnings emitted
- [ ] No fabricated data — empty periods reported as empty
