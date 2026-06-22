---
name: whitebit-order-execution
description: >
  Places, modifies, and cancels spot and collateral orders on WhiteBit via MCP tools.
  Use when executing a buy or sell decision on behalf of the user.
  Use when the user says "buy", "sell", "place an order", "cancel order", "modify order",
  "close position", "open a trade", or "execute".
disable-model-invocation: true
metadata:
  type: task
---

# WhiteBit Order Execution

Place and manage orders on WhiteBit spot and collateral markets.

## When This Skill Activates

- User says buy, sell, place, open, close, cancel, modify
- Agent reaches a trade signal and needs to execute
- DCA bot or algo-orders skill triggers a child order

## Tools

| Tool | Purpose |
|------|---------|
| `spot__create_limit_order` | Limit buy/sell on spot |
| `spot__create_market_order` | Market buy/sell on spot (amount in quote for buy) |
| `spot__create_stock_market_order` | Market buy with amount in quote currency |
| `spot__create_stop_limit_order` | Stop-limit trigger order |
| `spot__cancel_order` | Cancel one order by ID |
| `spot__cancel_all_orders` | Cancel all orders on a market |
| `spot__modify_order` | Change price or amount of open order |
| `spot__create_bulk_order` | Place multiple orders in one call |
| `collateral__create_limit_order` | Limit order on futures/collateral market |
| `collateral__create_market_order` | Market order on futures/collateral market |
| `collateral__create_oco_order` | OCO (take-profit + stop-loss) on collateral |
| `collateral__cancel_order` | Cancel collateral order |
| `account_trade__get_order` | Check order status |
| `account_trade__get_balance` | Pre-trade balance check |

## Instructions

### Step 1 — Check balance first

Call `account_trade__get_balance` with the quote asset (e.g. `ticker: "USDT"`).
If balance < required amount, stop and report the deficit. Never attempt an order that will fail.

### Step 2 — Show order summary and wait for confirmation

Present to user before executing:
```
Order summary:
  Pair:   BTC_USDT
  Side:   BUY
  Type:   limit
  Amount: 0.05 BTC
  Price:  $67,000
  Total:  ~$3,350 USDT

Confirm? (yes / no)
```
Do not set `confirmed: true` until the user explicitly approves.

### Step 3 — Select the right tool

```
Spot limit order?             → spot__create_limit_order
Spot market order (base qty)? → spot__create_market_order
Spot market buy (USDT spend)? → spot__create_stock_market_order
Stop trigger on spot?         → spot__create_stop_limit_order
Futures / collateral?         → collateral__create_limit_order / collateral__create_market_order
Both TP + SL on futures?      → collateral__create_oco_order
Cancel one order?             → spot__cancel_order
Cancel all on market?         → spot__cancel_all_orders
Modify open order?            → spot__modify_order
```

### Step 4 — Amount conventions

| Tool | `amount` field means |
|------|---------------------|
| `spot__create_limit_order` | Base currency (BTC quantity) |
| `spot__create_market_order` buy | Quote currency (USDT to spend) |
| `spot__create_market_order` sell | Base currency (BTC to sell) |
| `spot__create_stock_market_order` | Quote currency (USDT to spend) |

### Step 5 — Execute with `confirmed: true`

```
spot__create_limit_order →
  market: "BTC_USDT"
  side: "buy"
  amount: "0.05"
  price: "67000"
  confirmed: true
```

Return: `order_id`, `status`, confirmation message.

### Step 6 — Handle errors

| Error | Action |
|-------|--------|
| Insufficient balance | Report deficit, suggest reducing size |
| Invalid market | Call `market__get_markets`, find correct pair |
| Order already filled | Inform user, do not retry cancel |
| `confirmed` missing | Never execute — always require explicit approval first |

## Composability

Calls: `whitebit-market-data` (pre-trade price check), `whitebit-portfolio` (balance check).
Called by: `whitebit-dca-bot`, `whitebit-algo-orders`.

## Definition of Done

- [ ] Balance checked before order placement
- [ ] Order summary shown to user before execution
- [ ] User confirmed before `confirmed: true` sent
- [ ] Correct `amount` convention applied per tool
- [ ] `order_id` returned on success
- [ ] Error handled with clear message (no silent failures)
