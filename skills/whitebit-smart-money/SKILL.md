---
name: whitebit-smart-money
description: >
  Detects large orders and volume anomalies in WhiteBit markets using public order book
  and candle data, and produces a consensus directional signal.
  Use when looking for institutional activity before a trade decision.
  Use when the user says "whale activity", "large orders", "smart money", "unusual volume",
  "big players", "is anyone accumulating", or "order book walls".
metadata:
  type: task
---

# WhiteBit Smart Money Tracker

Detect large-player activity using public WhiteBit market data.

## When This Skill Activates

- User asks about whale or institutional activity on a pair
- User wants to know if large orders are sitting in the order book
- User asks about abnormal volume before entering a trade
- User asks about bid/ask walls or hidden support/resistance

## Tools

| Tool | Purpose |
|------|---------|
| `depth__get_order_book` | Order book up to 100 levels |
| `kline__get_kline` | Volume history for spike detection |
| `tickers__get_single_market_activity` | Current price and 24h volume context |

No auth required. All data is public.

## Instructions

### Step 1 — Fetch data

Run in parallel:
1. `depth__get_order_book` → market: `"BTC_USDT"`, limit: `100`
2. `kline__get_kline` → market: `"BTC_USDT"`, interval: `"1h"`, limit: `48`
3. `tickers__get_single_market_activity` → market: `"BTC_USDT"`

### Step 2 — Detect large orders

For every level in the order book, compute `order_usdt = price × quantity`.
Flag any single order where `order_usdt > threshold` (default $50,000).

Separately, compute average order size per side:
`avg_bid_size = sum(bid quantities) / bid count`

Flag any order > 3× avg for its side as a **wall** (potential support/resistance or spoofing).

### Step 3 — Detect volume spike

From the 48 hourly candles:
- Compute rolling 24-period average volume
- Compare latest closed candle volume to that average
- Ratio = `current_volume / rolling_avg`

| Ratio | Label |
|-------|-------|
| < 1.5× | Normal |
| 1.5–2× | Elevated |
| 2–3× | Spike |
| > 3× | Anomaly |

### Step 4 — Assess direction

Look at which side dominates in the order book (total bid USDT vs total ask USDT in top 20 levels).
Combine with volume direction: if a volume spike occurs and bids dominate → buy-side pressure.

### Step 5 — Consensus signal

Require at least 2 corroborating signals before any directional label:

| Evidence combo | Signal |
|---------------|--------|
| Large bids + buy-side volume spike | `bullish accumulation` |
| Large asks + sell-side volume spike | `bearish distribution` |
| Mixed or single signal only | `neutral / inconclusive` |

Never label a direction from one signal alone.

### Step 6 — Report

```
BTC_USDT Smart Money Scan

Order book
  · Large bid at $66,800: 12.4 BTC ($830K) — potential support
  · Bid wall at $66,500: 8.1 BTC ($540K) — 4.2× avg bid size
  · No large asks detected

Volume (1H)
  · Current: 847 BTC — 2.8× above 24H rolling avg (anomaly)
  · Bid side dominates: 68% of book depth

Consensus: bullish accumulation (2/2 signals)
Confidence: high
```

### Step 7 — Limitations

WhiteBit does not expose a trader leaderboard. If user asks about "top traders" or "copy trading", state this and offer order book + volume analysis as the available alternative.

### Step 8 — Handle errors

| Error | Action |
|-------|--------|
| Empty order book | "No order book data available for this pair" |
| Fewer than 24 candles | Use available candles, note reduced reliability |
| Threshold ambiguous | Default $50K, state it explicitly in report |

## Composability

Calls: `whitebit-market-data` (order book + candles).
Used by: user before entering large positions.

## Definition of Done

- [ ] Order book fetched with limit ≥ 100
- [ ] Large orders flagged by USDT value (threshold stated)
- [ ] Walls flagged (order > 3× avg for that side)
- [ ] Volume spike ratio computed against 24-period rolling average
- [ ] Consensus requires 2+ corroborating signals
- [ ] Leaderboard limitation stated if user asks about copy trading
