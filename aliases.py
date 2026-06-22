"""Canonical tool-name aliases for WhiteBit MCP skills.

Skills (see the `whitebit-mcp-skills` submodule) reference tools by canonical
names like ``spot__create_limit_order``. This server auto-generates tool names
as ``{subclient}__{method}`` from the Python SDK (e.g.
``spot_trading__create_limit_order``), which do NOT match the canonical names.

This map bridges the gap: ``canonical name -> (SDK subclient attr, SDK method)``.
At startup the server registers each mapped tool under its canonical name using
the same machinery as the auto-generated tools, so skills can call them.

A value of ``None`` means the Python SDK currently has no equivalent method; the
alias is skipped at registration (and any skill calling it will not work on this
server until the gap is resolved). These are flagged below.
"""

# canonical name (used by skills) -> (SUBCLIENT_CLASSES key, SDK method name) | None
ALIASES: dict[str, tuple[str, str] | None] = {
    # --- Spot trading ---------------------------------------------------------
    "spot__create_limit_order": ("spot_trading", "create_limit_order"),
    "spot__create_market_order": ("spot_trading", "create_market_order"),
    "spot__create_stock_market_order": ("spot_trading", "create_stock_market_order"),
    "spot__create_stop_limit_order": ("spot_trading", "create_stop_limit_order"),
    "spot__cancel_order": ("spot_trading", "cancel_order"),
    "spot__cancel_all_orders": ("spot_trading", "cancel_all_orders"),
    "spot__modify_order": ("spot_trading", "modify_order"),
    "spot__create_bulk_order": ("spot_trading", "create_bulk_limit_order"),

    # --- Spot account queries -------------------------------------------------
    "account_trade__get_balance": ("spot_trading", "trade_account_balance"),
    "account_trade__get_orders": ("spot_trading", "get_active_orders"),
    "account_trade__get_history": ("spot_trading", "get_order_history"),
    "account_trade__get_executed_history": ("spot_trading", "get_executed_order_history"),
    # account_trade__get_order and account_trade__get_oco_orders are registered
    # directly in server.py as handwritten tools (the Python SDK spot_trading client
    # exposes neither), calling /api/v4/trade-account/order and /api/v4/oco-orders —
    # mirrors the Go SDK / internal MCP.

    # --- Collateral / futures trading -----------------------------------------
    "collateral__create_limit_order": ("collateral_trading", "create_collateral_limit_order"),
    "collateral__create_market_order": ("collateral_trading", "create_collateral_market_order"),
    "collateral__create_oco_order": ("collateral_trading", "create_collateral_oco_order"),
    "collateral__cancel_oco_order": ("collateral_trading", "cancel_oco_order"),
    # FLAG: collateral_trading has no plain cancel_order (only cancel_conditional /
    # cancel_oco / cancel_oto). Regular collateral orders are cancelled via the
    # shared spot endpoint — verify this is correct.
    "collateral__cancel_order": ("spot_trading", "cancel_order"),

    # --- Collateral account queries -------------------------------------------
    "account_collateral__get_balance": ("collateral_trading", "collateral_account_balance"),
    "account_collateral__get_summary_balance": ("collateral_trading", "collateral_account_balance_summary"),
    "account_collateral__get_open_positions": ("collateral_trading", "get_open_positions"),
    "account_collateral__get_positions_history": ("collateral_trading", "get_positions_history"),

    # --- Earn / flexible lending ----------------------------------------------
    "lending__flex_invest": ("crypto_lending_flex", "create_flex_investment"),
    "lending__flex_withdraw": ("crypto_lending_flex", "withdraw_from_flex_investment"),
    "lending__flex_close": ("crypto_lending_flex", "close_flex_investment"),
    "lending__flex_set_auto_invest": ("crypto_lending_flex", "update_flex_auto_reinvestment"),
    "lending__get_flex_plans": ("crypto_lending_flex", "get_flex_plans"),
    "lending__get_flex_investments": ("crypto_lending_flex", "get_user_flex_investments"),
    # FLAG (minor): SDK splits history into investment vs payment history.
    # Mapped to investment history — confirm which the skill expects.
    "lending__get_flex_history": ("crypto_lending_flex", "get_flex_investment_history"),

    # --- Earn / fixed lending -------------------------------------------------
    "lending__create_fixed_investment": ("crypto_lending_fixed", "create_fixed_investment"),
    "lending__close_fixed_investment": ("crypto_lending_fixed", "close_fixed_investment"),
    "lending__get_fixed_plans": ("crypto_lending_fixed", "get_fixed_plans"),
    "lending__get_fixed_interest_history": ("crypto_lending_fixed", "get_interest_payment_history"),
    # FLAG (minor): SDK exposes only get_fixed_investments_history (no plain list).
    "lending__get_fixed_investments": ("crypto_lending_fixed", "get_fixed_investments_history"),

    # --- Main account ---------------------------------------------------------
    "main_account__get_balance": ("main_account", "get_main_balance"),

    # --- Public market data ---------------------------------------------------
    "market__get_markets": ("public_api_v4", "market_info"),
    "futures__get_markets": ("public_api_v4", "available_futures_markets_list"),
    "assets__get_assets": ("public_api_v4", "asset_status_list"),
    "depth__get_order_book": ("public_api_v4", "orderbook"),
    "deals__get_trade_history": ("public_api_v4", "recent_trades"),
    "tickers__get_tickers": ("public_api_v4", "market_activity"),
    "server__get_time": ("public_api_v4", "server_time"),
    "server__ping": ("public_api_v4", "server_status"),
    # kline__get_kline is registered directly in server.py as a handwritten tool
    # (the Python SDK public client has no REST candles/kline method), calling the
    # public /api/v1/public/kline endpoint — mirrors the Go SDK / internal MCP.
    # tickers__get_single_market_activity is registered directly in server.py as a
    # handwritten tool (the Python SDK only exposes all-markets activity), calling the
    # public /api/v1/public/ticker endpoint — mirrors the Go SDK / internal MCP.
}
