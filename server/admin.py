from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from const import T_CREATED, T_STARTED, reserved
from login import logout
from security_evasion import (
    add_ban_signals_from_user,
    remove_ban_signals_from_user,
)
from session_security import revoke_user_sessions_for_username
from settings import ADMINS
from team import remove_user_from_teams_on_account_disable
from user import SILENCE

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState

log = logging.getLogger(__name__)


def _resolve_online_username(users: Mapping[str, object], raw_username: str) -> str | None:
    candidate = raw_username.lstrip("@")
    if candidate in users:
        return candidate

    lowered = candidate.casefold()
    for username in users:
        if username.casefold() == lowered:
            return username

    return None


def _normalize_target_username(raw_username: str) -> str:
    return raw_username.lstrip("@")


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


def is_protected_username(username: str) -> bool:
    return _is_admin_username(username) or reserved(username)


async def resolve_existing_username(
    app_state: PychessGlobalAppState, raw_username: str
) -> str | None:
    candidate = _normalize_target_username(raw_username)

    user_doc = await app_state.db.user.find_one(
        {
            "$or": [
                {"_id": candidate},
                {
                    "username_lower": {
                        "$eq": candidate.lower(),
                        "$type": "string",
                    }
                },
            ]
        },
        projection={"_id": 1},
    )
    if user_doc is None:
        return None

    username = user_doc.get("_id")
    return username if isinstance(username, str) else None


async def set_patron(
    app_state: PychessGlobalAppState,
    raw_username: str,
    enabled: bool,
) -> bool:
    username = _normalize_target_username(raw_username)
    resolved_username = await resolve_existing_username(app_state, username)
    if resolved_username is None:
        return False
    username = resolved_username

    await app_state.db.user.find_one_and_update(
        {"_id": username},
        {"$set": {"patron": enabled}},
    )
    live_user = app_state.users.data.get(username)
    if live_user is not None:
        live_user.patron = enabled
    app_state.public_users.invalidate(username)
    return True


async def set_shadowban(
    app_state: PychessGlobalAppState,
    raw_username: str,
    enabled: bool,
) -> bool:
    username = _normalize_target_username(raw_username)
    if is_protected_username(username):
        return False

    resolved_username = await resolve_existing_username(app_state, username)
    if resolved_username is None:
        return False
    username = resolved_username

    await app_state.db.user.find_one_and_update(
        {"_id": username},
        {"$set": {"shadowban": enabled}},
    )
    if username in app_state.users:
        user = await app_state.users.get(username)
        user.shadowban = enabled

    return True


async def timeout_user(
    app_state: PychessGlobalAppState,
    raw_username: str,
) -> str | None:
    candidate = _normalize_target_username(raw_username)
    if is_protected_username(candidate):
        return None

    db = getattr(app_state, "db", None)
    if db is None:
        username = _resolve_online_username(app_state.users, candidate)
        if username is None:
            return None
    else:
        username = await resolve_existing_username(app_state, candidate)
        if username is None or is_protected_username(username):
            return None

    timeout_until = datetime.now(UTC) + timedelta(seconds=SILENCE)
    if db is not None:
        await db.user.update_one(
            {"_id": username},
            {"$set": {"chatTimeoutUntil": timeout_until}},
        )

    live_user = app_state.users.data.get(username)
    if live_user is not None:
        live_user.set_silence(timeout_until)

    return username


async def ban(app_state: PychessGlobalAppState, raw_username: str) -> bool:
    username = _normalize_target_username(raw_username)
    if is_protected_username(username):
        return False

    resolved_username = await resolve_existing_username(app_state, username)
    if resolved_username is None:
        return False

    username = resolved_username

    await app_state.db.user.find_one_and_update({"_id": username}, {"$set": {"enabled": False}})
    await remove_user_from_teams_on_account_disable(
        app_state, username, remove_from_tournaments=False
    )
    banned_user = None
    if username in app_state.users:
        banned_user = await app_state.users.get(username)
        banned_user.enabled = False

    # Keep started tournament history intact but ensure banned users are not
    # paired again. For not-yet-started tournaments, remove them from entries.
    for tournament in tuple(app_state.tournaments.values()):
        player = tournament.get_player_by_name(username)
        if player is None:
            continue
        if tournament.status == T_CREATED:
            await tournament.withdraw(player)
        elif tournament.status == T_STARTED:
            await tournament.pause(player)

    if banned_user is not None:
        await logout(None, banned_user)
    else:
        await revoke_user_sessions_for_username(app_state, username)

    signal_count = await add_ban_signals_from_user(app_state.db, username)
    if signal_count > 0:
        log.info("Stored %s ban-evasion signal(s) for %s", signal_count, username)
    return True


async def unban(app_state: PychessGlobalAppState, raw_username: str) -> bool:
    username = _normalize_target_username(raw_username)
    if is_protected_username(username):
        return False

    resolved_username = await resolve_existing_username(app_state, username)
    if resolved_username is None:
        return False

    username = resolved_username

    await app_state.db.user.find_one_and_update({"_id": username}, {"$set": {"enabled": True}})
    if username in app_state.users:
        user = await app_state.users.get(username)
        user.enabled = True

    touched_count, deleted_count = await remove_ban_signals_from_user(app_state.db, username)
    if touched_count > 0:
        log.info(
            "Unban %s removed source from %s signal(s), deleted %s empty signal(s)",
            username,
            touched_count,
            deleted_count,
        )
    return True
