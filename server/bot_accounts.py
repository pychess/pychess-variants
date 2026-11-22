from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict

from newid import new_id

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from typing_defs import UserDocument


BOT_TOKEN_SCOPE = "bot:play"
ENGINE_TOKEN_SCOPES = ("engine:read", "engine:write")
BOT_TOKEN_TEST_EXPIRES_MS = 1358509698620


class BotTokenDocument(TypedDict, total=False):
    _id: str
    user: str
    description: str
    tokenHash: str
    createdAt: datetime
    usedAt: datetime
    revokedAt: datetime
    scopes: list[str]


def bot_token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def clear_public_user_cache(app_state: Any, username: str) -> None:
    public_users = getattr(app_state, "public_users", None)
    if public_users is None:
        return
    profiles = getattr(public_users, "_profiles", None)
    titles = getattr(public_users, "_titles", None)
    if isinstance(profiles, dict):
        profiles.pop(username, None)
    if isinstance(titles, dict):
        titles.pop(username, None)


def user_game_count(user_doc: UserDocument | None) -> int:
    count = {} if user_doc is None else (user_doc.get("count") or {})
    try:
        return int(count.get("game", 0))
    except (TypeError, ValueError):
        return 0


async def create_bot_token(
    app_state: PychessGlobalAppState,
    username: str,
    description: str,
    *,
    scopes: tuple[str, ...] = (BOT_TOKEN_SCOPE,),
) -> tuple[str, str]:
    if app_state.db is None:
        raise RuntimeError("BOT token storage requires a database.")

    token_id = await new_id(app_state.db.bot_token)
    raw_token = secrets.token_urlsafe(32)
    await app_state.db.bot_token.insert_one(
        {
            "_id": token_id,
            "user": username,
            "description": description,
            "tokenHash": bot_token_hash(raw_token),
            "createdAt": datetime.now(UTC),
            "scopes": list(scopes),
        }
    )
    return token_id, raw_token


async def list_bot_tokens(
    app_state: PychessGlobalAppState, username: str
) -> list[BotTokenDocument]:
    if app_state.db is None:
        return []
    cursor = app_state.db.bot_token.find({"user": username}).sort([("createdAt", -1)])
    return await cursor.to_list(length=100)


async def revoke_bot_token(app_state: PychessGlobalAppState, username: str, token_id: str) -> bool:
    if app_state.db is None:
        return False
    result = await app_state.db.bot_token.update_one(
        {"_id": token_id, "user": username, "revokedAt": {"$exists": False}},
        {"$set": {"revokedAt": datetime.now(UTC)}},
    )
    if result.modified_count:
        await app_state.db.external_engine.delete_many({"_id": token_id, "user": username})
    return bool(result.modified_count)


async def get_db_token_owner(
    app_state: PychessGlobalAppState,
    raw_token: str,
    *,
    mark_used: bool,
    required_scope: str | None = BOT_TOKEN_SCOPE,
) -> UserDocument | None:
    if app_state.db is None:
        return None

    token_filter = {"tokenHash": bot_token_hash(raw_token), "revokedAt": {"$exists": False}}
    if required_scope is not None:
        if required_scope == BOT_TOKEN_SCOPE:
            token_filter["$or"] = [{"scopes": required_scope}, {"scopes": {"$exists": False}}]
        else:
            token_filter["scopes"] = required_scope
    if mark_used:
        token_doc = await app_state.db.bot_token.find_one_and_update(
            token_filter,
            {"$set": {"usedAt": datetime.now(UTC)}},
        )
    else:
        token_doc = await app_state.db.bot_token.find_one(token_filter)
    if token_doc is None:
        return None
    if required_scope is not None and required_scope not in token_doc.get(
        "scopes", [BOT_TOKEN_SCOPE]
    ):
        return None

    username = str(token_doc.get("user") or "")
    if username == "":
        return None

    user_doc: UserDocument | None = await app_state.db.user.find_one({"_id": username})
    if user_doc is None or not user_doc.get("enabled", True):
        return None
    return user_doc


async def upgrade_user_to_bot_account(
    app_state: PychessGlobalAppState, username: str
) -> UserDocument:
    if app_state.db is None:
        raise RuntimeError("BOT account upgrade requires a database.")

    user_doc: UserDocument | None = await app_state.db.user.find_one({"_id": username})
    if user_doc is None or not user_doc.get("enabled", True):
        raise ValueError("This account is not available for BOT upgrade.")

    if user_doc.get("title") == "BOT":
        cached_user = app_state.users.data.get(username)
        if cached_user is not None:
            cached_user.enable_bot_account()
        clear_public_user_cache(app_state, username)
        return user_doc

    if user_game_count(user_doc) != 0:
        raise ValueError("Only accounts that never played a single game can be upgraded to BOT.")

    await app_state.db.user.update_one({"_id": username}, {"$set": {"title": "BOT"}})
    user_doc["title"] = "BOT"

    cached_user = app_state.users.data.get(username)
    if cached_user is not None:
        cached_user.enable_bot_account()
    clear_public_user_cache(app_state, username)
    return user_doc
