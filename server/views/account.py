from __future__ import annotations

from datetime import UTC, datetime

import aiohttp_jinja2
import aiohttp_session
from account_api import (
    BOT_ERROR_SESSION_KEY,
    BOT_NEW_TOKEN_SESSION_KEY,
    BOT_NOTICE_SESSION_KEY,
    _reopen_token_hash,
)
from aiohttp import web
from bot_accounts import BOT_TOKEN_SCOPE, list_bot_tokens, user_game_count
from pychess_global_app_state_utils import get_app_state
from typing_defs import UserDocument, ViewContext

from views import get_user_context


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
    context["bot_tokens"] = [
        token
        for token in await list_bot_tokens(app_state, user.username)
        if BOT_TOKEN_SCOPE in token.get("scopes", [BOT_TOKEN_SCOPE])
    ]
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


@aiohttp_jinja2.template("account_engines.html")
async def account_engines(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    context["view_css"] = "faq.css"
    context["engine_tokens"] = [
        token
        for token in await list_bot_tokens(app_state, user.username)
        if "engine:write" in token.get("scopes", [])
    ]
    context["new_engine_token"] = str(session.pop("new_engine_token", "") or "")
    return context


@aiohttp_jinja2.template("account_close.html")
async def account_close(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")
    context["view_css"] = "faq.css"
    return context


@aiohttp_jinja2.template("account_delete.html")
async def account_delete(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    if user.anon:
        raise web.HTTPFound("/login")
    context["view_css"] = "faq.css"
    return context


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
