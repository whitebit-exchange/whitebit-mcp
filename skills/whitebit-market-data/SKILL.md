---
name: whitebit-market-data
description: >
  Fetches live prices, order books, candles, and 24h stats from the WhiteBit MCP server.
  Use before any trade decision or when the user needs current market state.
  Use when the user says "price of", "what's BTC at", "show the chart", "order book for",
  "how much is", "24h stats", "available markets", or "what pairs does WhiteBit have".
metadata:
  type: task
---

# WhiteBit Market Data

Retrieve live market data via WhiteBit MCP tools. No API key required.

## When This Skill Activates

- User asks for the current price of any asset
- User wants to see an order book or bid/ask spread
- User asks for candlestick/OHLCV data or a chart
- User asks which markets or pairs are available on WhiteBit
- Any other skill needs current price before placing an order or computing indicators

## Tools

| Tool | Purpose |
|------|---------|
| `tickers__get_single_market_activity` | Price, bid/ask, 24h volume for one pair |
| `tickers__get_tickers` | All pairs at once |
| `depth__get_order_book` | Bids and asks up to 100 levels |
| `kline__get_kline` | OHLCV candles (1m → 1M intervals) |
| `market__get_markets` | All available spot pairs |
| `futures__get_markets` | All futures contracts |
| `assets__get_assets` | Supported deposit assets |

## Instructions

### Step 1 — Choose the right tool

```
User asks for price of one pair?  → tickers__get_single_market_activity
User asks for price of all pairs? → tickers__get_tickers
User asks for order book?         → depth__get_order_book
User asks for chart / candles?    → kline__get_kline
User asks what markets exist?     → market__get_markets
User asks about futures pairs?    → futures__get_markets
```

### Step 2 — Format the market parameter

Always use `BASE_QUOTE` with underscore, uppercase: `BTC_USDT`, `ETH_USDT`.
Never use `BTCUSDT`, `BTC/USDT`, or lowercase. If the user writes it wrong, fix silently.

If the pair is not found, call `market__get_markets` and pick the closest match.

### Step 3 — Call the tool

**Price query:**
```
tickers__get_single_market_activity → market: "BTC_USDT"
```
Report: `last_price`, `bid`, `ask`, spread (`ask − bid` in absolute + %), `volume`.

**Order book:**
```
depth__get_order_book → market: "BTC_USDT", limit: 20
```
Report top 5 levels by default. Show cumulative volume per side.

**Candles:**
```
kline__get_kline → market: "ETH_USDT", interval: "4h", limit: 100
```
Valid intervals: `1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M`.
Return numbers exactly as received — do not round prices.

### Step 4 — Handle errors

| Error | Action |
|-------|--------|
| Market not found | Call `market__get_markets`, find closest match, retry |
| Empty response | State "no data available for this pair" |
| Invalid interval | List valid intervals and ask user to pick |

## Composability

Called by: `whitebit-technical-analysis`, `whitebit-dca-bot`, `whitebit-smart-money`, `whitebit-order-execution` (pre-trade price check), `whitebit-sentiment` (price confirmation).

## Definition of Done

- [ ] Correct tool selected for the query type
- [ ] Market formatted as `BASE_QUOTE` (e.g. `BTC_USDT`)
- [ ] Numbers returned as-is (no rounding)
- [ ] Spread reported for price queries (absolute + %)
- [ ] Error handled if pair not found
