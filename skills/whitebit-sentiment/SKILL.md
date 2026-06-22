---
name: whitebit-sentiment
description: >
  Fetches crypto news from CryptoPanic and scores market sentiment per coin traded on WhiteBit.
  Use when a price move needs explaining or when news context is needed before a trade.
  Use when the user says "any news on", "why is X moving", "market sentiment", "is there FUD",
  "what happened to", "recent events for", or "news about".
metadata:
  type: task
---

# WhiteBit Sentiment & News

Aggregate news and score sentiment for WhiteBit-traded assets.

## When This Skill Activates

- User asks about recent news for a coin
- A price move > 3% in 30 min occurs and explanation is needed
- User asks about general market mood
- User wants to know if there is FUD or hype around an asset

## Tools

| Tool | Purpose |
|------|---------|
| `kline__get_kline` | Confirm price move before news fetch |
| `tickers__get_single_market_activity` | Current price context |

External: CryptoPanic public API (`https://cryptopanic.com/api/free/v1/posts/`)

WhiteBit API provides no news or sentiment data. CryptoPanic is the primary source.

## First-Run Configuration

This skill requires a CryptoPanic API token for full functionality.

**Check on first use:**
1. Look for `CRYPTOPANIC_TOKEN` in environment or Claude Code settings.
2. If not set, ask the user once:
   > "To fetch crypto news, I need a CryptoPanic API token. Get one free at https://cryptopanic.com/developers/api/ — paste it here and I'll save it for this session."
3. Store the token for the session. If the user declines, fall back to the public RSS feed (Step 3 fallback path) and note reduced data quality.

Do not ask again after the first response. If the user skips, proceed with RSS fallback silently.

## Instructions

### Step 1 — Confirm price context (if triggered by a move)

`kline__get_kline` → market: `"BTC_USDT"`, interval: `"15m"`, limit: `8`
Quantify the move: "BTC down 3.2% in last 2 hours." Include this in the report.

### Step 2 — Map market to ticker

Strip `_USDT` from WhiteBit market name: `BTC_USDT` → `BTC`, `ETH_USDT` → `ETH`.

### Step 3 — Fetch news

```
GET https://cryptopanic.com/api/free/v1/posts/
  ?auth_token=<token>
  &currencies=BTC
  &kind=news
  &filter=hot
```

If no API token: use RSS feed `https://cryptopanic.com/news/<TICKER>/rss/`.
Fetch last 6 hours. Parse: `title`, `source`, `published_at`, `votes.positive`, `votes.negative`.

### Step 4 — Score sentiment

Classify each article:

| Keywords present | Label |
|-----------------|-------|
| partnership, launch, ETF, inflow, upgrade, adoption, bullish | positive |
| hack, exploit, ban, lawsuit, outflow, crash, FUD, bearish, SEC | negative |
| analysis, report, update (no strong keywords) | neutral |

`sentiment_score = (positive_count − negative_count) / total_articles`
Range: −1.0 (all negative) to +1.0 (all positive).

| Score | Label |
|-------|-------|
| > +0.5 | Strongly positive |
| +0.2 to +0.5 | Positive |
| −0.2 to +0.2 | Neutral |
| −0.5 to −0.2 | Negative |
| < −0.5 | Strongly negative |

### Step 5 — Report

```
BTC_USDT · −3.2% in 2H

Sentiment: −0.61 (strongly negative) · 14 articles, 11 negative

Top stories
· "SEC files new lawsuit against crypto exchange" — CoinDesk · negative
· "BTC ETF sees $400M outflow" — Bloomberg · negative
· "Mt.Gox creditors begin selling" — Reuters · negative

Chart: volume 2.1× above 24H average, sell-side dominant
```

Always show: article count, newest article timestamp, top 3 articles with source and label.
Never recommend buy or sell based on sentiment alone — pair with price data.

### Step 6 — Handle errors

| Error | Action |
|-------|--------|
| CryptoPanic API unavailable | Fall back to price/volume pattern only, state: "News API unavailable — showing chart analysis only" |
| No API token configured | Use RSS feed; note limitations |
| Fewer than 5 articles | Report low sample size: "Only {n} articles found — low confidence" |
| Coin not on CryptoPanic | State: "No news feed available for this asset" |

## Composability

Calls: `whitebit-market-data` (price context via `kline__get_kline`).
Used by: user before major trade decisions; triggered automatically on large unexpected price moves.

## Definition of Done

- [ ] Price context fetched and included (move size stated)
- [ ] Coin ticker mapped correctly (strip `_USDT`)
- [ ] Sentiment score computed from article keywords
- [ ] Score label applied per scale
- [ ] Top 3 articles shown with source and label
- [ ] Article count and newest timestamp included
- [ ] API unavailability handled gracefully with fallback
