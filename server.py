import base64
import hashlib
import hmac as _hmac
import inspect
import json
import os
import time

import httpx
from mcp.server.fastmcp import FastMCP

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
# Credentials are passed as tool parameters (api_key, secret_key) so that
# the LLM can supply them from conversation context.
# WHITEBIT_BASE_URL remains an env-var-only config (useful for tests).
# account_endpoints use OAuth2 Bearer auth; supply bearer_token to use them.
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

# Credential parameters injected into every tool signature.
_CRED_PARAMS = [
    inspect.Parameter("api_key", kind=inspect.Parameter.KEYWORD_ONLY, annotation=str),
    inspect.Parameter("secret_key", kind=inspect.Parameter.KEYWORD_ONLY, annotation=str),
]

# secret_key as optional — for endpoints that don't use HMAC signing.
_SECRET_KEY_OPTIONAL = inspect.Parameter(
    "secret_key",
    kind=inspect.Parameter.KEYWORD_ONLY,
    annotation=str,
    default="",
)

# Extra bearer_token parameter injected into account_endpoints tools.
_BEARER_PARAM = inspect.Parameter(
    "bearer_token",
    kind=inspect.Parameter.KEYWORD_ONLY,
    annotation=str,
    default="",
)

# HMAC signing fields injected by the transport — stripped from SDK method params.
_HMAC_FIELDS = {"request", "nonce"}

# SDK sends these snake_case keys but WhiteBit API expects camelCase.
_SNAKE_TO_CAMEL = {
    "order_id": "orderId",
    "client_order_id": "clientOrderId",
}

_ENV = None


def _get_environment() -> WhitebitApiEnvironment:
    global _ENV
    if _ENV is None:
        base_url = os.environ.get("WHITEBIT_BASE_URL", "https://whitebit.com")
        _ENV = WhitebitApiEnvironment(
            base=base_url,
            production=WhitebitApiEnvironment.DEFAULT.production,
            eu=WhitebitApiEnvironment.DEFAULT.eu,
        )
    return _ENV


def _is_credentials_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "invalid payload" in msg or "code: 9" in msg


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


class _NoAuthClientWrapper(AsyncClientWrapper):
    """AsyncClientWrapper that omits the Authorization header (for OAuth2 exchange endpoints)."""

    def get_headers(self) -> dict:
        return {"X-Fern-Language": "Python", "X-TXC-APIKEY": self._txc_apikey}


mcp = FastMCP("whitebit-mcp", host="0.0.0.0", port=8000)


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
    # Remember which HMAC fields the method needs so we can inject dummies.
    needs_hmac_fields = {
        name for name in original_sig.parameters
        if name in _HMAC_FIELDS
    }

    # HMAC endpoints need api_key + secret_key.
    # authentication only needs api_key; account_endpoints need api_key + bearer_token.
    _api_key_param = _CRED_PARAMS[0]
    if is_account_endpoint:
        new_sig = original_sig.replace(parameters=[_api_key_param, _SECRET_KEY_OPTIONAL, _BEARER_PARAM] + orig_params)
    elif is_authentication:
        new_sig = original_sig.replace(parameters=[_api_key_param, _SECRET_KEY_OPTIONAL] + orig_params)
    else:
        new_sig = original_sig.replace(parameters=_CRED_PARAMS + orig_params)

    async def tool(**kwargs):
        api_key = kwargs.pop("api_key")
        secret_key = kwargs.pop("secret_key", "")
        bearer_token = kwargs.pop("bearer_token", "")

        needs_hmac = not is_authentication and not is_account_endpoint
        if not api_key or (needs_hmac and not secret_key):
            raise RuntimeError(
                "❌ api_key and secret_key must be provided as tool parameters."
                if needs_hmac else
                "❌ api_key must be provided as tool parameter."
            )
        if is_account_endpoint and not bearer_token:
            raise RuntimeError(
                "❌ account_endpoints require a bearer_token (OAuth2 access token). "
                "Obtain one via authentication__get_access_token first."
            )

        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        # Inject dummy values for HMAC signing fields — transport overwrites them.
        for field in needs_hmac_fields:
            cleaned.setdefault(field, "auto")

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
                    f"❌ WhiteBit API auth/request error: {exc}"
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
    description="Check whether WhiteBit API credentials are valid by echoing masked values.",
)
async def get_credentials_status(api_key: str, secret_key: str) -> str:
    base_url = os.environ.get("WHITEBIT_BASE_URL", "https://whitebit.com")
    if api_key and secret_key:
        masked_key = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
        masked_secret = "****" + secret_key[-4:] if len(secret_key) > 4 else "****"
        return (
            f"✅ Credentials provided.\n"
            f"   API key:    {masked_key}\n"
            f"   Secret key: {masked_secret}\n"
            f"   Base URL:   {base_url}"
        )
    return "❌ api_key and/or secret_key not provided."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
