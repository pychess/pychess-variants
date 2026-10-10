from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

import aiohttp_session
from aiohttp import web

CSRF_FORM_FIELD = "_csrf_token"
CSRF_HEADER = "X-CSRF-Token"
CSRF_SESSION_KEY = "csrf_token"
SESSION_COOKIE_NAME = "AIOHTTP_SESSION"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
ALLOW_ORIGINLESS_LOOPBACK_KEY = web.AppKey("csrf_allow_originless_loopback", bool)

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def csrf_exempt[HandlerT: Callable[..., Any]](handler: HandlerT) -> HandlerT:
    """Mark a route as independently authenticated and not browser-session CSRF protected."""

    setattr(handler, "__csrf_exempt__", True)  # noqa: B010
    return handler


def ensure_csrf_token(session: Any) -> str:
    token = session.get(CSRF_SESSION_KEY)
    if isinstance(token, str) and token:
        return token

    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token


def _normalized_origin(value: str | None) -> str | None:
    if value is None or value == "null":
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or host is None:
        return None

    host = host.lower()
    if (parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443):
        port = None
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    authority = host if port is None else f"{host}:{port}"
    return f"{parsed.scheme.lower()}://{authority}"


def _request_origin(request: web.Request) -> str | None:
    # Heroku terminates TLS before aiohttp, so the public scheme is supplied by
    # X-Forwarded-Proto while Host remains the public host.
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").split(",", maxsplit=1)[0].strip()
    scheme = forwarded_proto or request.scheme
    return _normalized_origin(f"{scheme}://{request.host}")


def _same_origin(request: web.Request, value: str | None) -> bool:
    supplied = _normalized_origin(value)
    expected = _request_origin(request)
    return supplied is not None and expected is not None and supplied == expected


def _same_origin_referer(request: web.Request, value: str | None) -> bool:
    if value is None:
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or parsed.netloc == "":
        return False
    return _same_origin(request, f"{parsed.scheme}://{parsed.netloc}")


def _is_loopback_request(request: web.Request) -> bool:
    if not request.app.get(ALLOW_ORIGINLESS_LOOPBACK_KEY, False):
        return False
    try:
        host = urlsplit(f"//{request.host}").hostname
    except ValueError:
        return False
    return host in {"127.0.0.1", "::1", "localhost"} and request.remote in {"127.0.0.1", "::1"}


def _route_is_exempt(request: web.Request) -> bool:
    handler = getattr(request.match_info, "handler", None)
    return bool(getattr(handler, "__csrf_exempt__", False))


async def _provided_csrf_token(request: web.Request) -> str | None:
    header_token = request.headers.get(CSRF_HEADER)
    if header_token:
        return header_token

    content_type = request.content_type.lower()
    if content_type not in {
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }:
        return None

    try:
        post_data = await request.post()
    except (ValueError, UnicodeDecodeError):
        return None
    form_token = post_data.get(CSRF_FORM_FIELD)
    return form_token if isinstance(form_token, str) and form_token else None


def _forbidden() -> web.HTTPForbidden:
    return web.HTTPForbidden(text="CSRF validation failed")


@web.middleware
async def csrf_protection_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Protect browser-session mutations from cross-site requests.

    Independently authenticated machine routes opt out explicitly. For cookie-
    authenticated browser requests, Fetch Metadata and Origin/Referer provide an
    early same-origin boundary. A session-bound token is the fallback when those
    headers are absent, so privacy tools that strip Referer do not require a
    fail-open policy.
    """

    # WebSocket handshakes use GET but authorize later mutations. Browsers
    # always supply Origin; require an exact match even for anonymous sockets.
    if request.headers.get("Upgrade", "").lower() == "websocket":
        if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site" or not _same_origin(
            request, request.headers.get("Origin")
        ):
            raise _forbidden()
        return await handler(request)

    if request.method in SAFE_METHODS or _route_is_exempt(request):
        return await handler(request)

    # Requests without a pre-existing browser session carry no ambient session
    # authority. Handlers may still create an anonymous session themselves.
    if SESSION_COOKIE_NAME not in request.cookies:
        return await handler(request)

    session = await aiohttp_session.get_session(request)
    # Pending OAuth registration and account recovery carry session authority
    # before user_name exists. Protect every nonempty browser session.
    if not session:
        return await handler(request)

    fetch_site = request.headers.get("Sec-Fetch-Site", "").lower()
    if fetch_site == "cross-site":
        raise _forbidden()

    origin = request.headers.get("Origin")
    if origin is not None:
        if not _same_origin(request, origin):
            raise _forbidden()
        return await handler(request)

    referer = request.headers.get("Referer")
    if referer is not None:
        if not _same_origin_referer(request, referer):
            raise _forbidden()
        return await handler(request)

    # Only explicit test/development applications may omit tokens on a loopback
    # connection. A production Host header can never enable this exception.
    if _is_loopback_request(request):
        return await handler(request)

    expected_token = session.get(CSRF_SESSION_KEY)
    provided_token = await _provided_csrf_token(request)
    if (
        not isinstance(expected_token, str)
        or not expected_token
        or provided_token is None
        or not secrets.compare_digest(provided_token, expected_token)
    ):
        raise _forbidden()

    return await handler(request)
