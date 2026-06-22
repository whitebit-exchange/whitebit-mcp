# whitebit-mcp-skills

Single source of truth for WhiteBit MCP skills. Holds one `<skill-name>/SKILL.md`
directory per skill at the repo root, consumed by multiple MCP servers (Go and
Python) as a git submodule mounted at their `skills/` folder.

Skills are edited **here only**. Servers just pull this repo.

## Adding to a server

```bash
git submodule add <repo-url> skills
git submodule update --init
```

The server mounts this repo into its own `skills/` folder and registers each `SKILL.md`.
To update to the latest skills: `git submodule update --remote` and commit the pointer.

## Tool name contract

Skills reference tools by canonical names like `spot__create_limit_order`,
`account_trade__get_balance`, etc. These names follow the `domain__action` convention.

**Rule for servers:** every MCP server must expose its tools under these exact names.
- The **Go** server already registers tools under these names, no mapping needed.
- The **Python** server generates tool names from its SDK
  (`spot_trading__create_limit_order`, …), so it maps `canonical name -> (SDK subclient, method)`
  and registers each tool under the canonical name.

If a server does not expose a referenced name, any skill calling it will fail.
The skill is the source of truth for names.

### Available names

**Spot — trading**
`spot__create_limit_order`, `spot__create_market_order`, `spot__create_stock_market_order`,
`spot__create_stop_limit_order`, `spot__cancel_order`, `spot__cancel_all_orders`,
`spot__modify_order`, `spot__create_bulk_order`

**Spot — queries**
`account_trade__get_balance`, `account_trade__get_order`, `account_trade__get_orders`,
`account_trade__get_history`, `account_trade__get_executed_history`, `account_trade__get_oco_orders`

**Collateral / futures**
`collateral__create_limit_order`, `collateral__create_market_order`, `collateral__create_oco_order`,
`collateral__cancel_order`, `collateral__cancel_oco_order`, `account_collateral__get_balance`,
`account_collateral__get_summary_balance`, `account_collateral__get_open_positions`,
`account_collateral__get_positions_history`

**Earn (lending)**
`lending__flex_invest`, `lending__flex_withdraw`, `lending__flex_close`,
`lending__flex_set_auto_invest`, `lending__get_flex_plans`, `lending__get_flex_investments`,
`lending__get_flex_history`, `lending__create_fixed_investment`, `lending__close_fixed_investment`,
`lending__get_fixed_plans`, `lending__get_fixed_investments`, `lending__get_fixed_interest_history`

**Account / Public / System**
`main_account__get_balance`, `market__get_markets`, `futures__get_markets`, `assets__get_assets`,
`depth__get_order_book`, `kline__get_kline`, `deals__get_trade_history`, `tickers__get_tickers`,
`tickers__get_single_market_activity`, `server__get_time`, `server__ping`

## Skills

| Skill | Purpose |
|-------|---------|
| `whitebit-order-execution` | Place, modify, cancel orders (spot/collateral) |
| `whitebit-market-data` | Prices, order book, candles, tickers |
| `whitebit-portfolio` | Balances and positions |
| `whitebit-trade-review` | Trade history and PnL analysis |
| `whitebit-technical-analysis` | Technical analysis |
| `whitebit-algo-orders` | Algorithmic orders |
| `whitebit-dca-bot` | DCA strategy |
| `whitebit-earn` | Earn / lending |
| `whitebit-smart-money` | Smart-money analytics |
| `whitebit-sentiment` | Sentiment analysis |
| `whitebit-healthcheck` | Availability check |
| `whitebit-user-support` | WhiteBit user support |
