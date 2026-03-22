# Contributing to whitebit-mcp

Thank you for your interest in contributing! This document covers environment setup, the server architecture, and the process for submitting changes.

## Table of Contents

- [Setup](#setup)
- [Running Locally](#running-locally)
- [Architecture](#architecture)
- [Adding a New SDK Client](#adding-a-new-sdk-client)
- [Code Style](#code-style)
- [Tests](#tests)
- [Pull Request Checklist](#pull-request-checklist)

---

## Setup

### Prerequisites

- Python 3.12+
- pip (or [uv](https://docs.astral.sh/uv/) for faster installs)
- Docker (optional, for container testing)

### Install

```bash
git clone https://github.com/whitebit-exchange/whitebit-mcp.git
cd whitebit-mcp

# With pip
pip install -r requirements.txt

# Or with pip in editable mode (includes dev tools)
pip install -e ".[dev]"

# Or with uv (installs deps without creating a lockfile)
uv pip install -r requirements.txt
```

### Environment

```bash
cp .env.example .env
```

The only server-side variable is `WHITEBIT_BASE_URL` (defaults to `https://whitebit.com`).
API keys are not configured here — they are passed as parameters in each tool call.

---

## Running Locally

```bash
python server.py
```

The server starts on `http://0.0.0.0:8000`. The MCP endpoint is at `/mcp`.

To connect from Claude Code:

```bash
claude mcp add --transport http --scope user whitebit http://localhost:8000/mcp
```

To test with Docker:

```bash
docker compose up --build
# MCP endpoint: http://localhost:8080/mcp
```

To verify the SDK version (must be ≥ 1.1.6):

```bash
pip show whitebit-python-sdk
```

---

## Architecture

The entire server is a single file: `server.py`.

### How tools are registered

`server.py` uses `FastMCP` and the `whitebit-python-sdk` to register tools dynamically
at startup via `register_whitebit_tools()`.

**`SUBCLIENT_CLASSES`** is the authoritative list of SDK clients exposed as MCP tools:

```python
SUBCLIENT_CLASSES: dict[str, type] = {
    "public_api_v4": AsyncPublicApiV4Client,
    "spot_trading": AsyncSpotTradingClient,
    "collateral_trading": AsyncCollateralTradingClient,
    # ... etc
}
```

For every entry, `register_whitebit_tools()` iterates the public methods of the client
class and registers each as an MCP tool named `{subclient_attr}__{method_name}`. For
example, `spot_trading` + `create_limit_order` → tool name `spot_trading__create_limit_order`.

A small set of top-level methods on `AsyncWhitebitApi` (`convert_estimate`,
`convert_confirm`, `convert_history`) are registered directly without a subclient prefix.

The `get_credentials_status` tool is registered manually as a debug utility.

### `_make_tool()` — what it does

For each SDK method, `_make_tool()`:

1. Strips internal SDK parameters (`self`, `request_options`, HMAC signing fields)
2. Injects `api_key` and `secret_key` as required keyword-only parameters
3. Determines the auth pattern (see below) from the subclient name
4. Returns an async function that builds the appropriate SDK client with the right
   transport and calls the method

### Three authentication patterns

| Pattern | Subclients | Transport |
|---|---|---|
| **Public** | `public_api_v4` (GET requests) | HMAC transport, but WhiteBIT API does not validate keys on GET |
| **HMAC** | `spot_trading`, `collateral_trading`, `main_account`, `deposit`, `withdraw`, `transfer`, `codes`, `crypto_lending_fixed`, `crypto_lending_flex`, `fees`, `sub_account`, `sub_account_api_keys`, `mining_pool`, `credit_line`, `market_fee`, `jwt`, and top-level converts | `WhitebitHmacTransport` signs POST requests with HMAC-SHA512 using `X-TXC-APIKEY`, `X-TXC-PAYLOAD`, `X-TXC-SIGNATURE` headers |
| **OAuth2** | `authentication`, `account_endpoints` | Bearer token flow — scheduled for removal |

### Note on `wb_mcp/`

The `wb_mcp/` directory in this repository is from a prior modular architecture and is
not used by `server.py`. Do not modify it. It will be removed in a future cleanup.

---

## Adding a New SDK Client

When the `whitebit-python-sdk` gains a new client module:

1. Import the async client class at the top of `server.py`
2. Add it to `SUBCLIENT_CLASSES` with a snake_case key
3. Verify the auth pattern — if the new client uses HMAC POST requests (most do), no
   further changes are needed. The `_make_tool()` function handles it automatically
4. Run the server and confirm the tools appear: `python server.py` and connect via MCP
5. Add entries for the new tools to `llms.txt`
6. Update the tool count in `README.md`

---

## Code Style

The project uses `ruff` for linting and formatting, and `mypy` for type checking.

```bash
# Lint
ruff check .

# Auto-fix
ruff check --fix .

# Format
ruff format .

# Type check
mypy --strict server.py
```

All rules are configured in `pyproject.toml`.

---

## Tests

The `tests/` directory contains tests written for a prior version of the server and does
not cover `server.py`. Contributions that add tests for the current architecture are
welcome.

To run whatever tests exist:

```bash
pytest tests/
```

---

## Pull Request Checklist

Before submitting a PR:

- [ ] `ruff check .` passes with no errors
- [ ] `ruff format --check .` passes
- [ ] `mypy --strict server.py` passes with zero errors
- [ ] If a new SDK client was added: `llms.txt` and `README.md` tool count updated
- [ ] `CHANGELOG.md` updated under `[Unreleased]` with a brief description
