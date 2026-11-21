from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from random import random
from time import monotonic

import aiohttp_session
from aiohttp import web
from client_ip import get_client_ip
from request_utils import request_log_fingerprint, safe_log_value
from typedefs import (
    REQUEST_NEW_SESSION_KEY,
    REQUEST_PROFILE_RESTRICTED_KEY,
    REQUEST_RATE_LIMIT_BUCKET_KEY,
)
from users import NotInDbUsers

from lang import LOCALE

log = logging.getLogger(__name__)
Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        log.warning("Invalid %s=%r, using default=%s", name, value, default)
        return default


# Slow-request tracing is intentionally lightweight:
# - only logs errors and slow requests by default
# - excludes long-lived websocket/SSE endpoints unless explicitly enabled
REQUEST_TRACE_SLOW_MS = _env_float("REQUEST_TRACE_SLOW_MS", 500.0)
REQUEST_TRACE_SAMPLE_RATE = _env_float("REQUEST_TRACE_SAMPLE_RATE", 0.0)
REQUEST_TRACE_INCLUDE_LONG_LIVED = os.getenv("REQUEST_TRACE_INCLUDE_LONG_LIVED", "0") == "1"
LONG_LIVED_PREFIXES = (
    "/wsl",
    "/wsr/",
    "/wst",
    "/wss",
    "/api/ongoing",
    "/api/header/subscribe",
    "/notify",
    "/challenge/subscribe",
    "/api/invites/",
    "/api/stream/",
    "/api/bot/game/stream/",
)


def _is_long_lived_path(path: str) -> bool:
    return path.startswith(LONG_LIVED_PREFIXES)


def _should_trace_request(path: str, status: int, duration_ms: float) -> bool:
    if status >= 500:
        return True

    if duration_ms >= REQUEST_TRACE_SLOW_MS:
        if REQUEST_TRACE_INCLUDE_LONG_LIVED:
            return True
        return not _is_long_lived_path(path)

    if REQUEST_TRACE_SAMPLE_RATE <= 0.0:
        return False

    if not REQUEST_TRACE_INCLUDE_LONG_LIVED and _is_long_lived_path(path):
        return False
    return random() < REQUEST_TRACE_SAMPLE_RATE


@web.middleware
async def handle_404(request: web.Request, handler: Handler) -> web.StreamResponse:
    try:
        return await handler(request)
    except web.HTTPException as ex:
        if ex.status == 404:
            # JSON consumers must not receive a full HTML page on a missing resource.
            path = request.path
            if path.startswith("/api/") or (path.startswith("/@/") and path.endswith("/mini")):
                return web.json_response({"error": "Not found"}, status=404)
            # Avoid rendering the whole site for nonexistent pages and scanner traffic.
            return web.Response(
                text=(
                    '<!doctype html><html lang="en"><head>'
                    '<meta charset="utf-8"><meta name="viewport" '
                    'content="width=device-width,initial-scale=1">'
                    "<title>404 · PyChess</title>"
                    "<style>body{font:1.2rem system-ui,sans-serif;max-width:38rem;"
                    "margin:12vh auto;padding:0 1.5rem;color:#333}"
                    "h1{font-size:4rem;margin:0}a{color:#1769aa}</style>"
                    "</head><body><main><h1>404</h1><p>Page not found.</p>"
                    '<p><a href="/">Return to PyChess</a></p></main></body></html>'
                ),
                status=404,
                content_type="text/html",
            )
        # IMPORTANT: re-raise all other HTTP errors
        raise
    except NotInDbUsers:
        return web.HTTPFound("/")
    except asyncio.CancelledError:
        # Prevent emitting endless tracebacks on server shutdown
        return web.Response()


@web.middleware
async def redirect_to_https(request: web.Request, handler: Handler) -> web.StreamResponse:
    # https://help.heroku.com/J2R1S4T8/can-heroku-force-an-application-to-use-ssl-tls
    # https://docs.aiohttp.org/en/stable/web_advanced.html#aiohttp-web-forwarded-support
    if request.headers.get("X-Forwarded-Proto") == "http":
        # request = request.clone(scheme="https")
        url = request.url.with_scheme("https").with_port(None)
        raise web.HTTPPermanentRedirect(url)

    return await handler(request)


@web.middleware
async def set_user_locale(request: web.Request, handler: Handler) -> web.StreamResponse:
    session = await aiohttp_session.get_session(request)
    LOCALE.set(session.get("lang", "en"))
    return await handler(request)


@web.middleware
async def cross_origin_policy_middleware(
    request: web.Request, handler: Handler
) -> web.StreamResponse:
    response = await handler(request)
    if (
        request.path.startswith("/variants")
        or request.path.startswith("/blogs")
        or request.path.startswith("/video")
        or request.path.startswith("/inbox")
        or request.path.startswith("/forum")
    ):
        # Content-heavy pages can embed/link cross-origin resources.
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    else:
        # required to get stockfish.wasm in Firefox
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        if request.match_info.get("gameId") is not None:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Expires"] = "0"
    return response


@web.middleware
async def request_timing_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    started = monotonic()
    status = 500
    try:
        response = await handler(request)
        status = response.status
        return response
    except web.HTTPException as ex:
        status = ex.status
        raise
    except asyncio.CancelledError:
        raise
    except Exception:
        status = 500
        raise
    finally:
        duration_ms = (monotonic() - started) * 1000.0
        path = request.rel_url.path
        if _should_trace_request(path, status, duration_ms):
            request_id = request.headers.get("X-Request-ID", "-")
            client_ip = get_client_ip(request)
            user_agent, referer, http_version, session_cookie = request_log_fingerprint(request)
            profile_restricted = request.get(REQUEST_PROFILE_RESTRICTED_KEY, "-")
            rate_limit_bucket = request.get(REQUEST_RATE_LIMIT_BUCKET_KEY, "-")
            log.warning(
                "request-trace method=%s path=%s status=%s dur_ms=%.1f req_id=%s fwd=%s "
                "ua=%r ref=%r http=%s session_cookie=%s new_session=%s "
                "profile_restricted=%s rl_bucket=%s",
                request.method,
                safe_log_value(path),
                status,
                duration_ms,
                safe_log_value(request_id),
                safe_log_value(client_ip),
                user_agent,
                referer,
                http_version,
                session_cookie,
                request.get(REQUEST_NEW_SESSION_KEY, False),
                profile_restricted,
                safe_log_value(str(rate_limit_bucket)),
            )
