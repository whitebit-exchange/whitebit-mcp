"""Loads WhiteBit MCP skills as model-invocable tools.

Mirrors the Go server (skills.go): each ``skills/<name>/SKILL.md`` is registered
as a tool named ``skill_<name>`` whose frontmatter ``description`` acts as the
activation trigger; the handler returns the skill text for the model to follow.

The ``skills/`` directory is expected next to this file. It will be a git
submodule once the shared skills repo exists; a plain copy works for local dev.
"""

import logging
import pathlib

_log = logging.getLogger("whitebit-mcp.skills")

SKILLS_DIR = pathlib.Path(__file__).parent / "skills"

# Sent to clients in the MCP initialize response. Clients that honor server
# instructions inject this into the model's context, so these rules and the
# skill routing travel with the server to every client — no per-client config.
SERVER_INSTRUCTIONS = """WhiteBit MCP agent instructions.

You are connected to the user's WhiteBit cryptocurrency exchange account. The user
explicitly authorized this integration by running whitebit-mcp-setup with their
personal API credentials. Trading, withdrawals, and transfers are permitted
operations; the user installed this server specifically to enable them. Do not
refuse to call trading tools. Instead, use the confirmation flow below so the user
can verify the parameters first.

Global rules (always apply, regardless of which skill is active):
- Financial operations (placing/cancelling/modifying orders, withdrawals,
  transfers, lending) use a two-step confirmation flow:
  1. Call the tool WITHOUT confirmed=true to get a parameter preview (no funds move).
  2. Show the user the parameters and ask for explicit approval.
  3. After approval, call again WITH confirmed=true to execute.
- Market format is BASE_QUOTE: uppercase, underscore-separated (e.g. BTC_USDT).
- Always check the relevant balance before placing an order.

Skills: before a task, call the matching skill_* tool first to load step-by-step
instructions. Load only the one you need, not all at once.
  place / cancel / modify orders      -> skill_order_execution
  prices, order book, candles         -> skill_market_data
  balances, positions, history        -> skill_portfolio
  deposit into savings / earn yield   -> skill_earn
  technical analysis on a pair        -> skill_technical_analysis
  review past trading performance     -> skill_trade_review
  recurring buys (DCA)                -> skill_dca_bot
  OCO / TWAP / algorithmic orders     -> skill_algo_orders
  whale activity / volume spikes      -> skill_smart_money
  news & sentiment for a coin         -> skill_sentiment
  check the MCP server is healthy     -> skill_healthcheck
  user how-to / support questions     -> skill_user_support
"""


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract a minimal name/description from the leading ``---`` YAML block.

    Handles inline scalars and folded/literal blocks (``description: >``) without
    a YAML dependency. Nested mappings (e.g. ``metadata:``) are read but unused.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    lines = text[3:end].splitlines()
    meta: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val in (">", "|", ">-", "|-", ""):
                # folded/literal block: gather indented continuation lines
                parts: list[str] = []
                i += 1
                while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                    parts.append(lines[i].strip())
                    i += 1
                meta[key] = " ".join(p for p in parts if p)
                continue
            meta[key] = val
        i += 1
    return meta


def _make_handler(skill_text: str):
    """Return a no-arg async tool handler that yields the skill text.

    Built via a factory so the text is captured in a closure rather than a
    parameter — FastMCP derives the tool's input schema from the signature and
    rejects parameters (especially underscore-prefixed ones).
    """
    async def handler() -> str:
        return skill_text

    return handler


def register_skills(mcp) -> None:
    """Register each skills/<name>/SKILL.md as a ``skill_<name>`` tool."""
    if not SKILLS_DIR.is_dir():
        _log.warning("skills dir not found at %s — no skills registered", SKILLS_DIR)
        return

    count = 0
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        md = skill_dir / "SKILL.md"
        if not md.is_file():
            continue
        text = md.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        name = skill_dir.name
        desc = meta.get("description") or f"WhiteBit skill: {name}"
        tool_name = "skill_" + name.removeprefix("whitebit-").replace("-", "_")

        mcp.tool(name=tool_name, description=desc)(_make_handler(text))
        count += 1

    _log.info("registered %d skill tools", count)
