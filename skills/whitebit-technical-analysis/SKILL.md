---
name: whitebit-technical-analysis
description: >
  Computes technical indicators (RSI, MACD, Bollinger Bands, EMA) from WhiteBit OHLCV data
  and produces a scored market signal report.
  Use when the user wants a technical view before entering or exiting a trade.
  Use when the user says "analyze", "technical analysis", "RSI", "MACD", "is X a good buy",
  "chart analysis", "indicators", "support and resistance", or "signal for".
metadata:
  type: task
---

# WhiteBit Technical Analysis

Compute indicators from WhiteBit candle data and score market conditions 0–100.

## When This Skill Activates

- User asks for a technical analysis of any pair
- User asks whether a coin is a good buy or sell
- User asks for specific indicators (RSI, MACD, Bollinger Bands, EMA)
- `whitebit-dca-bot` needs a signal to decide whether to start accumulating

## Tools

| Tool | Purpose |
|------|---------|
| `kline__get_kline` | Fetch OHLCV candles for computation |
| `tickers__get_single_market_activity` | Current price context |

All indicator math runs in Claude's context — no external API needed.

## Instructions

### Step 1 — Fetch candles

```
kline__get_kline → market: "ETH_USDT", interval: "4h", limit: 200
```

Default timeframe: `4h` for swing trades, `1d` for position trades, `15m` for intraday.
Minimum 50 candles required. If fewer returned, report error and stop.

### Step 2 — Compute indicators

Use these standard formulas on the returned OHLCV data:

| Indicator | Formula | Signal |
|-----------|---------|--------|
| **RSI(14)** | 14-period relative strength | < 30 oversold, > 70 overbought |
| **EMA(20)** | 20-period exponential MA | Trend direction |
| **EMA(50)** | 50-period exponential MA | Trend direction |
| **MACD(12,26,9)** | EMA12 − EMA26, signal = EMA9 of MACD | Histogram direction |
| **BB(20,2)** | SMA20 ± 2×stddev | Price position in band |
| **ATR(14)** | 14-period average true range | Volatility, SL sizing |

### Step 3 — Score 0–100

Add/subtract points based on signals:

| Condition | Points |
|-----------|--------|
| RSI < 30 (oversold) | +15 |
| RSI > 70 (overbought) | −15 |
| EMA20 > EMA50 (uptrend) | +10 |
| EMA20 < EMA50 (downtrend) | −10 |
| MACD histogram positive and rising | +10 |
| MACD histogram negative and falling | −10 |
| Price above BB middle | +5 |
| Price below BB middle | −5 |
| Price near BB lower band (within 1%) | +10 |
| Price near BB upper band (within 1%) | −10 |
| Volume last candle > 1.5× 20-period avg | +5 |

Start at 50 (neutral). Clamp final score to 0–100.

### Step 4 — Interpret score

| Score | Label |
|-------|-------|
| 70–100 | Strong bullish |
| 55–69 | Moderately bullish |
| 45–54 | Neutral |
| 30–44 | Moderately bearish |
| 0–29 | Strong bearish |

### Step 5 — Report

Always include: timeframe, score, signal label, indicator values, 2–3 bullet reasons, ATR-based entry/SL levels.

```
ETH_USDT · 4H Technical Analysis
Score: 68/100 — Moderately bullish

Indicators
  RSI(14):  52.3 — neutral
  EMA trend: 20 > 50 — bullish (+10)
  MACD:     histogram +12.4, rising — bullish (+10)
  BB:       price at middle band — neutral
  ATR(14):  $84

Key levels
  Entry zone: $3,180–$3,220
  Stop loss:  $3,074 (1.5× ATR below entry)
  Take profit: $3,388 (2× ATR above entry)
```

### Step 6 — Handle errors

| Error | Action |
|-------|--------|
| Fewer than 50 candles | "Insufficient data for {timeframe} — try a shorter timeframe" |
| Invalid interval | List valid intervals, ask user to choose |
| Flat price (no volatility) | Note ATR near zero, skip BB scoring |

## Composability

Calls: `whitebit-market-data` (candles via `kline__get_kline`).
Called by: `whitebit-dca-bot` (signal gate before starting accumulation).

## Definition of Done

- [ ] Timeframe stated prominently in report header
- [ ] All 6 indicators computed and shown with values
- [ ] Score calculated and clamped 0–100
- [ ] Signal label matches score range
- [ ] ATR-based entry and SL levels included
- [ ] Minimum 50 candles confirmed before computing
