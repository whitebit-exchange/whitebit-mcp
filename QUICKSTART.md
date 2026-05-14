# WhiteBit MCP — Quick Start

Connect Claude (or any MCP-compatible AI) to the WhiteBit exchange in under 5 minutes.

Two options — pick one:

| | Option A: uvx | Option B: Docker |
|---|---|---|
| **Requires** | [uv](https://docs.astral.sh/uv/getting-started/installation/) | [Docker](https://docs.docker.com/get-docker/) + [git](https://git-scm.com/) |
| **How it runs** | Process per AI session (stdio) | Persistent local HTTP server |
| **Best for** | Personal use, quick setup | Teams, multiple users, always-on |

---

## Prerequisites for both options

**1. Get WhiteBit API keys**

Log in → **Profile → API Keys → Create key**

Choose permissions: `Read` for balance/market data, `Trade` to place orders.
Copy your **API Key** and **Secret Key**.

**2. Install Claude Code CLI** (if using Claude)

```bash
npm install -g @anthropic-ai/claude-code
```

Or use Claude Desktop, Cursor, or any other MCP-compatible client.

---

## Option A — uvx (stdio)

No server to manage. The MCP process starts automatically with each AI session.

### Step 1 — Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Step 2 — Configure all AI tools at once

```bash
uvx --from whitebit-mcp whitebit-mcp-setup --public=YOUR_API_KEY --secret=YOUR_SECRET_KEY
```

This writes config for **Claude Code, Claude Desktop, Cursor, Codex, and OpenClaw** in one shot.
You will be prompted for the secret key if you omit `--secret`.

### Step 3 — Restart your AI tool

```bash
# Claude Code: start a new session
claude

# Claude Desktop: quit and reopen the app
```

### Step 4 — Test

Ask Claude: **"What is my WhiteBit main account balance?"**

---

## Option B — Docker (HTTP server)

A persistent server on `localhost:8080`. Credentials go in request headers — the server never stores them.

### Step 1 — Clone and start the server

```bash
git clone https://github.com/whitebit-exchange/whitebit-mcp.git
cd whitebit-mcp
docker-compose up -d
```

Verify it's running:
```bash
docker-compose ps
```

### Step 2 — Connect your AI tool

**Claude Code**
```bash
claude mcp add whitebit "http://localhost:8080/mcp" \
  -s user \
  -t http \
  -H "X-WB-Api-Key: YOUR_API_KEY" \
  -H "X-WB-Secret-Key: YOUR_SECRET_KEY"
```

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):
```json
{
  "mcpServers": {
    "whitebit": {
      "type": "http",
      "url": "http://localhost:8080/mcp",
      "headers": {
        "X-WB-Api-Key": "YOUR_API_KEY",
        "X-WB-Secret-Key": "YOUR_SECRET_KEY"
      }
    }
  }
}
```

**Cursor** — add to `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "whitebit": {
      "type": "http",
      "url": "http://localhost:8080/mcp",
      "headers": {
        "X-WB-Api-Key": "YOUR_API_KEY",
        "X-WB-Secret-Key": "YOUR_SECRET_KEY"
      }
    }
  }
}
```

**OpenClaw**
```bash
openclaw mcp set whitebit '{"url":"http://localhost:8080/mcp","headers":{"X-WB-Api-Key":"YOUR_API_KEY","X-WB-Secret-Key":"YOUR_SECRET_KEY"}}'
```

### Step 3 — Restart your AI tool and test

Ask Claude: **"What is my WhiteBit main account balance?"**

### Managing the server

```bash
docker-compose stop        # stop
docker-compose start       # start again
docker-compose down        # remove container
docker-compose logs -f     # view logs
```

---

## Verify the connection

Ask your AI:

```
"Show my WhiteBit spot account balance"
"What is the current BTC/USDT price?"
"List my open orders"
```

Public endpoints (prices, order book) work without API keys.
Private endpoints (balance, trading) require both API key and secret.

---

## Troubleshooting

**"No tools available" / MCP not connecting**
- Option A: make sure `uv` is installed and on PATH; try `uvx --version`
- Option B: check `docker-compose ps` — container must show `Up`; check `docker-compose logs`
- Restart your AI tool after configuring

**"Invalid signature" / authentication errors**
- Double-check that you copied both the API key and the secret key correctly
- Verify the key has the required permissions on the WhiteBit dashboard

**Option B: connection refused on port 8080**
- Another process may be using the port; change it in `docker-compose.yml` (`"9090:8000"`) and update your AI tool config to match
