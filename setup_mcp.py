"""CLI setup script: generates MCP config files for AI tools."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from pathlib import Path

MCP_SERVER_NAME = "whitebit"


def _server_entry(api_key: str, secret_key: str) -> dict:
    return {
        "command": "uvx",
        "args": ["whitebit-mcp"],
        "env": {
            "WHITEBIT_API_KEY": api_key,
            "WHITEBIT_SECRET_KEY": secret_key,
        },
    }


_STALE_KEYS = ("whitebit-mcp",)  # old HTTP-entry name written by previous versions


def _merge_mcp_json(path: Path, entries: dict[str, dict]) -> None:
    """Read existing JSON config, upsert mcpServers entries, write back.

    Also removes stale keys left by older versions of this script.
    """
    config: dict = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    servers = config.setdefault("mcpServers", {})
    for stale in _STALE_KEYS:
        servers.pop(stale, None)
    servers.update(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def setup_claude_desktop(entry: dict) -> Path | None:
    system = platform.system()
    if system == "Darwin":
        config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        config_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        return None
    _merge_mcp_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


def setup_claude_code(entry: dict) -> Path:
    # User-level MCP config for Claude Code CLI
    config_path = Path.home() / ".claude.json"
    _merge_mcp_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


def setup_cursor(entry: dict) -> Path:
    # Global Cursor MCP config
    config_path = Path.home() / ".cursor" / "mcp.json"
    _merge_mcp_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


def _merge_codex_toml(path: Path, api_key: str, secret_key: str) -> None:
    """Upsert [mcp_servers.whitebit] block in Codex config.toml.

    Works line-by-line to avoid false matches on TOML array literals like
    args = ["whitebit-mcp"] that contain '['.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    # Drop all lines that belong to the whitebit section (header + subsections).
    prefix = f"[mcp_servers.{MCP_SERVER_NAME}"
    result: list[str] = []
    inside = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            inside = True
        elif stripped.startswith("[") and not stripped.startswith(prefix):
            inside = False
        if not inside:
            result.append(line)

    block = (
        f"\n[mcp_servers.{MCP_SERVER_NAME}]\n"
        f'command = "uvx"\n'
        f'args = ["whitebit-mcp"]\n'
        f"\n[mcp_servers.{MCP_SERVER_NAME}.env]\n"
        f'WHITEBIT_API_KEY = "{api_key}"\n'
        f'WHITEBIT_SECRET_KEY = "{secret_key}"\n'
    )

    cleaned = "\n".join(result).rstrip()
    path.write_text(cleaned + block, encoding="utf-8")


def setup_codex(api_key: str = "", secret_key: str = "") -> Path:
    # OpenAI Codex CLI uses TOML config
    config_path = Path.home() / ".codex" / "config.toml"
    _merge_codex_toml(config_path, api_key, secret_key)
    return config_path


def _merge_openclaw_json(path: Path, entries: dict[str, dict]) -> None:
    """Read existing OpenClaw config, upsert mcp.servers entries, write back.

    OpenClaw uses {"mcp": {"servers": {...}}} — NOT the "mcpServers" top-level
    key used by Claude Desktop/Code.  Writing "mcpServers" breaks OpenClaw,
    so any stale "mcpServers" key is removed on every run.
    """
    config: dict = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    config.pop("mcpServers", None)  # remove stale key that breaks OpenClaw
    config.setdefault("mcp", {}).setdefault("servers", {}).update(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def setup_openclaw(entry: dict) -> Path:
    # OpenClaw uses mcp.servers nested structure (NOT mcpServers)
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    _merge_openclaw_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


_TARGETS = [
    ("Claude Desktop", setup_claude_desktop),
    ("Claude Code",    setup_claude_code),
    ("Cursor",         setup_cursor),
    ("Codex",          setup_codex),
    ("OpenClaw",       setup_openclaw),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure WhiteBit MCP server for AI coding tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  whitebit-mcp-setup --public=YOUR_API_KEY --secret=YOUR_SECRET_KEY",
    )
    parser.add_argument("--public", required=True, metavar="API_KEY",    help="WhiteBit API key (public)")
    parser.add_argument("--secret", required=True, metavar="SECRET_KEY", help="WhiteBit secret key")
    args = parser.parse_args()

    entry = _server_entry(args.public, args.secret)

    print("WhiteBit MCP setup\n")
    ok = True
    for name, fn in _TARGETS:
        try:
            if fn is setup_codex:
                path = fn(api_key=args.public, secret_key=args.secret)
            else:
                path = fn(entry)
            if path is None:
                print(f"  - {name:<20} skipped (not supported on this OS)")
            else:
                print(f"  ✓ {name:<20} {path}")
        except Exception as exc:
            print(f"  ✗ {name:<20} failed: {exc}", file=sys.stderr)
            ok = False

    print("\nDone. Restart your AI tool to apply changes.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
