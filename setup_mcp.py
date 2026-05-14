"""CLI setup script: generates MCP config files for AI tools."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import stat
import subprocess
import sys
from pathlib import Path

MCP_SERVER_NAME = "whitebit"
_LOCAL_PKG_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# stdio entry (uvx transport)
# ---------------------------------------------------------------------------

def _stdio_entry(api_key: str, secret_key: str, base_url: str, local: bool = False) -> dict:
    args = ["--from", str(_LOCAL_PKG_DIR), "whitebit-mcp"] if local else ["whitebit-mcp"]
    return {
        "command": "uvx",
        "args": args,
        "env": {
            "WHITEBIT_API_KEY": api_key,
            "WHITEBIT_SECRET_KEY": secret_key,
            "WHITEBIT_BASE_URL": base_url,
        },
    }


# ---------------------------------------------------------------------------
# HTTP entry (Docker transport)
# ---------------------------------------------------------------------------

def _http_entry(api_key: str, secret_key: str, port: int) -> dict:
    return {
        "type": "http",
        "url": f"http://localhost:{port}/mcp",
        "headers": {
            "X-WB-Api-Key": api_key,
            "X-WB-Secret-Key": secret_key,
        },
    }


_STALE_KEYS = ("whitebit-mcp",)  # old HTTP-entry name written by previous versions


# ---------------------------------------------------------------------------
# JSON config helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Per-tool setup functions
# ---------------------------------------------------------------------------

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


def setup_claude_code_stdio(
    entry: dict,
    *,
    api_key: str,
    secret_key: str,
    base_url: str,
    local: bool,
) -> Path:
    """Use `claude mcp add` (stdio) if available; fall back to ~/.claude.json."""
    uvx_args = ["--from", str(_LOCAL_PKG_DIR), "whitebit-mcp"] if local else ["whitebit-mcp"]
    cmd = [
        "claude", "mcp", "add",
        MCP_SERVER_NAME,
        "-s", "user",
        "-e", f"WHITEBIT_API_KEY={api_key}",
        "-e", f"WHITEBIT_SECRET_KEY={secret_key}",
        "-e", f"WHITEBIT_BASE_URL={base_url}",
        "--", "uvx", *uvx_args,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return Path.home() / ".claude.json"
    except FileNotFoundError:
        pass
    # Fallback: write directly to ~/.claude.json (user-level Claude Code config)
    config_path = Path.home() / ".claude.json"
    _merge_mcp_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


def setup_claude_code_docker(entry: dict, *, api_key: str, secret_key: str, port: int) -> Path:
    """Use `claude mcp add` (HTTP) if available; fall back to ~/.claude.json."""
    url = f"http://localhost:{port}/mcp"
    cmd = [
        "claude", "mcp", "add",
        MCP_SERVER_NAME,
        "-s", "user",
        "-t", "http",
        "-H", f"X-WB-Api-Key: {api_key}",
        "-H", f"X-WB-Secret-Key: {secret_key}",
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return Path.home() / ".claude.json"
    except FileNotFoundError:
        pass
    config_path = Path.home() / ".claude.json"
    _merge_mcp_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


def setup_cursor(entry: dict) -> Path:
    config_path = Path.home() / ".cursor" / "mcp.json"
    _merge_mcp_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


def _merge_codex_toml_stdio(
    path: Path, api_key: str, secret_key: str, base_url: str, local: bool
) -> None:
    """Upsert [mcp_servers.whitebit] stdio block in Codex config.toml."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

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

    uvx_args_line = (
        f'args = ["--from", "{_LOCAL_PKG_DIR}", "whitebit-mcp"]\n' if local
        else 'args = ["whitebit-mcp"]\n'
    )
    block = (
        f"\n[mcp_servers.{MCP_SERVER_NAME}]\n"
        f'command = "uvx"\n'
        f"{uvx_args_line}"
        f"\n[mcp_servers.{MCP_SERVER_NAME}.env]\n"
        f'WHITEBIT_API_KEY = "{api_key}"\n'
        f'WHITEBIT_SECRET_KEY = "{secret_key}"\n'
        f'WHITEBIT_BASE_URL = "{base_url}"\n'
    )
    path.write_text("\n".join(result).rstrip() + block, encoding="utf-8")


def _merge_codex_toml_docker(path: Path, api_key: str, secret_key: str, port: int) -> None:
    """Upsert [mcp_servers.whitebit] HTTP block in Codex config.toml."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

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
        f'type = "http"\n'
        f'url = "http://localhost:{port}/mcp"\n'
        f"\n[mcp_servers.{MCP_SERVER_NAME}.headers]\n"
        f'"X-WB-Api-Key" = "{api_key}"\n'
        f'"X-WB-Secret-Key" = "{secret_key}"\n'
    )
    path.write_text("\n".join(result).rstrip() + block, encoding="utf-8")


def setup_codex_stdio(
    api_key: str = "", secret_key: str = "", base_url: str = "", local: bool = False
) -> Path:
    config_path = Path.home() / ".codex" / "config.toml"
    _merge_codex_toml_stdio(config_path, api_key, secret_key, base_url, local)
    return config_path


def setup_codex_docker(api_key: str = "", secret_key: str = "", port: int = 8080) -> Path:
    config_path = Path.home() / ".codex" / "config.toml"
    _merge_codex_toml_docker(config_path, api_key, secret_key, port)
    return config_path


def _merge_openclaw_json(path: Path, entries: dict[str, dict]) -> None:
    """Read existing OpenClaw config, upsert mcp.servers entries, write back."""
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
    """Try `openclaw mcp set` CLI; fall back to ~/.openclaw/openclaw.json."""
    cmd = ["openclaw", "mcp", "set", MCP_SERVER_NAME, json.dumps(entry)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return Path.home() / ".openclaw" / "openclaw.json"
    except FileNotFoundError:
        pass
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    _merge_openclaw_json(config_path, {MCP_SERVER_NAME: entry})
    return config_path


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _harden_file(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure WhiteBit MCP server for AI coding tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # stdio via uvx (PyPI)\n"
            "  whitebit-mcp-setup --public=KEY\n\n"
            "  # stdio via uvx, staging, local package\n"
            "  whitebit-mcp-setup --public=KEY --base-url=https://st.imoney24.technology --local\n\n"
            "  # Docker HTTP transport (requires running container)\n"
            "  whitebit-mcp-setup --public=KEY --docker\n\n"
            "  # Docker on custom port\n"
            "  whitebit-mcp-setup --public=KEY --docker --port=9090"
        ),
    )
    parser.add_argument("--public", required=True, metavar="API_KEY", help="WhiteBit API key (public)")
    parser.add_argument("--secret", metavar="SECRET_KEY",
                        help="WhiteBit secret key (omit to be prompted securely)")
    parser.add_argument(
        "--base-url",
        default="https://whitebit.com",
        metavar="URL",
        help="WhiteBit API base URL for stdio mode (default: https://whitebit.com)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="stdio mode: use local package directory instead of PyPI (for development)",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="HTTP transport mode: connect to a running Docker container",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        metavar="PORT",
        help="Docker container host port (default: 8080)",
    )
    args = parser.parse_args()

    if args.secret:
        secret_key = args.secret
    else:
        secret_key = getpass.getpass("WhiteBit secret key: ")

    if not secret_key:
        print("Error: secret key is required.", file=sys.stderr)
        sys.exit(1)

    docker: bool = args.docker
    local: bool = args.local
    base_url: str = args.base_url
    port: int = args.port

    if docker:
        entry = _http_entry(args.public, secret_key, port)
    else:
        entry = _stdio_entry(args.public, secret_key, base_url, local)

    print(f"\nWhiteBit MCP setup ({'Docker/HTTP' if docker else 'stdio/uvx'})\n")
    written: list[Path] = []
    ok = True

    targets: list[tuple[str, object]] = [
        ("Claude Desktop", setup_claude_desktop),
        ("Claude Code",    setup_claude_code_docker if docker else setup_claude_code_stdio),
        ("Cursor",         setup_cursor),
        ("Codex",          setup_codex_docker if docker else setup_codex_stdio),
        ("OpenClaw",       setup_openclaw),
    ]

    for name, fn in targets:
        try:
            if fn is setup_claude_code_stdio:
                path = fn(entry, api_key=args.public, secret_key=secret_key, base_url=base_url, local=local)
            elif fn is setup_claude_code_docker:
                path = fn(entry, api_key=args.public, secret_key=secret_key, port=port)
            elif fn is setup_codex_stdio:
                path = fn(api_key=args.public, secret_key=secret_key, base_url=base_url, local=local)
            elif fn is setup_codex_docker:
                path = fn(api_key=args.public, secret_key=secret_key, port=port)
            else:
                path = fn(entry)  # type: ignore[call-arg]
            if path is None:
                print(f"  - {name:<20} skipped (not supported on this OS)")
            else:
                _harden_file(path)
                written.append(path)
                print(f"  ✓ {name:<20} {path}")
        except Exception as exc:
            print(f"  ✗ {name:<20} failed: {exc}", file=sys.stderr)
            ok = False

    if written:
        print(
            "\n⚠  Credentials are stored in plaintext in the config files above.\n"
            "   Ensure these files are excluded from backups, version control, and cloud sync.\n"
            "   File permissions have been set to 600 (owner read/write only)."
        )
    if docker:
        print(f"\nMake sure the Docker container is running: docker-compose up -d")
    print("\nDone. Restart your AI tool to apply changes.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
