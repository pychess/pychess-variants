from __future__ import annotations

from datetime import UTC, datetime

import aiohttp_session
from account_api import erase_account
from admin import (
    ban,
    is_protected_username,
    resolve_existing_username,
    set_patron,
    set_shadowban,
    unban,
)
from aiohttp import web
from json_utils import json_response
from newid import new_id
from public_chat_moderation import timeout_public_chat_user
from pychess_global_app_state_utils import get_app_state
from report_api import TIMEOUT_REASONS
from request_utils import read_post_data
from session_security import session_matches_user
from settings import ADMINS

MOD_LOG_COLLECTION = "mod_log"

MOD_ACTION_LABELS: dict[str, str] = {
    "chat_timeout": "Chat timeout",
    "shadowban": "Shadowban",
    "unshadowban": "Remove shadowban",
    "close_account": "Close account",
    "delete_account": "Erase account (verified request)",
    "account_erasure_requested": "Account erasure requested by admin",
    "reopen_account": "Reopen account",
    "grant_patron": "Grant patron",
    "revoke_patron": "Revoke patron",
    "anonymous_sessions_disabled": "Disable new anonymous sessions",
    "anonymous_sessions_enabled": "Enable new anonymous sessions",
    "stream_added": "Add YouTube stream",
    "stream_removed": "Remove YouTube stream",
    "puzzle_deleted": "Delete puzzle",
    "highscore_regenerated": "Regenerate highscore",
    "crosstable_regenerated": "Regenerate crosstable",
    "fishnet_key_created": "Create fishnet key",
    "fishnet_key_removed": "Remove fishnet key",
    "system_message_sent": "Send system message",
    "close_team": "Close team",
    "reopen_team": "Reopen team",
    "simul_edited": "Edit simul",
    "simul_cancelled": "Cancel simul",
}

API_ACTIONS = {
    "timeout",
    "shadowban",
    "unshadowban",
    "close",
    "reopen",
    "patron",
    "unpatron",
    "delete",
}
USER_LOG_ACTIONS = frozenset(
    {
        "chat_timeout",
        "shadowban",
        "unshadowban",
        "close_account",
        "delete_account",
        "account_erasure_requested",
        "reopen_account",
        "grant_patron",
        "revoke_patron",
    }
)
TEAM_LOG_ACTIONS = frozenset({"close_team", "reopen_team"})


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


async def _session_username(request: web.Request) -> str | None:
    session = await aiohttp_session.get_session(request)
    value = session.get("user_name")
    return value if isinstance(value, str) else None


async def record_mod_action(
    app_state,
    moderator: str,
    target: str,
    action: str,
    details: str = "",
) -> None:
    collection = getattr(app_state.db, MOD_LOG_COLLECTION)
    document: dict[str, object] = {
        "_id": await new_id(collection),
        "mod": moderator,
        "user": target,
        "action": action,
        "createdAt": datetime.now(UTC),
    }
    if details:
        document["details"] = details
    await collection.insert_one(document)


async def record_team_action(
    app_state,
    moderator: str,
    team_id: str,
    action: str,
    details: str = "",
) -> None:
    if action not in TEAM_LOG_ACTIONS:
        raise ValueError(f"Unknown team moderation action: {action}")
    collection = getattr(app_state.db, MOD_LOG_COLLECTION)
    document: dict[str, object] = {
        "_id": await new_id(collection),
        "mod": moderator,
        "team": team_id,
        "action": action,
        "createdAt": datetime.now(UTC),
    }
    if details:
        document["details"] = details
    await collection.insert_one(document)


def _error(message: str, status: int) -> web.Response:
    return json_response({"type": "error", "message": message}, status=status)


async def admin_user_action(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    moderator = await _session_username(request)

    if moderator is None or app_state.db is None:
        return _error("Login required", 401)
    if not _is_admin_username(moderator):
        return _error("Admin only", 403)

    action = request.match_info.get("action", "")
    if action not in API_ACTIONS:
        return _error("Unsupported moderation action", 400)

    target = await resolve_existing_username(app_state, request.match_info.get("username", ""))
    if target is None:
        return _error("User not found", 404)
    user_doc = await app_state.db.user.find_one(
        {"_id": target},
        projection={
            "enabled": 1,
            "shadowban": 1,
            "patron": 1,
            "chatTimeoutUntil": 1,
            "gdprErasedAt": 1,
        },
    )
    if user_doc is None:
        return _error("User not found", 404)

    if action in {"patron", "unpatron"}:
        enabled = action == "patron"
        if bool(user_doc.get("patron", False)) == enabled:
            return _error(
                "User is already a patron" if enabled else "User is not a patron",
                409,
            )
        if not await set_patron(app_state, target, enabled):
            return _error("Failed to update patron status", 409)
        log_action = "grant_patron" if enabled else "revoke_patron"
        await record_mod_action(app_state, moderator, target, log_action)
        return json_response({"ok": True, "username": target, "action": log_action})

    if is_protected_username(target):
        return _error("Protected accounts cannot be moderated here", 403)

    if action == "delete":
        data = await read_post_data(request)
        form = data if data is not None else {}
        if (
            form.get("confirm_username") != target
            or form.get("understand") != "on"
            or form.get("verified_request") != "on"
        ):
            return _error(
                "Confirm the exact username, irreversible erasure and verified owner request", 400
            )
        session = await aiohttp_session.get_session(request)
        actor = await app_state.users.get(moderator)
        if not session_matches_user(session, actor):
            return _error("Session is no longer valid", 401)
        if user_doc.get("gdprErasedAt"):
            return _error("Account has already been erased", 409)
        user = await app_state.users.get(target)
        await record_mod_action(app_state, moderator, target, "account_erasure_requested")
        await erase_account(app_state, user)
        await record_mod_action(app_state, moderator, target, "delete_account")
        return json_response({"ok": True, "username": target, "action": "delete_account"})

    if action == "timeout":
        live_user = app_state.users.data.get(target)
        timeout_until = user_doc.get("chatTimeoutUntil")
        if isinstance(timeout_until, datetime) and timeout_until.tzinfo is None:
            timeout_until = timeout_until.replace(tzinfo=UTC)
        if live_user is not None and live_user.silence > 0:
            return _error("User already has a chat timeout", 409)
        if isinstance(timeout_until, datetime) and timeout_until > datetime.now(UTC):
            return _error("User already has a chat timeout", 409)

        data = await read_post_data(request)
        reason = str(data.get("reason") if data is not None else "").strip().lower()
        if reason not in TIMEOUT_REASONS:
            return _error("Invalid timeout reason", 400)

        if await timeout_public_chat_user(app_state, target) is None:
            return _error("User not found or protected", 409)
        await record_mod_action(
            app_state,
            moderator,
            target,
            "chat_timeout",
            TIMEOUT_REASONS[reason],
        )
        return json_response(
            {"ok": True, "username": target, "action": "chat_timeout", "reason": reason}
        )

    if action == "shadowban":
        if bool(user_doc.get("shadowban", False)):
            return _error("User is already shadowbanned", 409)
        if not await set_shadowban(app_state, target, True):
            return _error("Failed to shadowban user", 409)
        await record_mod_action(app_state, moderator, target, "shadowban")
        return json_response({"ok": True, "username": target, "action": "shadowban"})

    if action == "unshadowban":
        if not bool(user_doc.get("shadowban", False)):
            return _error("User is not shadowbanned", 409)
        if not await set_shadowban(app_state, target, False):
            return _error("Failed to remove shadowban", 409)
        await record_mod_action(app_state, moderator, target, "unshadowban")
        return json_response({"ok": True, "username": target, "action": "unshadowban"})

    if action == "close":
        if not bool(user_doc.get("enabled", True)):
            return _error("Account is already closed", 409)
        if not await ban(app_state, target):
            return _error("Failed to close account", 409)
        await record_mod_action(app_state, moderator, target, "close_account")
        return json_response({"ok": True, "username": target, "action": "close_account"})

    if bool(user_doc.get("enabled", True)):
        return _error("Account is already enabled", 409)
    if not await unban(app_state, target):
        return _error("Failed to reopen account", 409)
    await record_mod_action(app_state, moderator, target, "reopen_account")
    return json_response({"ok": True, "username": target, "action": "reopen_account"})
