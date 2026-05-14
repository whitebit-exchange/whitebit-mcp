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
    """ASGI middleware: extracts X-WB-Api-Key / X-WB-Secret-Key / X-WB-Bearer-Token headers into ContextVars."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers: dict[bytes, bytes] = dict(scope.get("headers", []))
            _api_key_var.set(headers.get(b"x-wb-api-key", b"").decode())
            _secret_key_var.set(headers.get(b"x-wb-secret-key", b"").decode())
            _bearer_token_var.set(headers.get(b"x-wb-bearer-token", b"").decode())
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

        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        for field in needs_hmac_fields:
            cleaned.setdefault(field, "auto")

        _masked_key = (api_key[:4] + "…" + api_key[-4:]) if len(api_key) > 8 else "****"
        _log.info("tool_call tool=%s key=%s", method_name, _masked_key)

        try:
            if subclient_attr is None:
                transport = WhitebitHmacTransport(api_key=api_key, secret_key=secret_key)
                async with httpx.AsyncClient(transport=transport) as hmac_client:
                    obj = AsyncWhitebitApi(
                        txc_apikey=api_key, token="unused",
                        environment=_get_environment(), httpx_client=hmac_client,
                    )
                    return await getattr(obj, method_name)(**cleaned)
            elif is_account_endpoint:
                async with httpx.AsyncClient() as plain_client:
                    wrapper = AsyncClientWrapper(
                        txc_apikey=api_key, token=bearer_token,
                        environment=_get_environment(), httpx_client=plain_client,
                    )
                    obj = AsyncAccountEndpointsClient(client_wrapper=wrapper)
                    return await getattr(obj, method_name)(**cleaned)
            elif is_authentication:
                async with httpx.AsyncClient() as plain_client:
                    wrapper = _NoAuthClientWrapper(
                        txc_apikey=api_key, token="unused",
                        environment=_get_environment(), httpx_client=plain_client,
                    )
                    obj = AsyncAuthenticationClient(client_wrapper=wrapper)
                    return await getattr(obj, method_name)(**cleaned)
            else:
                transport = WhitebitHmacTransport(api_key=api_key, secret_key=secret_key)
                async with httpx.AsyncClient(transport=transport) as hmac_client:
                    wrapper = AsyncClientWrapper(
                        txc_apikey=api_key, token="unused",
                        environment=_get_environment(), httpx_client=hmac_client,
                    )
                    subclient_cls = SUBCLIENT_CLASSES[subclient_attr]
                    obj = subclient_cls(client_wrapper=wrapper)
                    return await getattr(obj, method_name)(**cleaned)
        except RuntimeError:
            raise
        except Exception as exc:
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
        mcp.tool(name=name, description=(method.__doc__ or "").strip().split("\n")[0])(fn)

    for attr_name, subclient_cls in SUBCLIENT_CLASSES.items():
        for method_name, method in inspect.getmembers(subclient_cls, predicate=inspect.isfunction):
            if method_name.startswith("_"):
                continue
            tool_name = f"{attr_name}__{method_name}"
            fn = _make_tool(attr_name, method_name, inspect.signature(method))
            fn.__doc__ = method.__doc__
            description = (method.__doc__ or "").strip().split("\n")[0]
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
