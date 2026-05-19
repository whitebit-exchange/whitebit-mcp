import base64
import hashlib
import hmac as _hmac
import inspect
import json
import logging
import os
import re
import secrets
import time
from contextvars import ContextVar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("whitebit_mcp")
# Prevent httpx/httpcore from leaking request bodies (amounts, addresses) at DEBUG level.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.types import ASGIApp, Receive, Scope, Send

from whitebit.core.client_wrapper import AsyncClientWrapper
from whitebit.environment import WhitebitApiEnvironment
from whitebit.authentication.client import AsyncAuthenticationClient
from whitebit.account_endpoints.client import AsyncAccountEndpointsClient
from whitebit.public_api_v4.client import AsyncPublicApiV4Client
from whitebit.main_account.client import AsyncMainAccountClient
from whitebit.deposit.client import AsyncDepositClient
from whitebit.jwt.client import AsyncJwtClient
from whitebit.withdraw.client import AsyncWithdrawClient
from whitebit.transfer.client import AsyncTransferClient
from whitebit.codes.client import AsyncCodesClient
from whitebit.crypto_lending_fixed.client import AsyncCryptoLendingFixedClient
from whitebit.crypto_lending_flex.client import AsyncCryptoLendingFlexClient
from whitebit.fees.client import AsyncFeesClient
from whitebit.sub_account.client import AsyncSubAccountClient
from whitebit.sub_account_api_keys.client import AsyncSubAccountApiKeysClient
from whitebit.mining_pool.client import AsyncMiningPoolClient
from whitebit.credit_line.client import AsyncCreditLineClient
from whitebit.collateral_trading.client import AsyncCollateralTradingClient
from whitebit.market_fee.client import AsyncMarketFeeClient
from whitebit.spot_trading.client import AsyncSpotTradingClient
from whitebit.client import AsyncWhitebitApi, OMIT

# ---------------------------------------------------------------------------
# Credentials are read from:
#   HTTP transport  — request headers X-WB-Api-Key / X-WB-Secret-Key
#   stdio transport — env vars WHITEBIT_API_KEY / WHITEBIT_SECRET_KEY
#
# WHITEBIT_BASE_URL is an env-var-only setting (useful for testnet).
# account_endpoints use OAuth2 Bearer auth; supply via X-WB-Bearer-Token header or WHITEBIT_BEARER_TOKEN env var.
# ---------------------------------------------------------------------------

SUBCLIENT_CLASSES: dict[str, type] = {
    "authentication": AsyncAuthenticationClient,
    "account_endpoints": AsyncAccountEndpointsClient,
    "public_api_v4": AsyncPublicApiV4Client,
    "main_account": AsyncMainAccountClient,
    "deposit": AsyncDepositClient,
    "jwt": AsyncJwtClient,
    "withdraw": AsyncWithdrawClient,
    "transfer": AsyncTransferClient,
    "codes": AsyncCodesClient,
    "crypto_lending_fixed": AsyncCryptoLendingFixedClient,
    "crypto_lending_flex": AsyncCryptoLendingFlexClient,
    "fees": AsyncFeesClient,
    "sub_account": AsyncSubAccountClient,
    "sub_account_api_keys": AsyncSubAccountApiKeysClient,
    "mining_pool": AsyncMiningPoolClient,
    "credit_line": AsyncCreditLineClient,
    "collateral_trading": AsyncCollateralTradingClient,
    "market_fee": AsyncMarketFeeClient,
    "spot_trading": AsyncSpotTradingClient,
}

_TOP_LEVEL_METHODS = ("convert_estimate", "convert_confirm", "convert_history")

# Per-request credential storage (set by CredentialsMiddleware for HTTP transport).
_api_key_var: ContextVar[str] = ContextVar("wb_api_key", default="")
_secret_key_var: ContextVar[str] = ContextVar("wb_secret_key", default="")
_bearer_token_var: ContextVar[str] = ContextVar("wb_bearer_token", default="")

# HMAC signing fields injected by the transport — stripped from SDK method params.
_HMAC_FIELDS = {"request", "nonce"}

# ---------------------------------------------------------------------------
# R-01: Financial tools — require explicit user confirmation (HITL)
# ---------------------------------------------------------------------------

_FINANCIAL_METHODS: frozenset[str] = frozenset({
    # Withdrawals
    "create_withdraw", "create_withdraw_pay",
    # Transfers
    "between_balances", "transfer",
    # Spot trading — orders and kill switch
    "create_limit_order", "create_market_order", "create_stock_market_order",
    "create_stop_limit_order", "create_stop_market_order", "create_bulk_limit_order",
    "cancel_order", "cancel_all_orders", "modify_order", "set_kill_switch",
    # Collateral trading
    "create_collateral_limit_order", "create_collateral_market_order",
    "create_collateral_stop_limit_order", "create_collateral_trigger_market_order",
    "create_collateral_oco_order", "create_collateral_bulk_order",
    "cancel_conditional_order", "cancel_oco_order", "cancel_oto_order",
    "close_position",
    # Codes
    "create_code", "apply_code",
    # Lending
    "create_fixed_investment", "close_fixed_investment",
    "create_flex_investment", "close_flex_investment", "withdraw_from_flex_investment",
    # Convert
    "convert_confirm",
})

_FINANCIAL_DESCRIPTION_PREFIX = (
    "⚠️ FINANCIAL ACTION — always describe to the user what you are about to do "
    "and ask for explicit approval BEFORE calling this tool. "
    "Only set confirmed=True after the user has approved. "
)

# ---------------------------------------------------------------------------
# R-08/R-11: Response sanitization — mask sensitive fields, trim large lists
# ---------------------------------------------------------------------------

_SENSITIVE_KEY_RE = re.compile(
    r"secret|private_?key|password|seed|mnemonic|\bpin\b",
    re.IGNORECASE,
)
_DOC_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]*\)')   # [text](/path) → text
_DOC_TAG_RE  = re.compile(r'</?[A-Za-z][^>]*>')        # <Warning>, </Accordion> etc.

_PII_PARAM_RE = re.compile(
    r"address|amount|ticker|phone|email|account|iban|card|memo|tag|comment|recipient",
    re.IGNORECASE,
)
_MAX_LIST_ITEMS = 100


def _clean_description(doc: str | None) -> str:
    """Strip MDX markup and internal doc links from SDK docstring first line."""
    if not doc:
        return ""
    first_line = doc.strip().split("\n")[0].strip()
    first_line = _DOC_LINK_RE.sub(r"\1", first_line)
    first_line = _DOC_TAG_RE.sub("", first_line)
    return first_line.strip()


def _mask_log_params(params: dict) -> dict:
    """Return params copy safe for logging: mask PII/secret values, truncate long strings."""
    out = {}
    for k, v in params.items():
        if _SENSITIVE_KEY_RE.search(str(k)) or _PII_PARAM_RE.search(str(k)):
            out[k] = "[MASKED]"
        elif isinstance(v, str) and len(v) > 40:
            out[k] = v[:8] + "…"
        else:
            out[k] = v
    return out


def _to_serializable(obj: object) -> object:
    """Convert SDK model objects (Pydantic/dataclass) to plain Python types."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (dict, list)):
        return obj
    try:
        return obj.model_dump()  # type: ignore[union-attr]
    except AttributeError:
        pass
    try:
        return obj.dict()  # type: ignore[union-attr]
    except AttributeError:
        pass
    import dataclasses
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)  # type: ignore[arg-type]
    return str(obj)


def _sanitize(obj: object, _depth: int = 0) -> object:
    """Recursively mask sensitive fields and trim oversized lists."""
    if _depth > 8:
        return obj
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if _SENSITIVE_KEY_RE.search(str(k)) else _sanitize(v, _depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        out = [_sanitize(i, _depth + 1) for i in obj[:_MAX_LIST_ITEMS]]
        if len(obj) > _MAX_LIST_ITEMS:
            out.append({"_trimmed": f"{len(obj) - _MAX_LIST_ITEMS} more items not shown"})
        return out
    return obj


# SDK sends these snake_case keys but WhiteBit API expects camelCase.
_SNAKE_TO_CAMEL = {
    "order_id": "orderId",
    "client_order_id": "clientOrderId",
}

_ENV = None


def _get_credentials() -> tuple[str, str]:
    """Return (api_key, secret_key) from request context or env vars."""
    api_key = _api_key_var.get() or os.environ.get("WHITEBIT_API_KEY", "")
    secret_key = _secret_key_var.get() or os.environ.get("WHITEBIT_SECRET_KEY", "")
    return api_key, secret_key


def _get_bearer_token() -> str:
    """Return OAuth2 bearer token from request context or env vars."""
    return _bearer_token_var.get() or os.environ.get("WHITEBIT_BEARER_TOKEN", "")


_ALLOWED_BASE_URL = re.compile(
    r"^https://([a-z0-9-]+\.)?(whitebit\.(com|io)|imoney24\.technology)$"
)


def _get_environment() -> WhitebitApiEnvironment:
    global _ENV
    if _ENV is None:
        base_url = os.environ.get("WHITEBIT_BASE_URL", "https://whitebit.com")
        if not _ALLOWED_BASE_URL.match(base_url):
            raise ValueError(
                f"WHITEBIT_BASE_URL must be an HTTPS whitebit.com/whitebit.io/imoney24.technology URL, got: {base_url!r}"
            )
        _ENV = WhitebitApiEnvironment(
            base=base_url,
            production=WhitebitApiEnvironment.DEFAULT.production,
            eu=WhitebitApiEnvironment.DEFAULT.eu,
        )
    return _ENV


def _is_credentials_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "invalid payload" in msg or "code: 9" in msg


class CredentialsMiddleware:
    """ASGI middleware: extracts X-WB-Api-Key / X-WB-Secret-Key / X-WB-Bearer-Token headers into ContextVars.

    Rejects HTTP requests to /mcp with 401 when no credentials are present in
    either request headers or environment variables.  This prevents unauthenticated
    callers from connecting to the MCP endpoint and enumerating available tools.
    """

    _UNAUTHORIZED = (
        b'{"error":"Unauthorized: provide X-WB-Api-Key and X-WB-Secret-Key headers"}'
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers: dict[bytes, bytes] = dict(scope.get("headers", []))
            api_key = headers.get(b"x-wb-api-key", b"").decode()
            secret_key = headers.get(b"x-wb-secret-key", b"").decode()
            bearer_token = headers.get(b"x-wb-bearer-token", b"").decode()

            # Reject HTTP requests that carry no credentials at all.
            # Env-var credentials (stdio mode) are always accepted.
            if (
                scope["type"] == "http"
                and not api_key
                and not secret_key
                and not bearer_token
                and not os.environ.get("WHITEBIT_API_KEY")
                and not os.environ.get("WHITEBIT_SECRET_KEY")
                and not os.environ.get("WHITEBIT_BEARER_TOKEN")
                and scope.get("path", "").startswith("/mcp")
            ):
                _log.warning("auth_rejected path=%s peer=%s", scope.get("path"), scope.get("client"))
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b"WhiteBit-API-Key"),
                    ],
                })
                await send({"type": "http.response.body", "body": self._UNAUTHORIZED})
                return

            _api_key_var.set(api_key)
            _secret_key_var.set(secret_key)
            _bearer_token_var.set(bearer_token)
        await self.app(scope, receive, send)


class WhitebitHmacTransport(httpx.AsyncBaseTransport):
    """Signs POST requests with WhiteBit HMAC-SHA512."""

    def __init__(self, api_key: str, secret_key: str):
        self._api_key = api_key
        self._secret_key = secret_key
        self._inner = httpx.AsyncHTTPTransport()

    @staticmethod
    def _ua_for(request: httpx.Request) -> bytes:
        existing = request.headers.get("user-agent", "")
        return (f"{existing} mcp/python" if existing else "mcp/python").encode()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            try:
                body_bytes = request.content
            except httpx.RequestNotRead:
                body_bytes = b""

            body_dict = {}
            if body_bytes:
                try:
                    body_dict = json.loads(body_bytes)
                except (json.JSONDecodeError, ValueError):
                    pass

            # Rename snake_case keys that WhiteBit API expects as camelCase.
            for snake, camel in _SNAKE_TO_CAMEL.items():
                if snake in body_dict:
                    body_dict[camel] = body_dict.pop(snake)

            body_dict["request"] = request.url.path
            body_dict["nonce"] = time.time_ns()

            new_body = json.dumps(body_dict, separators=(',', ':')).encode()
            payload = base64.b64encode(new_body).decode()
            signature = _hmac.new(
                self._secret_key.encode(), payload.encode(), hashlib.sha512
            ).hexdigest()

            new_headers = [
                (k, v) for k, v in request.headers.raw
                if k.lower() not in (
                    b"authorization", b"content-type", b"content-length",
                    b"x-txc-apikey", b"x-txc-payload", b"x-txc-signature",
                    b"user-agent",
                )
            ]
            new_headers += [
                (b"x-txc-apikey", self._api_key.encode()),
                (b"x-txc-payload", payload.encode()),
                (b"x-txc-signature", signature.encode()),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(new_body)).encode()),
                (b"user-agent", self._ua_for(request)),
            ]
            request = httpx.Request(
                method=request.method,
                url=request.url,
                headers=new_headers,
                content=new_body,
                extensions=request.extensions,
            )

        else:
            new_headers = [(k, v) for k, v in request.headers.raw if k.lower() != b"user-agent"]
            new_headers.append((b"user-agent", self._ua_for(request)))
            try:
                body = request.content
            except httpx.RequestNotRead:
                body = b""
            request = httpx.Request(
                method=request.method,
                url=request.url,
                headers=new_headers,
                content=body,
                extensions=request.extensions,
            )

        return await self._inner.handle_async_request(request)

    async def aclose(self):
        await self._inner.aclose()


class MCPAuthMiddleware:
    """ASGI middleware: enforces Bearer token auth on HTTP MCP endpoint.

    Set MCP_AUTH_TOKEN env var to enable. If unset, middleware is a no-op
    (stdio transport ignores it entirely).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._token = os.environ.get("MCP_AUTH_TOKEN", "")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and self._token:
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode()
            expected = f"Bearer {self._token}"
            if not secrets.compare_digest(auth, expected):
                if scope["type"] == "http":
                    await send({"type": "http.response.start", "status": 401,
                                "headers": [(b"content-type", b"application/json")]})
                    await send({"type": "http.response.body", "body": b'{"error":"Unauthorized"}'})
                return
        await self.app(scope, receive, send)


class _NoAuthClientWrapper(AsyncClientWrapper):
    """AsyncClientWrapper that omits the Authorization header (for OAuth2 exchange endpoints)."""

    def get_headers(self) -> dict:
        return {"X-Fern-Language": "Python", "X-TXC-APIKEY": self._txc_apikey}


mcp = FastMCP("whitebit-mcp", host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("MCP_PORT", "8000")))


def _make_tool(subclient_attr: str | None, method_name: str, original_sig: inspect.Signature):
    is_account_endpoint = subclient_attr == "account_endpoints"
    is_authentication = subclient_attr == "authentication"
    is_financial = method_name in _FINANCIAL_METHODS

    orig_params = [
        p.replace(kind=inspect.Parameter.KEYWORD_ONLY, default=None)
        if p.default is OMIT
        else p.replace(kind=inspect.Parameter.KEYWORD_ONLY)
        for name, p in original_sig.parameters.items()
        if name not in ("self", "request_options") and name not in _HMAC_FIELDS
    ]
    needs_hmac_fields = {
        name for name in original_sig.parameters
        if name in _HMAC_FIELDS
    }

    if is_financial:
        orig_params.append(inspect.Parameter(
            "confirmed",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=False,
            annotation=bool,
        ))

    new_sig = original_sig.replace(parameters=orig_params)

    async def tool(**kwargs):
        api_key, secret_key = _get_credentials()
        bearer_token = _get_bearer_token()

        needs_hmac = not is_authentication and not is_account_endpoint
        if not api_key or (needs_hmac and not secret_key):
            raise RuntimeError(
                "❌ Credentials not configured. "
                "HTTP transport: set X-WB-Api-Key / X-WB-Secret-Key request headers. "
                "stdio transport: set WHITEBIT_API_KEY / WHITEBIT_SECRET_KEY env vars."
            )
        if is_account_endpoint and not bearer_token:
            raise RuntimeError(
                "❌ account_endpoints require a bearer_token (OAuth2 access token). "
                "HTTP transport: set X-WB-Bearer-Token request header. "
                "stdio transport: set WHITEBIT_BEARER_TOKEN env var."
            )

        if is_financial:
            confirmed = kwargs.pop("confirmed", False)
            if not confirmed:
                return {
                    "status": "preview",
                    "message": (
                        "⚠️ This is a financial action that has NOT been executed. "
                        "Show the user the parameters below and ask for explicit approval. "
                        "Call this tool again with confirmed=True only after the user approves."
                    ),
                    "tool": method_name,
                    "parameters": {k: v for k, v in kwargs.items() if v is not None},
                }

        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        for field in needs_hmac_fields:
            cleaned.setdefault(field, "auto")

        _masked_key = (api_key[:4] + "…" + api_key[-4:]) if len(api_key) > 8 else "****"
        _log.info("tool_call tool=%s key=%s params=%s", method_name, _masked_key, _mask_log_params(cleaned))

        try:
            if subclient_attr is None:
                transport = WhitebitHmacTransport(api_key=api_key, secret_key=secret_key)
                async with httpx.AsyncClient(transport=transport) as hmac_client:
                    obj = AsyncWhitebitApi(
                        txc_apikey=api_key, token="unused",
                        environment=_get_environment(), httpx_client=hmac_client,
                    )
                    result = await getattr(obj, method_name)(**cleaned)
            elif is_account_endpoint:
                async with httpx.AsyncClient() as plain_client:
                    wrapper = AsyncClientWrapper(
                        txc_apikey=api_key, token=bearer_token,
                        environment=_get_environment(), httpx_client=plain_client,
                    )
                    obj = AsyncAccountEndpointsClient(client_wrapper=wrapper)
                    result = await getattr(obj, method_name)(**cleaned)
            elif is_authentication:
                async with httpx.AsyncClient() as plain_client:
                    wrapper = _NoAuthClientWrapper(
                        txc_apikey=api_key, token="unused",
                        environment=_get_environment(), httpx_client=plain_client,
                    )
                    obj = AsyncAuthenticationClient(client_wrapper=wrapper)
                    result = await getattr(obj, method_name)(**cleaned)
            else:
                transport = WhitebitHmacTransport(api_key=api_key, secret_key=secret_key)
                async with httpx.AsyncClient(transport=transport) as hmac_client:
                    wrapper = AsyncClientWrapper(
                        txc_apikey=api_key, token="unused",
                        environment=_get_environment(), httpx_client=hmac_client,
                    )
                    subclient_cls = SUBCLIENT_CLASSES[subclient_attr]
                    obj = subclient_cls(client_wrapper=wrapper)
                    result = await getattr(obj, method_name)(**cleaned)
            _log.info("tool_ok tool=%s", method_name)
            return _sanitize(_to_serializable(result))
        except RuntimeError:
            _log.warning("tool_error tool=%s error=RuntimeError", method_name)
            raise
        except Exception as exc:
            _log.warning("tool_error tool=%s error=%s", method_name, type(exc).__name__)
            if _is_credentials_error(exc):
                raise RuntimeError(
                    f"❌ WhiteBIT API auth/request error: {exc}"
                ) from None
            raise

    tool.__name__ = method_name
    tool.__signature__ = new_sig
    return tool


def register_whitebit_tools():
    for name in _TOP_LEVEL_METHODS:
        method = getattr(AsyncWhitebitApi, name)
        fn = _make_tool(None, name, inspect.signature(method))
        fn.__doc__ = method.__doc__
        mcp.tool(name=name, description=_clean_description(method.__doc__))(fn)

    for attr_name, subclient_cls in SUBCLIENT_CLASSES.items():
        for method_name, method in inspect.getmembers(subclient_cls, predicate=inspect.isfunction):
            if method_name.startswith("_"):
                continue
            tool_name = f"{attr_name}__{method_name}"
            fn = _make_tool(attr_name, method_name, inspect.signature(method))
            fn.__doc__ = method.__doc__
            description = _clean_description(method.__doc__)
            if attr_name == "account_endpoints":
                description = "⚠️ Requires bearer token (call authentication__get_access_token first). " + description
            if method_name in _FINANCIAL_METHODS:
                description = _FINANCIAL_DESCRIPTION_PREFIX + description
            mcp.tool(name=tool_name, description=description)(fn)


register_whitebit_tools()


@mcp.tool(
    name="get_credentials_status",
    description="Check whether WhiteBit API credentials are configured by echoing masked values.",
)
async def get_credentials_status() -> str:
    api_key, secret_key = _get_credentials()
    base_url = os.environ.get("WHITEBIT_BASE_URL", "https://whitebit.com")
    if api_key and secret_key:
        masked_key = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
        masked_secret = "****" + secret_key[-4:] if len(secret_key) > 4 else "****"
        return (
            f"✅ Credentials configured.\n"
            f"   API key:    {masked_key}\n"
            f"   Secret key: {masked_secret}\n"
            f"   Base URL:   {base_url}"
        )
    return (
        "❌ Credentials not configured. "
        "HTTP transport: set X-WB-Api-Key / X-WB-Secret-Key request headers. "
        "stdio transport: set WHITEBIT_API_KEY / WHITEBIT_SECRET_KEY env vars."
    )


@mcp.tool(
    name="whitebit_guide",
    description="Start here. Returns a concise guide: account types, which tools to use for common tasks, and how authentication works.",
)
async def whitebit_guide() -> str:
    return """\
# WhiteBit MCP — quick reference

## Account types
WhiteBit has three separate wallets. Always clarify which one the user means:

| Account | What it's for | Balance tool |
|---------|--------------|--------------|
| **Main account** | Deposits, withdrawals, fiat | `main_account__get_main_balance` |
| **Trade (spot) account** | Spot trading | `spot_trading__trade_account_balance` |
| **Collateral account** | Margin / futures trading | `collateral_trading__collateral_account_balance` |

Funds do NOT move between accounts automatically — use `transfer__between_balances` to move them.

## Common tasks

**Check balance**
- Spot: `spot_trading__trade_account_balance`
- Main: `main_account__get_main_balance`
- Collateral: `collateral_trading__collateral_account_balance`

**Place a spot order**
1. `spot_trading__create_limit_order` or `spot_trading__create_market_order`
2. These are financial actions — first call without `confirmed=True` to preview, then confirm with the user, then call again with `confirmed=True`.

**Check open orders**
- `spot_trading__get_active_orders`

**Withdraw funds**
1. `withdraw__create_withdraw` — financial action, requires confirmation.
2. Funds must be in the **main account** first; transfer from trade account if needed.

**Market data (no credentials needed)**
- Price / ticker: `public_api_v4__market_activity`
- Order book: `public_api_v4__orderbook`
- Recent trades: `public_api_v4__recent_trades`

## Authentication

| Tool category | What's needed |
|---------------|--------------|
| `public_api_v4__*` | Nothing — public endpoints |
| All private tools | API key + secret key (set at connection time, not as tool params) |
| `account_endpoints__*` | **Bearer token** — call `authentication__get_access_token` first, then pass the token via `X-WB-Bearer-Token` header (HTTP) or `WHITEBIT_BEARER_TOKEN` env var (stdio) |

## Financial actions — confirmation required
Tools that move money or place orders have a `confirmed` parameter.
- `confirmed=False` (default): returns a preview — no action taken.
- `confirmed=True`: executes. Only set this after the user has explicitly approved.

Affected tools include: all order creation/cancellation, withdrawals, transfers, code operations, lending actions.

## Verify setup
Call `get_credentials_status` to confirm credentials are loaded.
"""


def main() -> None:
    """Entry point for `uvx whitebit-mcp` / `whitebit-mcp` console script (stdio transport).

    Credentials are read from WHITEBIT_API_KEY / WHITEBIT_SECRET_KEY env vars.
    """
    mcp.run()


if __name__ == "__main__":
    starlette_app = mcp.streamable_http_app()
    starlette_app.add_middleware(CredentialsMiddleware)
    starlette_app.add_middleware(MCPAuthMiddleware)
    _host = os.environ.get("MCP_HOST", "127.0.0.1")
    _port = int(os.environ.get("MCP_PORT", "8000"))
    uvicorn.run(starlette_app, host=_host, port=_port)
