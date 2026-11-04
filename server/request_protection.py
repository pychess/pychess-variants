from __future__ import annotations

import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import NoReturn

import aiohttp_session
from aiohttp import web
from client_ip import get_client_ip
from const import ANON_PREFIX
from request_utils import request_log_fingerprint, safe_log_value
from settings import ANON_HTML_MAX_INFLIGHT, ANON_HTML_REQUESTS_PER_MINUTE, LOCALHOST, URI
from typedefs import (
    REQUEST_RATE_LIMIT_BUCKET_KEY,
    request_protection_state_key,
)

log = logging.getLogger(__name__)

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def _mark_rate_limit_bucket(request: web.Request, bucket: str) -> None:
    current = request.get(REQUEST_RATE_LIMIT_BUCKET_KEY)
    if not isinstance(current, str) or not current:
        request[REQUEST_RATE_LIMIT_BUCKET_KEY] = bucket
        return

    buckets = current.split(",")
    if bucket not in buckets:
        request[REQUEST_RATE_LIMIT_BUCKET_KEY] = f"{current},{bucket}"


@dataclass(frozen=True)
class RouteRateLimit:
    """Simple per-route-group limit definition."""

    name: str
    max_requests: int
    window_seconds: float


class SlidingWindowLimiter:
    """
    Lightweight in-memory limiter suitable for single-dyno deployments.

    We intentionally keep this tiny and dependency-free:
    - O(1)-ish operations per request (deque append/pop)
    - bounded map size to protect low-memory dynos
    - periodic stale-key cleanup to avoid unbounded growth
    """

    def __init__(self, max_keys: int = 20_000, cleanup_interval_seconds: float = 15.0) -> None:
        self._events: dict[str, deque[float]] = {}
        self._expires_at: dict[str, float] = {}
        self._max_keys = max_keys
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._last_cleanup = 0.0

    def allow(self, key: str, max_requests: int, window_seconds: float) -> bool:
        now = monotonic()
        self._cleanup_if_needed(now)

        events = self._events.get(key)
        if events is None:
            if len(self._events) >= self._max_keys:
                self._cleanup(now)
                # If still full, fail open for this request.
                # Keeping gameplay available is preferable to a memory-driven outage.
                if len(self._events) >= self._max_keys:
                    return True
            events = deque()
            self._events[key] = events

        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= max_requests:
            return False

        events.append(now)
        self._expires_at[key] = now + window_seconds
        return True

    def _cleanup_if_needed(self, now: float) -> None:
        if now - self._last_cleanup >= self._cleanup_interval_seconds:
            self._cleanup(now)

    def _cleanup(self, now: float) -> None:
        # Cleanup cadence is not the rate window. Removing a bucket after only
        # 15 idle seconds would silently reset a 30/60/120-second budget.
        for key, events in tuple(self._events.items()):
            if not events or self._expires_at.get(key, now) <= now:
                del self._events[key]
                self._expires_at.pop(key, None)
        self._last_cleanup = now


class RequestProtectionState:
    """
    Central request protection state.

    This intentionally combines:
    1) early scanner-path suppression (standalone aiohttp equivalent of an edge deny-list)
    2) app-level per-route-group rate limits for DB-touching endpoints
    """

    _SCANNER_PREFIXES = (
        "/wp-admin",
        "/wp-content",
        "/xmlrpc.php",
        "/phpmyadmin",
        "/cgi-bin",
        "/vendor/phpunit",
        "/.env",
        "/boaform",
        "/HNAP1",
    )

    _PROFILE_LIMIT = RouteRateLimit("profile", max_requests=40, window_seconds=30.0)
    # Distributed crawlers can evade a per-IP budget by using one address per
    # request. Keep a second, application-wide admission budget for anonymous
    # profile rendering, plus a hard cap on concurrently executing profiles.
    _ANON_PROFILE_GLOBAL_LIMIT = RouteRateLimit(
        "anon_profile_global", max_requests=120, window_seconds=60.0
    )
    _ANON_PROFILE_MAX_INFLIGHT = 30
    _ANON_HTML_IP_LIMIT = RouteRateLimit("anon_html", max_requests=30, window_seconds=30.0)
    _ANON_HTML_GLOBAL_LIMIT = RouteRateLimit(
        "anon_html_global", max_requests=ANON_HTML_REQUESTS_PER_MINUTE, window_seconds=60.0
    )
    _ANON_HTML_MAX_INFLIGHT = ANON_HTML_MAX_INFLIGHT
    # Match resolved route templates, not Accept/UA/Referer headers or arbitrary
    # URL prefixes. APIs, static files, auth, streams, game views, and live
    # tournament/simul/Study pages must not compete for this browsing budget.
    _ANON_HTML_ROUTES = frozenset(
        {
            "/",
            "/about",
            "/authors",
            "/contact",
            "/terms",
            "/privacy",
            "/faq",
            "/stats",
            "/players",
            "/allplayers",
            "/calendar",
            "/features",
            "/friendly-sites",
            "/forum",
            "/blogs",
            "/video",
            "/variants",
            "/tournaments",
            "/simul",
            "/simuls",
            "/team",
            "/patron",
            "/patron/thanks",
            "/level8win",
            "/memory",
            "/practice",
            "/practice/{variant}",
            "/study",
            "/study/all",
            "/study/member",
            "/study/likes",
            "/study/public",
            "/study/private",
            "/study/search",
            "/study/topic",
            "/study/topic/{topic}",
            "/study/by/{username}",
        }
    )
    _ANON_HTML_ROUTE_PREFIXES = (
        "/analysis/",
        "/editor/",
        "/variants/",
        "/blogs/",
        "/video/",
        "/forum/",
        "/players/",
        "/page/",
        "/team/",
        "/tournaments/",
    )
    _NEW_ANON_IDENTITY_LIMIT = RouteRateLimit(
        "new_anon_identity", max_requests=10, window_seconds=1.0
    )
    _LOCAL_DEV_NEW_ANON_IDENTITY_LIMIT = RouteRateLimit(
        "new_anon_identity", max_requests=1000, window_seconds=1.0
    )
    _WS_HANDSHAKE_LIMIT = RouteRateLimit("wsr", max_requests=80, window_seconds=30.0)
    _NAMES_LIMIT = RouteRateLimit("names", max_requests=20, window_seconds=30.0)
    _STATUS_LIMIT = RouteRateLimit("status", max_requests=20, window_seconds=30.0)
    _PROFILE_API_LIMIT = RouteRateLimit("profile_api", max_requests=30, window_seconds=30.0)
    # PGN export is expensive enough to warrant a much tighter shared budget
    # than normal page/API traffic on low-memory dynos.
    _EXPORT_LIMIT = RouteRateLimit("export", max_requests=2, window_seconds=120.0)
    _GAME_VIEW_LIMIT = RouteRateLimit("game_view", max_requests=45, window_seconds=30.0)
    # Local stress/smoke runs can legitimately open many websockets and game views
    # from a single IP, so apply far higher local budgets there only.
    _LOCAL_DEV_WS_HANDSHAKE_LIMIT = RouteRateLimit("wsr", max_requests=1000, window_seconds=30.0)
    _LOCAL_DEV_GAME_VIEW_LIMIT = RouteRateLimit("game_view", max_requests=2000, window_seconds=30.0)
    _PUZZLE_LIMIT = RouteRateLimit("puzzle", max_requests=30, window_seconds=30.0)
    _STATIC_API_SEGMENTS = frozenset(
        {
            "account",
            "stream",
            "bot",
            "blocks",
            "calendar",
            "stats",
            "games",
            "users",
            "invites",
            "ongoing",
            "inbox",
            "names",
            "challenge",
            "check-username",
            "confirm-username",
            "token",
        }
    )

    _BLOCK_LOG_MAX_KEYS = 20_000
    _BLOCK_LOG_RETENTION_SECONDS = 60.0
    _BLOCK_LOG_CLEANUP_INTERVAL_SECONDS = 15.0

    def __init__(self) -> None:
        self._limiter = SlidingWindowLimiter()
        self._last_block_log: dict[str, float] = {}
        self._last_block_log_cleanup = 0.0
        self._local_dev_mode = URI == LOCALHOST
        self._anonymous_profile_inflight = 0
        self._anonymous_html_inflight = 0
        # A fixed global deque cannot fail open when per-IP keys reach capacity,
        # and its full window is preserved even after an idle cleanup interval.
        self._anonymous_html_events: deque[float] = deque()

    def classify(self, path: str) -> RouteRateLimit | None:
        # Keep checks cheap and explicit; this runs on every request.
        if path.startswith("/@/"):
            return self._PROFILE_LIMIT
        if path.startswith("/wsr/"):
            if self._local_dev_mode:
                return self._LOCAL_DEV_WS_HANDSHAKE_LIMIT
            return self._WS_HANDSHAKE_LIMIT
        if path == "/api/names":
            return self._NAMES_LIMIT
        if path == "/api/users/status":
            return self._STATUS_LIMIT
        if path.startswith("/api/games/user/"):
            if path.endswith("/pgn"):
                return self._EXPORT_LIMIT
            return self._PROFILE_API_LIMIT
        if path.startswith("/api/"):
            parts = path.split("/")
            # Dynamic user-centric endpoints use "/api/{profileId}/...". Those
            # can still produce avoidable work (DB checks or deliberate sleeps)
            # on random profile probes and should be throttled more aggressively
            # than static API endpoints.
            if len(parts) >= 4 and parts[2] not in self._STATIC_API_SEGMENTS:
                return self._PROFILE_API_LIMIT
        if path.startswith(("/invite/", "/embed/", "/study/embed/", "/corranalysis/")):
            if self._local_dev_mode:
                return self._LOCAL_DEV_GAME_VIEW_LIMIT
            return self._GAME_VIEW_LIMIT
        if path.startswith("/puzzle/"):
            return self._PUZZLE_LIMIT
        # Game page dynamic route: "/{gameId}" where gameId is 8 chars.
        # We require at least one digit or uppercase letter to avoid matching
        # fixed lowercase routes like "/analysis" or "/calendar".
        if len(path) == 9 and path[0] == "/":
            game_id_candidate = path[1:]
            if game_id_candidate.replace("_", "a").isalnum() and (
                any(ch.isdigit() for ch in game_id_candidate)
                or any(ch.isupper() for ch in game_id_candidate)
            ):
                if self._local_dev_mode:
                    return self._LOCAL_DEV_GAME_VIEW_LIMIT
                return self._GAME_VIEW_LIMIT
        return None

    def is_known_scanner_path(self, path: str) -> bool:
        lowered = path.lower()
        return any(lowered.startswith(prefix.lower()) for prefix in self._SCANNER_PREFIXES)

    def client_key(self, request: web.Request) -> str:
        return get_client_ip(request) or "unknown"

    def should_log_block(self, key: str) -> bool:
        now = monotonic()
        self._cleanup_block_log_if_needed(now)
        prev = self._last_block_log.get(key, 0.0)
        if now - prev < 30.0:
            return False
        self._last_block_log[key] = now
        return True

    def _cleanup_block_log_if_needed(self, now: float) -> None:
        cleanup_due = now - self._last_block_log_cleanup >= self._BLOCK_LOG_CLEANUP_INTERVAL_SECONDS
        at_capacity = len(self._last_block_log) >= self._BLOCK_LOG_MAX_KEYS
        if not cleanup_due and not at_capacity:
            return

        cutoff = now - self._BLOCK_LOG_RETENTION_SECONDS
        for key, logged_at in tuple(self._last_block_log.items()):
            if logged_at <= cutoff:
                del self._last_block_log[key]

        if len(self._last_block_log) >= self._BLOCK_LOG_MAX_KEYS:
            # Shed a batch so a scanner flood does not force an O(n) eviction
            # for every subsequent unique address.
            target_size = max(1, self._BLOCK_LOG_MAX_KEYS * 9 // 10)
            remove_count = len(self._last_block_log) - target_size
            oldest = sorted(self._last_block_log, key=self._last_block_log.__getitem__)
            for key in oldest[:remove_count]:
                del self._last_block_log[key]

        self._last_block_log_cleanup = now

    def allow(self, key: str, route_limit: RouteRateLimit) -> bool:
        return self._limiter.allow(key, route_limit.max_requests, route_limit.window_seconds)

    def is_anonymous_profile_request(self, request: web.Request, session_user: str | None) -> bool:
        return (
            request.method in {"GET", "HEAD"}
            and request.path.startswith("/@/")
            and (session_user is None or session_user.startswith(ANON_PREFIX))
        )

    def is_public_browsing_request(self, request: web.Request) -> bool:
        if request.method not in {"GET", "HEAD"}:
            return False
        resource = request.match_info.route.resource
        if resource is None:
            return False
        route = resource.canonical
        return route in self._ANON_HTML_ROUTES or route.startswith(self._ANON_HTML_ROUTE_PREFIXES)

    def enter_anonymous_html(self, client: str | None = None) -> tuple[bool, str | None]:
        if self._anonymous_html_inflight >= self._ANON_HTML_MAX_INFLIGHT:
            return False, "concurrency"

        now = monotonic()
        route_limit = self._ANON_HTML_GLOBAL_LIMIT
        cutoff = now - route_limit.window_seconds
        events = self._anonymous_html_events
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= route_limit.max_requests:
            return False, "rate"
        # Check the fixed-size global budget first. A distributed flood already
        # rejected there must not allocate a per-IP bucket or trigger map cleanup.
        if client is not None and not self.allow(
            f"{self._ANON_HTML_IP_LIMIT.name}:{client}", self._ANON_HTML_IP_LIMIT
        ):
            return False, "ip_rate"
        events.append(now)
        self._anonymous_html_inflight += 1
        return True, None

    def leave_anonymous_html(self) -> None:
        if self._anonymous_html_inflight > 0:
            self._anonymous_html_inflight -= 1

    def enter_anonymous_profile(self) -> tuple[bool, str | None]:
        if self._anonymous_profile_inflight >= self._ANON_PROFILE_MAX_INFLIGHT:
            return False, "concurrency"

        route_limit = self._ANON_PROFILE_GLOBAL_LIMIT
        if not self.allow(route_limit.name, route_limit):
            return False, "rate"

        self._anonymous_profile_inflight += 1
        return True, None

    def leave_anonymous_profile(self) -> None:
        if self._anonymous_profile_inflight > 0:
            self._anonymous_profile_inflight -= 1

    def allow_new_anonymous_identity(self) -> bool:
        route_limit = (
            self._LOCAL_DEV_NEW_ANON_IDENTITY_LIMIT
            if self._local_dev_mode
            else self._NEW_ANON_IDENTITY_LIMIT
        )
        return self.allow(route_limit.name, route_limit)


def enforce_new_anonymous_identity_limit(request: web.Request) -> None:
    state: RequestProtectionState = request.app[request_protection_state_key]
    bucket = state._NEW_ANON_IDENTITY_LIMIT.name
    _mark_rate_limit_bucket(request, bucket)
    if state.allow_new_anonymous_identity():
        return

    client = state.client_key(request)
    if state.should_log_block(f"{bucket}:{client}"):
        user_agent, referer, http_version, session_cookie = request_log_fingerprint(request)
        log.warning(
            "rate-limited new anonymous identity from %s at path %s "
            "ua=%r ref=%r http=%s session_cookie=%s bucket=%s",
            safe_log_value(client),
            safe_log_value(request.path),
            user_agent,
            referer,
            http_version,
            session_cookie,
            bucket,
        )
    raise web.HTTPTooManyRequests(headers={"Retry-After": "1"})


def _enforce_route_rate_limit(
    request: web.Request, state: RequestProtectionState, client: str, route_limit: RouteRateLimit
) -> None:
    _mark_rate_limit_bucket(request, route_limit.name)
    bucket = f"{route_limit.name}:{client}"
    if state.allow(bucket, route_limit):
        return
    _reject_route_rate_limit(request, state, client, route_limit)


def _reject_route_rate_limit(
    request: web.Request, state: RequestProtectionState, client: str, route_limit: RouteRateLimit
) -> NoReturn:
    bucket = f"{route_limit.name}:{client}"
    if state.should_log_block(bucket):
        user_agent, referer, http_version, session_cookie = request_log_fingerprint(request)
        log.warning(
            "rate-limited %s from %s at path %s (%s req / %ss) "
            "ua=%r ref=%r http=%s session_cookie=%s bucket=%s",
            route_limit.name,
            safe_log_value(client),
            safe_log_value(request.path),
            route_limit.max_requests,
            route_limit.window_seconds,
            user_agent,
            referer,
            http_version,
            session_cookie,
            route_limit.name,
        )
    retry_after = max(1, int(route_limit.window_seconds))
    raise web.HTTPTooManyRequests(
        headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"}
    )


@web.middleware
async def request_protection_middleware(
    request: web.Request, handler: Handler
) -> web.StreamResponse:
    # Heroku hobby deploys run aiohttp standalone without nginx/caddy in front.
    # This middleware acts as an in-app "edge-like" fast filter:
    # - drop obvious scanner paths early
    # - apply route-group limits before session/db-heavy handlers run
    state: RequestProtectionState = request.app[request_protection_state_key]
    path = request.path
    client = state.client_key(request)

    if state.is_known_scanner_path(path):
        _mark_rate_limit_bucket(request, "scanner")
        scanner_key = f"scanner:{client}"
        if not state._limiter.allow(scanner_key, max_requests=8, window_seconds=60.0):
            if state.should_log_block(scanner_key):
                user_agent, referer, http_version, session_cookie = request_log_fingerprint(request)
                log.warning(
                    "scanner path flood blocked from %s on %s "
                    "ua=%r ref=%r http=%s session_cookie=%s bucket=scanner",
                    safe_log_value(client),
                    safe_log_value(path),
                    user_agent,
                    referer,
                    http_version,
                    session_cookie,
                )
            raise web.HTTPTooManyRequests(headers={"Retry-After": "60"})
        # Return 404 for scanner signatures to avoid signaling valid app routes.
        raise web.HTTPNotFound()

    route_limit = state.classify(path)
    browsing_request = state.is_public_browsing_request(request)
    if route_limit is None and not browsing_request:
        return await handler(request)

    if route_limit is not None:
        _enforce_route_rate_limit(request, state, client, route_limit)

    session = await aiohttp_session.get_session(request)
    session_user_value = session.get("user_name")
    session_user = session_user_value if isinstance(session_user_value, str) else None
    if state.is_anonymous_profile_request(request, session_user):
        global_limit = state._ANON_PROFILE_GLOBAL_LIMIT
        admitted, reason = state.enter_anonymous_profile()
        inflight = state._anonymous_profile_inflight
        max_inflight = state._ANON_PROFILE_MAX_INFLIGHT
        leave = state.leave_anonymous_profile
        kind = "profile"
    elif browsing_request and (session_user is None or session_user.startswith(ANON_PREFIX)):
        _mark_rate_limit_bucket(request, state._ANON_HTML_IP_LIMIT.name)
        global_limit = state._ANON_HTML_GLOBAL_LIMIT
        admitted, reason = state.enter_anonymous_html(client)
        if reason == "ip_rate":
            _reject_route_rate_limit(request, state, client, state._ANON_HTML_IP_LIMIT)
        inflight = state._anonymous_html_inflight
        max_inflight = state._ANON_HTML_MAX_INFLIGHT
        leave = state.leave_anonymous_html
        kind = "HTML"
    else:
        return await handler(request)

    _mark_rate_limit_bucket(request, global_limit.name)
    if not admitted:
        aggregate_bucket = f"{global_limit.name}:{reason}"
        if state.should_log_block(aggregate_bucket):
            user_agent, referer, http_version, session_cookie = request_log_fingerprint(request)
            log.warning(
                "rate-limited anonymous %s traffic reason=%s from %s at path %s "
                "(inflight=%s max_inflight=%s) ua=%r ref=%r http=%s "
                "session_cookie=%s bucket=%s",
                kind,
                reason,
                safe_log_value(client),
                safe_log_value(path),
                inflight,
                max_inflight,
                user_agent,
                referer,
                http_version,
                session_cookie,
                global_limit.name,
            )
        retry_after = max(1, int(global_limit.window_seconds)) if reason == "rate" else 1
        raise web.HTTPTooManyRequests(
            headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"}
        )

    try:
        return await handler(request)
    finally:
        leave()
