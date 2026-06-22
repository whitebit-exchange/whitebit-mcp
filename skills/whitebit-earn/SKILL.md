---
name: whitebit-earn
description: >
  Deposits assets into WhiteBit lending products, compares APY rates, and manages earn positions via MCP tools.
  Use when the user wants to put idle funds to work or optimize yield on uninvested balance.
  Use when the user says "earn", "savings", "lending", "APY", "stake", "best yield",
  "put USDT to work", "flex invest", or "fixed term".
disable-model-invocation: true
metadata:
  type: task
---

# WhiteBit Earn

Manage flexible and fixed lending products on WhiteBit.

## When This Skill Activates

- User asks about savings, staking, or earning yield on idle assets
- User wants to deposit into flex or fixed lending
- User wants to check current APY rates
- Agent detects a large idle balance after a trade exits

## Tools

| Tool | Purpose |
|------|---------|
| `lending__get_flex_plans` | List flexible lending products with APY |
| `lending__get_fixed_plans` | List fixed-term lending products with APY |
| `lending__flex_invest` | Deposit into a flex plan |
| `lending__flex_withdraw` | Withdraw from a flex plan |
| `lending__flex_close` | Close a flex position |
| `lending__flex_set_auto_invest` | Toggle automatic yield reinvestment |
| `lending__get_flex_investments` | Current flex positions |
| `lending__get_flex_history` | Flex interest history |
| `lending__create_fixed_investment` | Deposit into a fixed-term plan |
| `lending__close_fixed_investment` | Early-close a fixed position |
| `lending__get_fixed_investments` | Current fixed positions |
| `lending__get_fixed_interest_history` | Fixed interest history |

## Instructions

### Step 1 — List before investing

Always call `lending__get_flex_plans` or `lending__get_fixed_plans` first.
Filter by `ticker` (e.g. `"USDT"`) and sort by APY descending.
Never invest without showing the user rates first.

### Step 2 — Check existing positions

Call `lending__get_flex_investments` and `lending__get_fixed_investments`.
Show current positions before recommending new ones. Avoid duplicate investments.

### Step 3 — Check balance

Call `account_trade__get_balance` (via `whitebit-portfolio`).
Keep a 10% buffer — never invest 100% of available balance.
State the buffer explicitly: "Investing $450 of your $500 available USDT (keeping $50 liquid)."

### Step 4 — Show summary and wait for confirmation

```
Earn summary:
  Product:       Flex USDT
  APY:           6.2%
  Amount:        $450 USDT
  Daily yield:   ~$0.077
  Monthly yield: ~$2.30
  Auto-reinvest: enabled

Confirm? (yes / no)
```

Do not set `confirmed: true` until the user explicitly approves.

### Step 5 — Execute

```
lending__flex_invest →
  plan_id: "<id from get_flex_plans>"
  amount: "450"
  confirmed: true
```

Return: `investment_id`, APY, projected daily yield.

### Step 6 — Decision tree

```
"Best APY for USDT?"      → get_flex_plans + get_fixed_plans (ticker: "USDT"), sort by APY
"Invest in flex"          → flex_invest (confirmed)
"Invest in fixed"         → create_fixed_investment (confirmed)
"My earn positions"       → get_flex_investments + get_fixed_investments
"Withdraw flex"           → flex_withdraw
"Enable auto-reinvest"    → flex_set_auto_invest
"Close fixed early"       → warn about forfeited interest → close_fixed_investment on confirm
```

### Step 7 — Handle errors

| Error | Action |
|-------|--------|
| Amount < min_deposit | Report minimum and ask user to adjust |
| plan_id unknown | Re-fetch plans, use ID from response |
| Early fixed close | Warn: "Closing before maturity forfeits accrued interest. Confirm?" |

## Composability

Calls: `whitebit-portfolio` (balance check).
Called by: agent when idle balance > $100 detected after order exit.

## Definition of Done

- [ ] Plans listed with APY before any deposit
- [ ] Existing positions checked to avoid duplicates
- [ ] 10% balance buffer enforced and stated
- [ ] Summary shown before `confirmed: true`
- [ ] `investment_id` returned on success
- [ ] Early fixed-close warning shown before execution
