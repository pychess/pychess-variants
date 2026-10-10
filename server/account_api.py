from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp_jinja2
import aiohttp_session
import msgspec
from aiohttp import web
from bot_accounts import (
    create_bot_token,
    list_bot_tokens,
    revoke_bot_token,
    upgrade_user_to_bot_account,
    user_game_count,
)
from forum.constants import ERASED_POST_TEXT, ERASED_POST_USER, KEY_TO_REACTION
from forum.storage import recompute_categ_summary, recompute_topic_summary
from login import logout
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from session_security import auth_version_from_user_document, authenticate_session
from simul.simuls import erase_user_from_simuls
from study.gdpr import erase_user_from_studies
from team import remove_user_from_teams_on_account_disable
from tournament.gdpr import erase_user_from_tournaments
from typedefs import REQUEST_NEW_SESSION_KEY
from typing_defs import UserDocument, ViewContext
from user_stats import DEFAULT_USER_COUNT
from utils import remove_seek
from views import get_user_context

log = logging.getLogger(__name__)

MAX_EXPORT_ROWS = 20_000
EXPORT_WRITE_CHUNK_BYTES = 64 * 1024
ERASED_MESSAGE_TEXT = "[deleted by account deletion request]"
BOT_NOTICE_SESSION_KEY = "account_bot_notice"
BOT_ERROR_SESSION_KEY = "account_bot_error"
BOT_NEW_TOKEN_SESSION_KEY = "account_bot_new_token"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


_EXPORT_JSON_ENCODER = msgspec.json.Encoder(enc_hook=_json_default, order="sorted")


def _export_section_header(title: str) -> bytes:
    return f"\n{'=' * len(title)}\n{title}\n{'=' * len(title)}\n".encode()


def _export_json(payload: Any) -> bytes:
    return msgspec.json.format(_EXPORT_JSON_ENCODER.encode(payload), indent=2)


async def _write_export_value(response: web.StreamResponse, title: str, payload: Any) -> None:
    await response.write(_export_section_header(title))
    await response.write(_export_json(payload))
    await response.write(b"\n")


async def _write_export_cursor(response: web.StreamResponse, title: str, cursor: Any) -> None:
    await response.write(_export_section_header(title))
    await response.write(b"[\n")

    chunk = bytearray()
    first = True
    async for row in cursor.limit(MAX_EXPORT_ROWS):
        if not first:
            chunk.extend(b",\n")
        encoded = _export_json(row)
        chunk.extend(b"  ")
        chunk.extend(encoded.replace(b"\n", b"\n  "))
        first = False

        if len(chunk) >= EXPORT_WRITE_CHUNK_BYTES:
            await response.write(bytes(chunk))
            chunk.clear()

    if chunk:
        await response.write(bytes(chunk))
    await response.write(b"\n]\n")


async def _require_logged_in_user(request: web.Request) -> tuple[Any, Any, str | None]:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)
    if user.anon:
        raise web.HTTPFound("/login")
    return app_state, user, session_user


def _clear_public_user_cache(app_state: Any, username: str) -> None:
    public_users = getattr(app_state, "public_users", None)
    if public_users is None:
        return
    profiles = getattr(public_users, "_profiles", None)
    titles = getattr(public_users, "_titles", None)
    if isinstance(profiles, dict):
        profiles.pop(username, None)
    if isinstance(titles, dict):
        titles.pop(username, None)


def _reopen_token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _set_account_bot_flash(
    session: aiohttp_session.Session,
    *,
    notice: str = "",
    error: str = "",
    new_token: str = "",
) -> None:
    if notice:
        session[BOT_NOTICE_SESSION_KEY] = notice
    else:
        session.pop(BOT_NOTICE_SESSION_KEY, None)

    if error:
        session[BOT_ERROR_SESSION_KEY] = error
    else:
        session.pop(BOT_ERROR_SESSION_KEY, None)

    if new_token:
        session[BOT_NEW_TOKEN_SESSION_KEY] = new_token
    else:
        session.pop(BOT_NEW_TOKEN_SESSION_KEY, None)


async def _erase_forum_posts_by_user(app_state: Any, username: str, now: datetime) -> None:
    db = getattr(app_state, "db", None)
    if db is None:
        return

    topic_ids = sorted(
        {
            str(topic_id)
            for topic_id in await db.forum_post.distinct("topicId", {"user": username})
            if isinstance(topic_id, str) and topic_id != ""
        }
    )
    categ_ids = sorted(
        {
            str(categ_id)
            for categ_id in await db.forum_post.distinct("categId", {"user": username})
            if isinstance(categ_id, str) and categ_id != ""
        }
    )
    if len(topic_ids) == 0 and len(categ_ids) == 0:
        return

    await db.forum_post.update_many(
        {"user": username},
        {
            "$set": {
                "user": ERASED_POST_USER,
                "text": ERASED_POST_TEXT,
                "erasedAt": now,
            },
            "$unset": {"reactions": "", "updatedAt": ""},
        },
    )
    await db.forum_topic.update_many({"user": username}, {"$set": {"user": ERASED_POST_USER}})

    for topic_id in topic_ids:
        await recompute_topic_summary(app_state, topic_id)
    for categ_id in categ_ids:
        await recompute_categ_summary(app_state, categ_id)


async def _remove_active_seeks_for_user(app_state: Any, user: Any) -> None:
    db = getattr(app_state, "db", None)
    removed = False
    stale_seek_ids: list[str] = []

    for seek in tuple(app_state.seeks.values()):
        if getattr(getattr(seek, "creator", None), "username", None) != user.username:
            continue
        if getattr(seek, "game_id", None) is not None:
            app_state.invites.pop(seek.game_id, None)
        stale_seek_ids.append(seek.id)
        remove_seek(app_state.seeks, seek)
        removed = True

    for seek_id in tuple(user.seeks):
        user.seeks.pop(seek_id, None)

    if db is not None:
        delete_query: dict[str, object] = {"user": user.username}
        if len(stale_seek_ids) > 0:
            delete_query = {"$or": [{"user": user.username}, {"_id": {"$in": stale_seek_ids}}]}
        await db.seek.delete_many(delete_query)

    if removed:
        await app_state.lobby.lobby_broadcast_seeks()


def _scrub_chat_line(line: Any, username: str) -> None:
    if not isinstance(line, dict):
        return
    if line.get("user") != username:
        return
    line["user"] = ERASED_POST_USER
    line["message"] = ERASED_MESSAGE_TEXT


async def _scrub_persisted_bug_game_chats(db: Any, username: str) -> None:
    # Bughouse persists only player-room chat and stores it under dynamic ply keys
    # such as c.m0/c.m12. Limit the scan to this user's games via the existing
    # multikey `us` index instead of scanning the whole game collection.
    cursor = db.game.find({"us": username, "c": {"$exists": True}}, {"_id": 1, "c": 1})
    async for doc in cursor:
        chat_by_ply = doc.get("c")
        if not isinstance(chat_by_ply, dict):
            continue

        changed = False
        new_chat: dict[str, Any] = {}
        for ply_key, chat_lines in chat_by_ply.items():
            if not isinstance(chat_lines, list):
                new_chat[ply_key] = chat_lines
                continue

            new_lines: list[Any] = []
            for line in chat_lines:
                if not isinstance(line, dict):
                    new_lines.append(line)
                    continue
                new_line = dict(line)
                if new_line.get("u") == username:
                    new_line["u"] = ERASED_POST_USER
                    new_line["m"] = ERASED_MESSAGE_TEXT
                    changed = True
                new_lines.append(new_line)
            new_chat[ply_key] = new_lines

        if changed:
            await db.game.update_one({"_id": doc["_id"]}, {"$set": {"c": new_chat}})


async def _scrub_authored_chat_history(app_state: Any, username: str) -> None:
    db = getattr(app_state, "db", None)
    if db is None:
        return

    for tournament in getattr(app_state, "tournaments", {}).values():
        for cached_line in getattr(tournament, "tourneychat", ()):
            _scrub_chat_line(cached_line, username)

    for simul in getattr(app_state, "simuls", {}).values():
        for cached_line in getattr(simul, "tourneychat", ()):
            _scrub_chat_line(cached_line, username)

    for game in getattr(app_state, "games", {}).values():
        for cached_line in getattr(game, "messages", ()):
            _scrub_chat_line(cached_line, username)

    # Keep GDPR erasure compatible with the retired lobby-chat collection until
    # operators choose to drop that historical collection from MongoDB.
    if "lobbychat" in await db.list_collection_names():
        await db.lobbychat.update_many(
            {"user": username},
            {"$set": {"user": ERASED_POST_USER, "message": ERASED_MESSAGE_TEXT}},
        )
    await db.tournament_chat.update_many(
        {"user": username},
        {"$set": {"user": ERASED_POST_USER, "message": ERASED_MESSAGE_TEXT}},
    )
    await db.simul_chat.update_many(
        {"user": username},
        {"$set": {"user": ERASED_POST_USER, "message": ERASED_MESSAGE_TEXT}},
    )
    await _scrub_persisted_bug_game_chats(db, username)


async def _scrub_delete_owned_data(app_state: Any, user: Any, now: datetime) -> None:
    db = getattr(app_state, "db", None)
    if db is None:
        return

    await remove_user_from_teams_on_account_disable(
        app_state, user.username, erase=True, remove_from_tournaments=True
    )
    await _erase_forum_posts_by_user(app_state, user.username, now)
    await db.ublog_post.delete_many({"author": user.username})
    await db.bot_token.delete_many({"user": user.username})
    await db.push_subscription.delete_many({"user": user.username})
    await db.practice.delete_one({"_id": user.username})
    await db.account_reopen_token.delete_many({"username": user.username})
    await db.notify.delete_many({"notifies": user.username})
    await app_state.timeline.erase_user(user.username)
    await _remove_active_seeks_for_user(app_state, user)
    await _scrub_authored_chat_history(app_state, user.username)
    await erase_user_from_tournaments(app_state, user.username)
    await erase_user_from_simuls(app_state, user.username)
    await erase_user_from_studies(app_state, user.username)

    await db.inbox_msg.update_many(
        {"from": user.username},
        {"$set": {"text": ERASED_MESSAGE_TEXT, "erasedBySenderAt": now}},
    )
    await db.relation.delete_many({"$or": [{"u1": user.username}, {"u2": user.username}]})

    await db.ublog_post.update_many(
        {"$or": [{"likes": user.username}, {"viewers": user.username}]},
        {"$pull": {"likes": user.username, "viewers": user.username}},
    )
    reaction_fields = [f"reactions.{reaction_key}" for reaction_key in KEY_TO_REACTION]
    await db.forum_post.update_many(
        {"$or": [{reaction_field: user.username} for reaction_field in reaction_fields]},
        {"$pull": {reaction_field: user.username for reaction_field in reaction_fields}},
    )


@aiohttp_jinja2.template("account.html")
async def account_home(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")
    context["view_css"] = "faq.css"
    return context


@aiohttp_jinja2.template("account_data.html")
async def account_personal_data(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")
    context["view_css"] = "faq.css"
    return context


@aiohttp_jinja2.template("account_bot.html")
async def account_bot(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")

    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    user_doc: UserDocument | None = await app_state.db.user.find_one({"_id": user.username})
    game_count = user_game_count(user_doc)
    if user_doc is not None and user_doc.get("title") == "BOT" and not user.bot:
        user.enable_bot_account()

    context["view_css"] = "faq.css"
    context["bot_tokens"] = await list_bot_tokens(app_state, user.username)
    context["bot_account_title"] = user.title
    context["bot_game_count"] = game_count
    context["bot_upgrade_eligible"] = (not user.bot) and game_count == 0
    context["bot_upgrade_reason"] = (
        ""
        if user.bot or game_count == 0
        else "Only accounts that never played a single game can be upgraded to BOT."
    )
    context["bot_notice"] = str(session.pop(BOT_NOTICE_SESSION_KEY, "") or "")
    context["bot_error"] = str(session.pop(BOT_ERROR_SESSION_KEY, "") or "")
    context["new_bot_token"] = str(session.pop(BOT_NEW_TOKEN_SESSION_KEY, "") or "")
    return context


async def account_personal_data_export(request: web.Request) -> web.StreamResponse:
    app_state, user, _ = await _require_logged_in_user(request)

    user_doc: UserDocument | None = await app_state.db.user.find_one({"_id": user.username})
    if user_doc is None:
        raise web.HTTPNotFound()

    metadata = {
        "exportedAt": datetime.now(UTC),
        "username": user.username,
        "note": (
            "This export contains account and private interaction data. "
            "Public game archives are handled separately via the profile PGN export."
        ),
    }
    cursor_sections = (
        (
            "Relations (blocks and related links)",
            app_state.db.relation.find({"$or": [{"u1": user.username}, {"u2": user.username}]}),
        ),
        (
            "Direct messages sent by this account",
            app_state.db.inbox_msg.find({"from": user.username}),
        ),
        ("Forum posts by this account", app_state.db.forum_post.find({"user": user.username})),
        ("Blog posts by this account", app_state.db.ublog_post.find({"author": user.username})),
        (
            "Push subscriptions",
            app_state.db.push_subscription.find({"user": user.username}),
        ),
        (
            "Reports created by this account",
            app_state.db.user_report.find({"reporter": user.username}),
        ),
        (
            "Timeline activities authored or received by this account",
            app_state.db.timeline_entry.find(
                {"$or": [{"data.actor": user.username}, {"users": user.username}]}
            ),
        ),
        ("Team memberships", app_state.db.team_member.find({"user": user.username})),
        ("Team join requests", app_state.db.team_request.find({"user": user.username})),
        (
            "Team updates authored by this account",
            app_state.db.team_update.find({"sender": user.username}),
        ),
        ("Teams created by this account", app_state.db.team.find({"createdBy": user.username})),
    )

    response = web.StreamResponse()
    response.content_type = "text/plain"
    response.charset = "utf-8"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="pychess_personal_data_{user.username}.txt"'
    )
    await response.prepare(request)

    await _write_export_value(response, f"Personal data export for {user.username}", metadata)
    await _write_export_value(response, "Account document", user_doc)
    for title, cursor in cursor_sections:
        await _write_export_cursor(response, title, cursor)
    await _write_export_value(response, "End of export", {"ok": True})
    await response.write_eof()
    return response


async def account_bot_token_create(request: web.Request) -> web.StreamResponse:
    app_state, user, _ = await _require_logged_in_user(request)
    session = await aiohttp_session.get_session(request)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)

    description = str(post_data.get("description", "")).strip()[:120]
    if description == "":
        description = "pychess-bot"

    _, raw_token = await create_bot_token(app_state, user.username, description)
    _set_account_bot_flash(
        session,
        notice="Created a new BOT API token. Copy it now; it will not be shown again.",
        new_token=raw_token,
    )
    return web.HTTPFound("/account/bot")


async def account_bot_token_revoke(request: web.Request) -> web.StreamResponse:
    app_state, user, _ = await _require_logged_in_user(request)
    session = await aiohttp_session.get_session(request)
    token_id = str(request.match_info.get("tokenId") or "").strip()
    if token_id == "":
        raise web.HTTPBadRequest(text="Missing token id.")

    revoked = await revoke_bot_token(app_state, user.username, token_id)
    _set_account_bot_flash(
        session,
        notice="BOT API token revoked." if revoked else "",
        error="" if revoked else "BOT API token was not found or was already revoked.",
    )
    return web.HTTPFound("/account/bot")


async def account_bot_upgrade_post(request: web.Request) -> web.StreamResponse:
    app_state, user, _ = await _require_logged_in_user(request)
    session = await aiohttp_session.get_session(request)
    try:
        await upgrade_user_to_bot_account(app_state, user.username)
    except ValueError as exc:
        _set_account_bot_flash(session, error=str(exc))
        return web.HTTPFound("/account/bot")

    _set_account_bot_flash(session, notice="Account upgraded to BOT.")
    return web.HTTPFound("/account/bot")


@aiohttp_jinja2.template("account_close.html")
async def account_close(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")
    context["view_css"] = "faq.css"
    return context


async def account_close_post(request: web.Request) -> web.StreamResponse:
    app_state, user, _ = await _require_logged_in_user(request)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)

    confirm_username = str(post_data.get("confirm_username", "")).strip()
    understand = str(post_data.get("understand", "")).strip().lower() in {
        "on",
        "true",
        "1",
        "yes",
    }
    if confirm_username != user.username or not understand:
        raise web.HTTPBadRequest(text="Username confirmation and acknowledgement are required.")

    user_doc: UserDocument | None = await app_state.db.user.find_one(
        {"_id": user.username}, {"reopenedAt": 1}
    )
    close_type = "self_final" if user_doc and user_doc.get("reopenedAt") else "self"

    await app_state.db.user.update_one(
        {"_id": user.username},
        {
            "$set": {
                "enabled": False,
                "closedAt": datetime.now(UTC),
                "closeType": close_type,
            }
        },
    )
    await remove_user_from_teams_on_account_disable(app_state, user.username)
    user.enabled = False
    _clear_public_user_cache(app_state, user.username)
    return await logout(request)


@aiohttp_jinja2.template("account_delete.html")
async def account_delete(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")
    context["view_css"] = "faq.css"
    return context


async def account_delete_post(request: web.Request) -> web.StreamResponse:
    await _require_logged_in_user(request)
    raise web.HTTPForbidden(text="Account deletion requires admin assistance. Contact site admins.")


async def erase_account(app_state: Any, user: Any) -> None:
    """Erase an account after an admin has independently verified its owner's request.

    This is not a self-service HTTP handler. Authorization and target confirmation
    belong to the admin API; logout revokes the target, never the admin's session.
    """
    now = datetime.now(UTC)
    await app_state.db.user.update_one(
        {"_id": user.username},
        [
            {
                "$set": {
                    "enabled": False,
                    "title": "",
                    "oauth_id": "",
                    "oauth_provider": "",
                    "lang": "en",
                    "theme": "dark",
                    "ct": "all",
                    "pmf": False,
                    "gdprErasedAt": now,
                    "closeType": "deleted",
                    "count": dict(DEFAULT_USER_COUNT),
                    "forumPosts": 0,
                    "tournamentPoints": 0,
                    "perfs": {},
                    "pperfs": {},
                    # Erase identifying security data while preserving the current
                    # generation atomically, including any concurrent revocation.
                    "security": {"sessionVersion": {"$ifNull": ["$security.sessionVersion", 0]}},
                },
            },
        ],
    )
    # Disable the shared live User before any potentially long GDPR discovery and
    # cleanup. Existing websocket handlers observe this immediately, and new
    # websocket handshakes are rejected by process_ws while authored data is erased.
    user.enabled = False
    await logout(None, user)
    await _scrub_delete_owned_data(app_state, user, now)
    _clear_public_user_cache(app_state, user.username)

    user.forum_posts = 0
    user.tournament_points = 0
    user.enabled = False
    user.title = ""
    user.oauth_id = ""
    user.oauth_provider = ""
    user.perfs = {}
    user.pperfs = {}
    user.count = dict(DEFAULT_USER_COUNT)
    user.blocked.clear()
    user.following.clear()
    user.notifications = []
    user.pm_friends_only = False

    log.info("Account deleted (GDPR erase) for user %s", user.username)


@aiohttp_jinja2.template("account_reopen.html")
async def account_reopen(request: web.Request) -> ViewContext:
    _user, context = await get_user_context(request)
    raw_token = str(request.rel_url.query.get("token") or "").strip()
    if not raw_token:
        raise web.HTTPFound("/login")

    app_state = get_app_state(request.app)
    now = datetime.now(UTC)
    await app_state.db.account_reopen_token.delete_many({"expiresAt": {"$lt": now}})
    token_doc = await app_state.db.account_reopen_token.find_one(
        {
            "tokenHash": _reopen_token_hash(raw_token),
            "usedAt": {"$exists": False},
            "expiresAt": {"$gt": now},
        }
    )
    closed_username = str((token_doc or {}).get("username") or "").strip()
    user_doc: UserDocument | None = (
        await app_state.db.user.find_one({"_id": closed_username}) if closed_username else None
    )

    can_reopen = bool(
        token_doc
        and user_doc
        and (not user_doc.get("enabled", True))
        and user_doc.get("closeType") == "self"
        and (not user_doc.get("gdprErasedAt"))
    )
    context["view_css"] = "faq.css"
    context["reopen_username"] = closed_username
    context["reopen_token"] = raw_token
    context["can_reopen"] = can_reopen
    return context


async def account_reopen_post(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    post_data = await read_post_data(request)
    if post_data is None:
        return web.Response(status=204)

    raw_token = str(post_data.get("token", "")).strip()
    if not raw_token:
        raise web.HTTPBadRequest(text="Missing reopen token.")

    confirm_username = str(post_data.get("confirm_username", "")).strip()
    understand = str(post_data.get("understand", "")).strip().lower() in {
        "on",
        "true",
        "1",
        "yes",
    }
    if not understand:
        raise web.HTTPBadRequest(text="Username confirmation and acknowledgement are required.")

    now = datetime.now(UTC)
    token_hash = _reopen_token_hash(raw_token)
    matching_token = await app_state.db.account_reopen_token.find_one(
        {
            "tokenHash": token_hash,
            "usedAt": {"$exists": False},
            "expiresAt": {"$gt": now},
        }
    )
    if matching_token is None:
        raise web.HTTPForbidden(text="Invalid or expired reopen token.")

    closed_username = str(matching_token.get("username") or "")
    if confirm_username != closed_username:
        raise web.HTTPBadRequest(text="Username confirmation and acknowledgement are required.")

    token_doc = await app_state.db.account_reopen_token.find_one_and_update(
        {
            "tokenHash": token_hash,
            "username": closed_username,
            "usedAt": {"$exists": False},
            "expiresAt": {"$gt": now},
        },
        {"$set": {"usedAt": now}},
    )
    if token_doc is None:
        raise web.HTTPForbidden(text="Invalid or expired reopen token.")

    user_doc: UserDocument | None = await app_state.db.user.find_one({"_id": closed_username})
    if (
        user_doc is None
        or user_doc.get("enabled", True)
        or user_doc.get("closeType") != "self"
        or user_doc.get("gdprErasedAt")
    ):
        raise web.HTTPForbidden(text="This account cannot be reopened automatically.")

    now = datetime.now(UTC)
    await app_state.db.user.update_one(
        {"_id": closed_username},
        {"$set": {"enabled": True, "reopenedAt": now}, "$unset": {"closedAt": "", "closeType": ""}},
    )

    if closed_username in app_state.users:
        cached_user = app_state.users[closed_username]
        cached_user.enabled = True

    _clear_public_user_cache(app_state, closed_username)
    authenticate_session(
        session,
        closed_username,
        auth_version_from_user_document(user_doc),
    )
    request[REQUEST_NEW_SESSION_KEY] = True
    session.pop("closed_account_user", None)
    return web.HTTPFound("/")
