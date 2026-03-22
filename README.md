# whitebit-mcp

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes the [WhiteBIT](https://whitebit.com) exchange API as AI tools. Connect it to Cursor, Claude Code, or Claude Desktop and interact with markets, order books, trading, balances, and more in plain language.

## Features

- **115 tools** across market data, spot trading, collateral trading, wallet, lending, sub-accounts, mining pool, and currency conversion
- Credentials are passed per tool call — the server never stores API keys
- Runs as a single Docker container; no external infrastructure needed
- Full tool reference: [`llms.txt`](llms.txt)

## Quick Start (Docker)

```bash
git clone https://github.com/whitebit-exchange/whitebit-mcp
cd whitebit-mcp

docker compose up -d
```

The MCP endpoint is at `http://localhost:8080/mcp`.

To stop:

```bash
docker compose down
```

## Connecting Your AI Client

### Cursor

Create or edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "whitebit": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

Then open the Command Palette (`Cmd+Shift+P`) → **MCP: Reload Servers**.

### Claude Code (CLI)

The repo ships with a `.mcp.json` at the project root. Running `claude` from inside this directory registers the server automatically (project scope).

To register it globally for all projects:

```bash
claude mcp add --transport http --scope user whitebit http://localhost:8080/mcp
```

Verify:

```bash
claude mcp list
# whitebit: http://localhost:8080/mcp (http)
```

Use `/mcp` inside a Claude Code session to see live server status and available tools.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "whitebit": {
      "type": "http",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

Restart Claude Desktop.

### Codex

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.whitebit]
url = "http://localhost:8080/mcp"
```

Then start a Codex session — it will connect to the server automatically.

### OpenClaw

Add to your OpenClaw agent config:

```json
{
  "mcp_servers": {
    "whitebit": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## API Keys

Most tools require WhiteBIT API keys. Generate them at [whitebit.com](https://whitebit.com) → Profile → API Keys. Use the minimum permissions your use case requires — read-only keys are sufficient for balance and order queries.

**How credentials work:** API keys are passed as parameters in each tool call. Your AI client sends them on your behalf when you provide them in conversation. The server uses them only to sign the outgoing WhiteBIT API request and does not store, log, or cache them.

**Public market data tools** (market info, tickers, order book, etc.) query WhiteBIT's public endpoints. The server still requires both `api_key` and `secret_key` to be non-empty strings — pass `"public"` for both if you only need public data.

### Example: telling the AI your keys

At the start of a session with authenticated tools, tell the AI:

```
My WhiteBIT API key is <your-public-key> and secret is <your-secret-key>.
Show my spot balance.
```

The AI will pass your credentials as tool parameters for the duration of the conversation.

## Example Prompts

**Market data (any string for api_key/secret_key)**

- "What is the current BTC_USDT price?"
- "Show me the order book for ETH_USDT"
- "What are the deposit fees for USDT?"
- "List all available markets"
- "What's the funding rate history for BTC_USDT?"
- "Is WhiteBIT in maintenance mode?"

**Spot trading (API keys required)**

- "What is my spot balance?"
- "Show my open orders on BTC_USDT"
- "Place a limit buy order for 0.001 BTC at $90,000 on BTC_USDT"
- "Cancel all my open orders on ETH_USDT"
- "Show my order history for the last 30 days"

**Wallet (API keys required)**

- "What is my deposit address for USDT on TRC20?"
- "Show my recent deposits and withdrawals"
- "Transfer 100 USDT from my main account to spot trading"
- "Create a WhiteBIT code for 50 USDT"

**Collateral trading (API keys required)**

- "What are my open collateral positions?"
- "Place a collateral limit buy for 0.01 BTC on BTC_USDT"
- "What is my current leverage?"
- "Close my BTC_USDT position"

**Sub-accounts (API keys required)**

- "List all my sub-accounts"
- "Show the balance of sub-account ID 123"
- "Transfer 200 USDT to sub-account ID 456"

## Configuration

| Variable | Default | Description |
|---|---|---|
| `WHITEBIT_BASE_URL` | `https://whitebit.com` | API base URL — override for custom deployments |

Set it in `docker-compose.yml` or as a shell variable:

```bash
WHITEBIT_BASE_URL=https://whitebit.com docker compose up
```

## Running Without Docker

```bash
pip install -r requirements.txt
python server.py
```

The server listens on `http://0.0.0.0:8000`. When running without Docker, update your MCP client config to use port 8000 instead of 8080.

## Development

```bash
pip install -e ".[dev]"
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
