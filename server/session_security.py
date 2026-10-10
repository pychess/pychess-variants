from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp_session
from aiohttp import web
from const import STARTED, T_STARTED
from pychess_global_app_state_utils import get_app_state
from pymongo import ReturnDocument
from settings import MAX_AGE, SESSION_GAMEPLAY_GRACE

if TYPE_CHECKING:
    from aiohttp.web_ws import WebSocketResponse
    from aiohttp_session import Session
    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
    from tournament.tournament import Tournament
    from user import User

AUTH_VERSION_SESSION_KEY = "auth_version"
AUTH_VERSION_DB_PATH = "security.sessionVersion"
AUTHENTICATED_AT_SESSION_KEY = "authenticated_at"
GAMEPLAY_EXPIRY_GRACE_KEY = web.ResponseKey("gameplay_expiry_grace", bool)

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def auth_version_from_user_document(user_doc: Mapping[str, Any]) -> int:
    security = user_doc.get("security")
    if not isinstance(security, Mapping):
        return 0
    value = security.get("sessionVersion", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def authenticate_session(session: Session, username: str, auth_version: int) -> None:
    session["user_name"] = username
    session[AUTH_VERSION_SESSION_KEY] = auth_version
    session[AUTHENTICATED_AT_SESSION_KEY] = int(datetime.now(UTC).timestamp())


async def revoke_user_sessions(user: User) -> None:
    """Invalidate every browser session previously issued for one registered user.

    Browser sessions are encrypted client-side cookies, so deleting one browser's
    cookie cannot invalidate a copied cookie.  The durable per-user generation is
    stored in Mongo and mirrored on the cached User.  Every authenticated request
    must present the same generation in its encrypted cookie.
    """

    if user.anon:
        return

    version = await revoke_user_sessions_for_username(user.app_state, user.username)
    # In-memory test identities may have no corresponding Mongo document.
    user.auth_version = (
        max(user.auth_version, version) if version is not None else user.auth_version + 1
    )


async def revoke_user_sessions_for_username(
    app_state: PychessGlobalAppState, username: str
) -> int | None:
    """Persist revocation even when the account has no cached User object."""
    if app_state.db is None:
        return None
    doc = await app_state.db.user.find_one_and_update(
        {"_id": username},
        {"$inc": {AUTH_VERSION_DB_PATH: 1}},
        projection={AUTH_VERSION_DB_PATH: 1},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        return None

    version = auth_version_from_user_document(doc)
    # A User may have been loaded during the database await. Also avoid moving
    # its generation backwards if concurrent revocations return out of order.
    cached_user = app_state.users.data.get(username)
    if cached_user is not None:
        cached_user.auth_version = max(cached_user.auth_version, version)
    return version


def _session_auth_version(session: Session) -> int | None:
    value = session.get(AUTH_VERSION_SESSION_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _session_authentication_is_recent(session: Session) -> bool:
    # Legacy cookies have no separate login timestamp. Use their signed creation
    # time rather than granting another full lifetime on first use.
    authenticated_at = session.get(AUTHENTICATED_AT_SESSION_KEY, session.created)
    if type(authenticated_at) is not int:
        return False
    age = int(datetime.now(UTC).timestamp()) - authenticated_at
    return 0 <= age < MAX_AGE


def _session_identity_matches_user(session: Session, user: User) -> bool:
    session_user = session.get("user_name")
    if not isinstance(session_user, str) or session_user != user.username or not user.enabled:
        return False
    if user.anon:
        return True
    return _session_auth_version(session) == user.auth_version


def _gameplay_grace_deadline(session: Session, user: User) -> float | None:
    if user.anon or not _session_identity_matches_user(session, user):
        return None
    authenticated_at = session.get(AUTHENTICATED_AT_SESSION_KEY, session.created)
    if type(authenticated_at) is not int:
        return None
    expiry = authenticated_at + MAX_AGE
    if not expiry <= datetime.now(UTC).timestamp() < expiry + SESSION_GAMEPLAY_GRACE:
        return None
    return expiry


def _existing_tournament_participant(
    tournament: Tournament, user: User, expiry: float, *, allow_withdrawn: bool = False
) -> bool:
    player = tournament.player_data_by_name(user.username)
    return (
        player is not None
        and (allow_withdrawn or not player.withdrawn)
        and player.joined_at.timestamp() < expiry
        and tournament.starts_at.timestamp() < expiry
    )


def _tournament_allows_grace(tournament: Tournament, user: User, expiry: float) -> bool:
    return tournament.status == T_STARTED and _existing_tournament_participant(
        tournament, user, expiry
    )


def _game_allows_grace(game: Game, user: User, expiry: float) -> bool:
    if (
        game.status > STARTED
        or game.corr
        or not any(player.username == user.username for player in game.non_bot_players)
    ):
        return False
    if game.date.timestamp() < expiry:
        return True
    # Later rounds of an already-running tournament also qualify. If the event
    # finishes before its last game, let that game finish as well.
    tournament = user.app_state.tournaments.get(game.tournamentId)
    return tournament is not None and _existing_tournament_participant(
        tournament, user, expiry, allow_withdrawn=True
    )


def session_has_gameplay_grace(session: Session, user: User) -> bool:
    expiry = _gameplay_grace_deadline(session, user)
    if expiry is None:
        return False
    return any(
        _tournament_allows_grace(tournament, user, expiry)
        for tournament in user.app_state.tournaments.values()
    ) or any(_game_allows_grace(game, user, expiry) for game in user.app_state.games.values())


_ROUND_GRACE_MESSAGES = frozenset(
    {
        "move",
        "reconnect",
        "berserk",
        "ready",
        "board",
        "setup",
        "draw",
        "reject_draw",
        "byoyomi",
        "takeback",
        "reject_takeback",
        "abort",
        "resign",
        "abandon",
        "flag",
        "is_user_present",
        "moretime",
        "bugroundchat",
        "roundchat",
        "leave",
        "count",
        "ceval_detected",
        "pong",
        "logout",
        "disconnect",
    }
)
_TOURNAMENT_GRACE_MESSAGES = frozenset(
    {
        "get_players",
        "my_page",
        "get_games",
        "get_rr_arrangements",
        "join",
        "pause",
        "withdraw",
        "tournament_user_connected",
        "rr_challenge",
        "rr_accept_challenge",
        "lobbychat",
        "pong",
        "logout",
        "disconnect",
    }
)


def session_matches_user(
    session: Session,
    user: User,
    *,
    request: web.Request | None = None,
    message: Mapping[str, object] | None = None,
) -> bool:
    """Normal authority expires absolutely; only scoped gameplay gets grace."""
    if not _session_identity_matches_user(session, user):
        return False
    if user.anon or _session_authentication_is_recent(session):
        return True
    expiry = _gameplay_grace_deadline(session, user)
    if expiry is None or request is None:
        return False
    if request.path == "/logout" and request.method == "POST":
        return session_has_gameplay_grace(session, user)
    tournament_id = request.match_info.get("tournamentId")
    if (
        request.method == "POST"
        and tournament_id is not None
        and request.path == f"/tournament/{tournament_id}/pause"
    ):
        tournament = user.app_state.tournaments.get(tournament_id)
        return tournament is not None and _tournament_allows_grace(tournament, user, expiry)
    if request.method != "GET":
        return False
    # Reauthentication must remain available without destroying the cookie
    # needed by a parallel game tab. These routes do not grant account access.
    if request.path == "/login" or request.path.startswith(("/oauth/", "/login/")):
        return session_has_gameplay_grace(session, user)
    # RR's play dialog polls this public, unauthenticated presence endpoint.
    if request.path == "/api/users/status":
        return session_has_gameplay_grace(session, user)
    if message is not None and (
        not isinstance(message.get("type"), str)
        or str(message.get("message", "")).lstrip().startswith(("/", "!"))
    ):
        return False
    game_id = request.match_info.get("gameId")
    if game_id is not None and request.path in {f"/{game_id}", f"/wsr/{game_id}"}:
        game = user.app_state.games.get(game_id)
        return (
            game is not None
            and _game_allows_grace(game, user, expiry)
            and (
                message is None
                or (
                    message.get("type") in _ROUND_GRACE_MESSAGES
                    and message.get("gameId", game_id) == game_id
                )
            )
        )
    if request.path == "/wst":
        if message is None or message.get("type") in {"pong", "logout", "disconnect"}:
            return any(
                _tournament_allows_grace(tournament, user, expiry)
                for tournament in user.app_state.tournaments.values()
            )
        if message.get("type") not in _TOURNAMENT_GRACE_MESSAGES:
            return False
        tournament_id = message.get("tournamentId")
    elif tournament_id is None or request.path != f"/tournament/{tournament_id}":
        return False
    if not isinstance(tournament_id, str):
        return False
    tournament = user.app_state.tournaments.get(tournament_id)
    return tournament is not None and _tournament_allows_grace(tournament, user, expiry)


def session_expiry_timeout(session: Session, user: User) -> asyncio.Timeout:
    """Bound a live connection to its original login lifetime, even while idle.

    The caller must keep connection cleanup outside this timeout. Anonymous
    connections have no registered-account authority and no login deadline.
    """
    if not session_matches_user(session, user):
        raise web.HTTPUnauthorized(text="Session is no longer valid. Please sign in again.")
    remaining = None
    if not user.anon:
        authenticated_at = session.get(AUTHENTICATED_AT_SESSION_KEY, session.created)
        remaining = max(0.0, authenticated_at + MAX_AGE - datetime.now(UTC).timestamp())
    return asyncio.timeout(remaining)


@asynccontextmanager
async def websocket_session_lifetime(
    session: Session, user: User, request: web.Request, ws: WebSocketResponse
):
    """Recheck gameplay at the deadline and while grace is active, even if idle.

    Close the connection instead of cancelling an in-flight move/DB write.
    Per-message checks still enforce scope and immediate revocation.
    """
    if not session_matches_user(session, user, request=request):
        raise web.HTTPUnauthorized(text="Session is no longer valid. Please sign in again.")
    if user.anon:
        yield
        return
    authenticated_at = session.get(AUTHENTICATED_AT_SESSION_KEY, session.created)
    expiry = authenticated_at + MAX_AGE

    async def close_at_expiry() -> None:
        await asyncio.sleep(max(0.0, expiry - datetime.now(UTC).timestamp()))
        while _gameplay_grace_deadline(session, user) is not None and session_matches_user(
            session, user, request=request
        ):
            await asyncio.sleep(
                min(1.0, max(0.0, expiry + SESSION_GAMEPLAY_GRACE - datetime.now(UTC).timestamp()))
            )
        user.authenticated_sockets.discard(ws)
        await ws.close()

    watcher = asyncio.create_task(close_at_expiry(), name="websocket-session-expiry")
    try:
        yield
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)


def _is_websocket_handshake(request: web.Request) -> bool:
    return request.headers.get("Upgrade", "").lower() == "websocket"


@web.middleware
async def session_security_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Reject browser cookies invalidated by logout/account administration.

    Missing auth_version means version 0 for compatibility with cookies issued
    before this mechanism was deployed.  The first logout increments the user's
    durable version, which also invalidates any copied legacy cookie.
    """

    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if not isinstance(session_user, str) or not session_user:
        return await handler(request)

    app_state = get_app_state(request.app)
    user = await app_state.users.get(session_user)

    if not user.anon and AUTHENTICATED_AT_SESSION_KEY not in session:
        # Session.__setitem__ resets created, so pin the original timestamp
        # before views update last_visit or generate a CSRF token.
        session[AUTHENTICATED_AT_SESSION_KEY] = session.created

    if not session_matches_user(session, user, request=request):
        # A background inbox/account request must not delete a still-useful
        # game reconnect cookie. It gets no authenticated authority, however.
        if session_has_gameplay_grace(session, user):
            raise web.HTTPUnauthorized(text="Session expired. Please sign in again.")
        session.invalidate()

        # Do not let an invalid authenticated cookie silently become a fresh
        # anonymous identity on mutations or WebSocket handshakes.
        if request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"} or _is_websocket_handshake(
            request
        ):
            raise web.HTTPUnauthorized(text="Session is no longer valid. Please sign in again.")

    return await handler(request)
