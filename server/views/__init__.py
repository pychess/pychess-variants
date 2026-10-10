from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp_session
from aiohttp import web
from catalogued_variants import (
    catalogued_variant_client_doc_for_game,
    catalogued_variants_for_client,
)
from const import (
    ANON_PREFIX,
    CATEGORY_VARIANT_GROUPS,
    CATEGORY_VARIANT_LISTS,
    CATEGORY_VARIANT_SETS,
    CATEGORY_VARIANTS,
    CREATED,
    DARK_FEN,
    GAME_CATEGORY_ALL,
    HTTP_ANON_USER,
    STARTED,
)
from csrf import ensure_csrf_token
from fairy import BLACK, WHITE
from json_utils import json_dumps
from preferences import (
    apply_anonymous_session_preferences,
    effective_game_category,
    effective_theme,
)
from pychess_global_app_state_utils import get_app_state
from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    ExecutionTimeout,
    NetworkTimeout,
    ServerSelectionTimeoutError,
    WaitQueueTimeoutError,
)
from settings import ADMINS, SIMULING
from typing_defs import UserDocument, ViewContext
from user import User, mint_guest_user
from utils import corr_games, load_game_from_doc
from variants import ALL_VARIANTS

from lang import LOCALE

if TYPE_CHECKING:
    from bug.game_bug import GameBug
    from game import Game

log = logging.getLogger(__name__)


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


REPORT_REASON_SCORES: dict[str, int] = {
    "cheat": 90,
    "cheating": 90,
    "violence": 88,
    "self_harm": 88,
    "hate": 86,
    "harass": 78,
    "harassment": 78,
    "verbal_abuse": 74,
    "spam": 64,
    "stall": 62,
    "boost": 62,
    "bad_behavior": 62,
    "impersonation": 58,
    "username": 56,
    "other": 50,
}


def _report_priority_score(report: Mapping[str, Any]) -> int:
    reason = str(report.get("reason", "")).lower()
    score = REPORT_REASON_SCORES.get(reason, 45)
    if report.get("source") == "inbox":
        score += 4
    if report.get("inquiryBy"):
        score = max(0, score - 6)
    return min(99, score)


async def _max_open_report_score(request: web.Request) -> int:
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return 0
    cursor = app_state.db.user_report.find(
        {"status": "open"}, projection={"reason": 1, "source": 1, "inquiryBy": 1}
    ).limit(400)
    reports = await cursor.to_list(length=400)
    if not reports:
        return 0
    return max(_report_priority_score(report) for report in reports)


piece_css_path: Path = Path(Path(__file__).parent.parent.parent, "static/piece-css")
piece_sets: list[str] = [
    x.name for x in piece_css_path.iterdir() if x.is_dir() and x.name != "mono"
]


async def get_user_context(request: web.Request) -> tuple[User, ViewContext]:
    app_state = get_app_state(request.app)

    # Who made the request?
    session = await aiohttp_session.get_session(request)
    session_user_value = session.get("user_name")
    session_user = session_user_value if isinstance(session_user_value, str) else None
    csrf_token = ensure_csrf_token(session) if session else ""

    if session_user is not None:
        session["last_visit"] = datetime.now(UTC).isoformat()
        log.info("+++ Existing user %s connected.", session_user)
        doc: UserDocument | None = None
        # Anonymous users are in-memory only and are not persisted in db.user.
        # Skip pointless db lookups for Anon-* sessions to reduce Mongo load
        # under heavy anonymous traffic (e.g. stress runs / large spectator spikes).
        if not session_user.startswith(ANON_PREFIX):
            try:
                doc = await app_state.db.user.find_one({"_id": session_user})
            except Exception:
                log.error(
                    "index() app_state.db.user.find_one Exception. Failed to get user %s from mongodb!",
                    session_user,
                )
        if doc is not None and not doc.get("enabled", True):
            log.info("Closed account %s tried to connect.", session_user)
            session.invalidate()
            raise web.HTTPFound("/")

        if session_user in app_state.users:
            user = app_state.users[session_user]
        else:
            user = await app_state.users.get(session_user)

            if not user.enabled:
                session.invalidate()
                raise web.HTTPFound("/")
    else:
        # Ordinary anonymous page views stay stateless. A persistent Anon-*
        # identity is created only when a request can actually perform an
        # anonymous action (non-GET) or when a websocket is opened. Keep the
        # existing Test-* behavior for local ``-a`` development mode.
        if request.method in {"GET", "HEAD"} and not app_state.anon_as_test_users:
            user = app_state.users[HTTP_ANON_USER]
        else:
            if app_state.disable_new_anons:
                session.invalidate()
                raise web.HTTPFound("/login")

            user = await mint_guest_user(app_state, request, session, arriving_at="page")

    theme = effective_theme(session, user)
    game_category = effective_game_category(session, user)

    # A materialized Anon-* user should carry the browser preferences into
    # websocket-backed pages and later requests. Never mutate the shared
    # Anon-HTTP object used by stateless anonymous GET requests.
    if user.anon and user.username != HTTP_ANON_USER:
        apply_anonymous_session_preferences(session, user)

    category_variants = CATEGORY_VARIANTS[game_category]
    category_variant_groups = CATEGORY_VARIANT_GROUPS[game_category]
    category_variant_list = CATEGORY_VARIANT_LISTS[game_category]
    category_variant_set = CATEGORY_VARIANT_SETS[game_category]

    view = request.path.split("/")[1] if len(request.path) > 2 else "lobby"
    lang = LOCALE.get()
    gettext = app_state.translations[lang].gettext

    def variant_display_name(variant: str) -> str:
        server_variant = ALL_VARIANTS.get(variant)
        if server_variant is None:
            return variant
        return gettext(server_variant.translated_name)

    if game_category == GAME_CATEGORY_ALL:
        menu_variant = "chess"
    else:
        menu_variant = category_variant_list[0] if category_variant_list else "chess"

    mod_report_score = 0
    if _is_admin_username(user.username):
        try:
            mod_report_score = await _max_open_report_score(request)
        except (
            ServerSelectionTimeoutError,
            AutoReconnect,
            NetworkTimeout,
            ConnectionFailure,
            ExecutionTimeout,
            WaitQueueTimeoutError,
        ):
            log.warning(
                "Failed to load mod report score for %s due to Mongo connectivity/timeout; using fallback=0",
                user.username,
                exc_info=True,
            )

    context: ViewContext = {
        "user": user,
        "lang": lang,
        "variant_display_name": variant_display_name,
        "theme": theme,
        "game_category": game_category,
        "category_variants": category_variants,
        "category_variant_groups": category_variant_groups,
        "category_variant_list": category_variant_list,
        "category_variant_set": category_variant_set,
        "game_category_intro": (not user.anon) and (not getattr(user, "game_category_set", False)),
        "catalogued_variants": json_dumps(
            catalogued_variants_for_client(
                app_state,
                user.username if not user.anon else None,
                favorite_names=(
                    user.catalogued_variant_favorites if not user.anon and not user.bot else None
                ),
            )
        ),
        "pm_friends_only": user.pm_friends_only,
        "corr_push_enabled": user.corr_push_enabled,
        "rr_push_enabled": user.rr_push_enabled,
        "menu_variant": menu_variant,
        "title": "%s • PyChess" % view.capitalize(),
        "view": view,
        "view_css": ("round" if view == "tv" else view) + ".css",
        "anon": user.anon,
        "username": user.username,
        "csrf_token": csrf_token,
        "piece_sets": piece_sets,
        "simuling": SIMULING,
        "admin": _is_admin_username(user.username),
        "mod_report_score": mod_report_score,
        "vapid_public_key": app_state.push_notifier.vapid_public_key
        if app_state.push_notifier.enabled
        else "",
    }
    return (user, context)


async def _ensure_user_correspondence_games_loaded(app_state: Any, user: User) -> None:
    """Complete one user's correspondence list while startup restore is still running.

    Correspondence games are restored globally in the background so aiohttp can start
    serving promptly after a restart.  A user who arrives before that restore reaches
    all of their games must not receive a partial ``corr_games`` snapshot, though.
    Load just that user's active correspondence documents here; ``load_game_from_doc``
    shares the global ``game_load_tasks`` machinery, so racing the background restore
    is safe and does not construct duplicate live ``Game`` objects.
    """

    loaded_event = getattr(app_state, "correspondence_games_loaded", None)
    if loaded_event is None or loaded_event.is_set() or getattr(user, "anon", False):
        return

    cursor = app_state.db.game.find(
        {
            "r": "d",
            "c": True,
            "us": user.username,
            "$or": [{"s": CREATED}, {"s": STARTED}],
        }
    )
    cursor.sort("d", -1)

    async for doc in cursor:
        try:
            await load_game_from_doc(app_state, doc)
        except Exception:
            log.exception(
                "Failed to lazy-load correspondence game %s for %s",
                doc.get("_id", ""),
                user.username,
            )


async def add_corr_games_context(
    app_state: Any,
    user: User,
    context: ViewContext,
) -> None:
    """Add ongoing correspondence games and their required variant metadata."""

    await _ensure_user_correspondence_games_loaded(app_state, user)
    games = list(user.correspondence_games)
    context["corr_games"] = json_dumps(corr_games(games))
    if not games:
        return

    catalogued_variants = json.loads(str(context.get("catalogued_variants") or "[]"))
    attempted_names = {str(item.get("name") or "") for item in catalogued_variants}

    for game in games:
        name = str(game.variant)
        if not name or name in attempted_names:
            continue
        attempted_names.add(name)
        try:
            catalogued_doc = await catalogued_variant_client_doc_for_game(
                app_state, game, user.username
            )
        except Exception:
            log.exception(
                "Failed to load catalogued variant metadata for ongoing game %s",
                getattr(game, "id", ""),
            )
            continue
        if catalogued_doc is not None:
            catalogued_variants.append(catalogued_doc)

    context["catalogued_variants"] = json_dumps(catalogued_variants)


def add_game_context(
    game: Game | GameBug,
    ply: int | str | None,
    user: User,
    context: ViewContext,
) -> None:
    context["gameid"] = game.id
    context["variant"] = game.variant
    context["wplayer"] = game.wplayer.username
    context["wtitle"] = game.wplayer.title
    context["wpatron"] = game.wplayer.patron
    context["wrating"] = game.wrating
    context["wrdiff"] = game.wrdiff
    context["chess960"] = game.chess960
    context["rated"] = game.rated
    context["corr"] = game.corr
    context["level"] = game.level
    context["bplayer"] = game.bplayer.username
    context["btitle"] = game.bplayer.title
    context["bpatron"] = game.bplayer.patron
    context["brating"] = game.brating
    context["brdiff"] = game.brdiff
    context["fen"] = DARK_FEN if game.variant == "fogofwar" else game.fen
    context["posnum"] = game.posnum if game.status > STARTED else -1
    context["base"] = game.base
    context["inc"] = game.inc
    context["byo"] = game.byoyomi_period
    context["result"] = game.result
    context["status"] = game.status
    context["date"] = game.date.isoformat()
    context["title"] = game.browser_title
    # todo: I think sent ply value shouldn't be minus 1.
    #       But also it gets overwritten anyway right after that so why send all this stuff at all here.
    #       just init client on 1st ws board msg received right after ws connection is established
    context["ply"] = ply if ply is not None else game.ply - 1
    context["initialFen"] = game.initial_fen

    user_color = WHITE if user == game.wplayer else BLACK if user == game.bplayer else None
    if game.server_variant.two_boards:
        board_response = game.get_board(full=True, persp_color=user_color, client_history=True)
    else:
        if TYPE_CHECKING:
            assert isinstance(game, Game)
        board_response = game.get_board(full=True, persp_color=user_color, client_history=True)
    context["board"] = json_dumps(board_response)

    if game.server_variant.two_boards:
        if TYPE_CHECKING:
            assert isinstance(game, GameBug)
        game_two_boards = game
        context["wplayerB"] = game_two_boards.wplayerB.username
        context["wtitleB"] = game_two_boards.wplayerB.title
        context["wpatronB"] = game_two_boards.wplayerB.patron
        context["wratingB"] = game_two_boards.wrating_b
        context["bplayerB"] = game_two_boards.bplayerB.username
        context["btitleB"] = game_two_boards.bplayerB.title
        context["bpatronB"] = game_two_boards.bplayerB.patron
        context["bratingB"] = game_two_boards.brating_b
