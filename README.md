<h1 align="center">WhiteBit MCP Server</h1>

<p align="center">
  <strong>Connect AI assistants to WhiteBit — trade, query, and manage your crypto portfolio through natural language.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/MCP-compatible-8A2BE2?style=flat-square" alt="MCP compatible" />
  <img src="https://img.shields.io/badge/transport-HTTP-0070f3?style=flat-square" alt="HTTP transport" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT license" />
</p>

---

**WhiteBit MCP Server** is a [Model Context Protocol](https://modelcontextprotocol.io) server for the [WhiteBit](https://whitebit.com) cryptocurrency exchange. It exposes 100+ trading and account tools — auto-generated from the official WhiteBit Python SDK — that any MCP-compatible AI assistant can call through natural language. Check prices, manage orders, query balances, handle withdrawals, and more.

Works with **Claude Code**, **Claude Desktop**, **Cursor**, and any other MCP-compatible client.

> **Credentials are passed as tool parameters** (`api_key`, `secret_key`), not as server-level configuration. This means you can use different WhiteBit accounts within the same session without restarting the server.

---

## Prerequisites

Before you start, make sure you have the following:

| Requirement | Details |
|-------------|---------|
| **Docker & Docker Compose** | To run the server — [install Docker](https://docs.docker.com/get-docker/) |
| **WhiteBit account** | Sign up at [whitebit.com](https://whitebit.com) |
| **WhiteBit API key** | Profile → API keys → Create key (Read and/or Trade permissions) |
| **MCP-compatible AI client** | Claude Code, Claude Desktop, Cursor, or any other MCP client |
| **Python 3.11+** | Only if running without Docker |

---

## Quick Start

### 1. Get your WhiteBit API credentials

1. Log in to [whitebit.com](https://whitebit.com) → **Profile → API keys**
2. Create a new key — choose **Read** and/or **Trade** permissions as needed
3. Copy your **API Key** and **Secret Key**

> Public endpoints (market data, tickers, order book) work without credentials. Private endpoints (account, trading) require both.

### 2. Start the server

```bash
git clone https://github.com/whitebit-exchange/whitebit-mcp.git
cd whitebit-mcp
docker compose up -d
```

The server starts at `http://localhost:8000`.

### 3. Add to your AI client

#### Claude Code (project-level)

Create or update `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "whitebit-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Or via CLI:

```bash
claude mcp add whitebit-mcp "http://localhost:8000/mcp" -t http -s user
```

> Credentials (`api_key`, `secret_key`) are passed directly to each tool call — the server does not store them.

That's it. Your AI can now trade on WhiteBit.

---

## Integrations

### VS Code (Claude Extension)

Install the [Claude extension for VS Code](https://marketplace.visualstudio.com/items?itemName=Anthropic.claude-code), then add the server via CLI:

```bash
claude mcp add whitebit-mcp "http://localhost:8000/mcp" -t http -s user
```

Or create `.mcp.json` in your project root to share the config with your team:

```json
{
  "mcpServers": {
    "whitebit-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Once added, use `/mcp` in the Claude chat panel to enable, disable, or reconnect the server.

> `.mcp.json` is in `.gitignore` by default — if you want to share it with your team, remove it from `.gitignore` first.

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "whitebit-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Cursor

Add to your Cursor MCP settings (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "whitebit-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Codex

Add to your Codex MCP settings (`~/.codex/config.toml`):

```toml
[[mcp_servers]]
name = "whitebit-mcp"
type = "http"
url  = "http://localhost:8000/mcp"
```

Or using the JSON format (`~/.codex/mcp.json`):

```json
{
  "mcpServers": {
    "whitebit-mcp": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### OpenClaw

Add via CLI:

```bash
openclaw mcp set whitebit-mcp '{"url":"http://localhost:8000/mcp"}'
```

Or add to your OpenClaw config under `mcp.servers`:

```json
{
  "mcp": {
    "servers": {
      "whitebit-mcp": {
        "url": "http://localhost:8000/mcp"
      }
    }
  }
}
```

### Any MCP-compatible client

The server uses standard **Streamable HTTP transport** on `http://localhost:8000/mcp`. No server-level authentication is required — credentials are supplied per tool call.

---

## Usage Examples

Once connected, talk to your AI naturally. It will prompt you for credentials when needed:

```
"What's the current BTC/USDT price?"
"Show me my spot account balance"
"Place a limit buy order for 0.01 BTC at $95,000"
"Cancel all my open orders on ETH/USDT"
"What are the trading fees for BTC/USDT?"
"Transfer 100 USDT from my main account to my trade account"
"Show my open collateral positions"
"Withdraw 500 USDT to address 0x..."
```

---

## How Credentials Work

Unlike header-based servers, this server receives `api_key` and `secret_key` as explicit parameters on every tool call. The AI assistant supplies them from the conversation context.

| Endpoint type | Required parameters |
|---------------|---------------------|
| Public (market data) | `api_key`, `secret_key` |
| Private (trading, account) | `api_key`, `secret_key` |
| Account endpoints (OAuth2) | `api_key`, `bearer_token` |

To obtain a `bearer_token` for account endpoints, use the `authentication__get_access_token` tool first.

Use `get_credentials_status` to verify that credentials are being passed correctly.

---

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```env
# WhiteBit API base URL
WHITEBIT_BASE_URL=https://whitebit.com

# Server port (default: 8000)
PORT=8000

# Log level: debug | info | warn | error
LOG_LEVEL=info
```


## Available Tools

100+ tools auto-generated from the official WhiteBit Python SDK across 19 categories:

| Category | Tool prefix |
|----------|-------------|
| **Authentication** | `authentication__` |
| **Account endpoints** | `account_endpoints__` |
| **Public API v4** | `public_api_v4__` |
| **Main account** | `main_account__` |
| **Deposit** | `deposit__` |
| **Withdraw** | `withdraw__` |
| **Transfer** | `transfer__` |
| **Codes** | `codes__` |
| **Spot trading** | `spot_trading__` |
| **Collateral trading** | `collateral_trading__` |
| **Market fee** | `market_fee__` |
| **Fees** | `fees__` |
| **Convert** | `convert_estimate`, `convert_confirm`, `convert_history` |
| **Crypto lending (flex)** | `crypto_lending_flex__` |
| **Crypto lending (fixed)** | `crypto_lending_fixed__` |
| **Sub-account** | `sub_account__` |
| **Sub-account API keys** | `sub_account_api_keys__` |
| **Mining pool** | `mining_pool__` |
| **Credit line** | `credit_line__` |
| **Credentials** | `get_credentials_status` |

Tools are named `{category}__{method}` (e.g. `spot_trading__create_limit_order`). All tool names and parameters are derived directly from the SDK — no manual mapping.

---

## Security

- Credentials are passed per tool call — **never stored** in server memory or logs
- Use **read-only API keys** if you only need market data or account queries
- For trading, create a dedicated API key with only the permissions you need
- Consider IP whitelisting on your WhiteBit API key for additional protection

---

## Running without Docker

Requirements: **Python 3.11+**

```bash
pip install -r requirements.txt

# Run
python server.py
```

The server listens on `PORT` (default `8000`).

---

## License

[MIT](LICENSE)
