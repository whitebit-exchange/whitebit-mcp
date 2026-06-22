---
name: whitebit-algo-orders
description: >
  Executes OCO (one-cancels-other) orders and agent-orchestrated TWAP strategies on WhiteBit.
  Use when managing complex entry/exit logic or splitting large orders to reduce market impact.
  Use when the user says "OCO", "one-cancels-other", "TWAP", "split my order",
  "reduce market impact", "take-profit and stop-loss together", or "execute over time".
disable-model-invocation: true
metadata:
  type: task
---

# WhiteBit Algo Orders

Execute OCO orders and TWAP strategies on WhiteBit.

## When This Skill Activates

- User wants a combined take-profit + stop-loss on a futures position
- User wants to buy or sell a large quantity over time without moving the market
- User needs an OCO checked, created, or cancelled

## Tools

| Tool | Purpose |
|------|---------|
| `collateral__create_oco_order` | Native OCO on collateral/futures market |
| `collateral__cancel_oco_order` | Cancel an active OCO |
| `account_trade__get_oco_orders` | List active OCO orders |
| `account_collateral__get_open_positions` | Confirm position size before OCO |
| `spot__create_limit_order` | TWAP child orders |
| `spot__cancel_order` | Cancel unfilled TWAP slices |
| `account_trade__get_order` | Check fill status of TWAP slice |
| `tickers__get_single_market_activity` | Mid-price for TWAP slice pricing |

## Instructions

---

### OCO (One-Cancels-Other)

**When to use:** Protect an open futures position with simultaneous TP and SL. When one leg fills, the other cancels automatically.

#### Step 1 — Verify position

`account_collateral__get_open_positions` → confirm position exists and get exact size.

#### Step 2 — Check existing OCO

`account_trade__get_oco_orders` → warn if OCO already active for this market.

#### Step 3 — Determine side

| Position | OCO side |
|----------|---------|
| Long (bought) | `"sell"` |
| Short (sold) | `"buy"` |

#### Step 4 — Show summary and confirm

```
OCO order:
  Pair:            ETH_USDT
  Side:            sell
  Quantity:        1.5 ETH
  Take-profit:     $3,600 (limit)
  Stop trigger:    $3,000
  Stop fill price: $2,980

Confirm? (yes / no)
```

Note: `stop_limit_price` must be slightly worse than `activation_price` to ensure fill
(for sell-stop: activation $3,000, fill $2,980).

#### Step 5 — Execute

```
collateral__create_oco_order →
  market: "ETH_USDT"
  side: "sell"
  amount: "1.5"
  price: "3600"
  activation_price: "3000"
  stop_limit_price: "2980"
  confirmed: true
```

Return: OCO order ID, both leg prices.

---

### TWAP (Time-Weighted Average Price)

**When to use:** Buy or sell a large quantity over a time window to minimize market impact.
WhiteBit has no native TWAP — this skill orchestrates sequential limit orders.

#### Step 1 — Confirm plan

| Parameter | Default |
|-----------|---------|
| `pair` | required |
| `side` | required |
| `total_qty` | required |
| `duration_minutes` | required |
| `slices` | auto: duration / 15, min 3 |

Show plan and confirm once. Slices execute automatically after approval.

```
TWAP plan:
  Buy 5 BTC_USDT over 120 min
  8 slices × 0.625 BTC every 15 min
  Price: mid ± 0.1% per slice

Confirm to start? (yes / no)
```

#### Step 2 — Execute slice loop

For each slice:
1. `tickers__get_single_market_activity` → get current `last_price`
2. Set limit price: buy = `last_price × 1.001`, sell = `last_price × 0.999`
3. `spot__create_limit_order` → amount: slice_qty, price: limit_price, confirmed: true
4. Check fill every 2 min via `account_trade__get_order`
5. If not filled within slice interval: cancel via `spot__cancel_order`, replace at new mid-price
6. On fill: record, wait remainder of interval, proceed to next slice

#### Step 3 — Slice report

```
TWAP 3/8 — BTC_USDT buy
  Slice filled:    0.625 BTC at $67,182
  Total filled:    1.875 BTC
  Avg price so far: $67,215
  Remaining:       3.125 BTC
  ETA:             ~75 min
```

#### Step 4 — Completion report

```
TWAP complete — 5 BTC_USDT bought
  Avg execution: $67,198
  Start price:   $67,050
  Slippage:      +0.22%
  Duration:      118 min
```

### Handle errors

| Error | Action |
|-------|--------|
| Slice not filled in interval | Cancel and replace at fresh mid-price |
| Balance runs out mid-TWAP | Pause, notify user, wait for top-up |
| Position size mismatch on OCO | Re-fetch positions, use exact size from API |

## Composability

Calls: `whitebit-market-data` (mid-price for TWAP slices), `whitebit-order-execution` (child orders).
Called by: user directly for large orders or position protection.

## Definition of Done

**OCO:**
- [ ] Position existence confirmed before creating OCO
- [ ] Existing OCO checked to avoid duplicates
- [ ] `stop_limit_price` set worse than `activation_price`
- [ ] Summary shown and confirmed before execution
- [ ] OCO order ID returned

**TWAP:**
- [ ] Slice count and interval shown in plan before start
- [ ] Confirmed once — slices run automatically after
- [ ] Each slice checked for fill, replaced if stale
- [ ] Slice report after every fill
- [ ] Final slippage report on completion
