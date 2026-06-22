---
name: whitebit-dca-bot
description: >
  Runs a Dollar Cost Averaging strategy on WhiteBit — buys a fixed amount on a schedule
  or on price dips, tracks cycles, and reports average cost.
  Use when the user wants to accumulate an asset automatically over time.
  Use when the user says "DCA", "buy automatically", "accumulate", "buy every day",
  "buy on dips", "recurring buys", or "average in".
disable-model-invocation: true
metadata:
  type: workflow
---

# WhiteBit DCA Bot

Automate recurring buys on WhiteBit spot market.

## When This Skill Activates

- User wants to buy an asset on a fixed schedule (time-based DCA)
- User wants to buy on price dips (drop-based DCA)
- User asks for a DCA status update
- User wants to stop an active DCA

## Tools

Uses `whitebit-market-data`, `whitebit-portfolio`, and `whitebit-order-execution` skills.

Direct tools:
| Tool | Purpose |
|------|---------|
| `tickers__get_single_market_activity` | Price check before each cycle |
| `account_trade__get_balance` | Balance check before each cycle |
| `spot__create_market_order` | Time-based cycle execution |
| `spot__create_limit_order` | Drop-based cycle execution (limit at target price) |
| `spot__cancel_order` | Cancel pending limit orders on stop |
| `account_trade__get_order` | Check if limit order filled |

## Instructions

### Phase 1 — Setup

Confirm these parameters with the user before starting:

| Parameter | Default | Notes |
|-----------|---------|-------|
| `pair` | — | e.g. `BTC_USDT` |
| `amount_per_cycle` | — | USDT per buy |
| `trigger` | `time` | `time` or `drop` |
| `interval_hours` | 24 | For time-based |
| `drop_pct` | 3% | For drop-based |
| `total_cycles` | — | Stop after N cycles |
| `take_profit_pct` | optional | Close all at N% profit on avg cost |

Show confirmation summary:
```
DCA Plan:
  Pair:    ETH_USDT
  Buy:     $100 USDT every 24h
  Cycles:  7
  Total:   $700 USDT
  TP:      none

Confirm to start? (yes / no)
```

### Phase 2 — Execution loop

**Time-based cycle:**
1. `account_trade__get_balance` → confirm ≥ `amount_per_cycle` USDT available
2. `spot__create_market_order` → side: `"buy"`, amount: `"100"` (USDT), confirmed: true
3. Record fill price and quantity
4. Update state: `cycles_done`, `total_invested`, `avg_buy_price`
5. Report cycle result (see Step 4)
6. Wait `interval_hours` before next cycle

**Drop-based cycle:**
1. `tickers__get_single_market_activity` → get current price as `reference_price` (set once at start)
2. Place limit order at `reference_price × (1 − drop_pct / 100)`
3. Convert USDT amount to base qty: `qty = amount_per_cycle / limit_price`
4. `spot__create_limit_order` → amount: qty, price: limit_price, confirmed: true
5. Check fill every 5 min via `account_trade__get_order`
6. On fill: update state, update `reference_price` to fill price, proceed to next level

### Phase 3 — State tracking

Maintain per session:
```
reference_price:   67000
cycles_done:       3
total_invested:    300 USDT
total_qty:         0.00447 BTC
avg_buy_price:     67113
open_order_ids:    [...]
```

`avg_buy_price` formula: `(prev_avg × prev_qty + fill_price × fill_qty) / (prev_qty + fill_qty)`

### Phase 4 — Cycle report

After each fill:
```
DCA cycle 3/7 complete
  Bought:        0.00149 ETH at $3,218
  Total invested: $300 USDT
  Avg cost:       $3,195
  Current price:  $3,240 (+1.4% above avg)
  Next cycle:     in 24h
```

### Phase 5 — Stop conditions

Stop when:
- All cycles complete
- User says "stop DCA"
- Balance < `amount_per_cycle` (pause and notify)
- TP hit: `current_price ≥ avg_buy_price × (1 + take_profit_pct / 100)`

On stop: cancel all open limit orders via `spot__cancel_order`. Report final summary.

### Step 6 — Handle errors

| Error | Action |
|-------|--------|
| Insufficient balance | Pause bot, notify user, wait for top-up |
| Order not filled in 2× interval | Cancel and replace at new market price |
| Market unavailable | Pause bot, notify user |

## Composability

Calls: `whitebit-market-data` (price), `whitebit-portfolio` (balance), `whitebit-order-execution` (order placement).
Optional gate: `whitebit-technical-analysis` (only start DCA if score < 45 — oversold zone).

## Definition of Done

- [ ] Parameters confirmed with user before first order
- [ ] Balance checked before every cycle
- [ ] State tracked: cycles_done, total_invested, avg_buy_price
- [ ] Cycle report shown after each fill
- [ ] Stop: all open limit orders cancelled on exit
- [ ] Final summary shown on completion or stop
