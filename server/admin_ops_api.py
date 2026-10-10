from __future__ import annotations

import collections
import hashlib
import re

import aiohttp_session
from admin import resolve_existing_username
from admin_api import record_mod_action
from aiohttp import web
from broadcast import broadcast_streams
from generate_crosstable import generate_crosstable
from generate_highscore import generate_highscore
from json_utils import json_response
from newid import new_id
from puzzle import drop_stale_daily_puzzle_keys
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from settings import ADMINS, FISHNET_KEYS
from variants import VARIANTS

SITE_LOG_TARGET = "site"
FISHNET_KEY_ID_LENGTH = 12

OPERATION_LOG_ACTIONS = frozenset(
    {
        "anonymous_sessions_disabled",
        "anonymous_sessions_enabled",
        "stream_added",
        "stream_removed",
        "puzzle_deleted",
        "highscore_regenerated",
        "crosstable_regenerated",
        "fishnet_key_created",
        "fishnet_key_removed",
    }
)

API_ACTIONS = frozenset(
    {
        "disable-anons",
        "enable-anons",
        "stream-add",
        "stream-remove",
        "puzzle-delete",
        "highscore",
        "crosstable",
        "fishnet-create",
        "fishnet-remove",
    }
)

CHANNEL_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
PUZZLE_ID_RE = re.compile(r"^[A-Za-z0-9]{5}$")
FISHNET_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,40}$")
FISHNET_KEY_ID_RE = re.compile(rf"^[a-f0-9]{{{FISHNET_KEY_ID_LENGTH}}}$")


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


def fishnet_key_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:FISHNET_KEY_ID_LENGTH]


def _error(message: str, status: int) -> web.Response:
    return json_response({"type": "error", "message": message}, status=status)


def _success(action: str, message: str, **extra: object) -> web.Response:
    return json_response({"ok": True, "action": action, "message": message, **extra})


def _clean_text(value: object, *, maximum: int) -> str | None:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(char) < 32 for char in text):
        return None
    return text


async def admin_operation(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    raw_moderator = session.get("user_name")
    moderator = raw_moderator if isinstance(raw_moderator, str) else None

    if moderator is None:
        return _error("Login required", 401)
    if not _is_admin_username(moderator):
        return _error("Admin only", 403)
    if app_state.db is None:
        return _error("Database unavailable", 503)

    action = request.match_info.get("action", "")
    if action not in API_ACTIONS:
        return _error("Unsupported operation", 400)

    data = await read_post_data(request)
    form = data if data is not None else {}

    if action in {"disable-anons", "enable-anons"}:
        disabled = action == "disable-anons"
        if app_state.disable_new_anons == disabled:
            state = "disabled" if disabled else "enabled"
            return _error(f"New anonymous sessions are already {state}", 409)

        app_state.disable_new_anons = disabled
        log_action = "anonymous_sessions_disabled" if disabled else "anonymous_sessions_enabled"
        await record_mod_action(app_state, moderator, SITE_LOG_TARGET, log_action)
        state = "disabled" if disabled else "enabled"
        return _success(log_action, f"New anonymous sessions are now {state}.")

    if action == "stream-add":
        channel = str(form.get("channel") or "").strip()
        username = _clean_text(form.get("username") or "unknown", maximum=50)
        title = _clean_text(form.get("title") or "PyChess stream", maximum=120)
        if not CHANNEL_RE.fullmatch(channel):
            return _error("Enter a valid YouTube channel ID", 400)
        if username is None or title is None:
            return _error("Enter a valid streamer name and title", 400)
        if channel in app_state.youtube.streams:
            return _error("That YouTube channel is already listed", 409)

        app_state.youtube.add(channel, username, title)
        await broadcast_streams(app_state)
        await record_mod_action(
            app_state,
            moderator,
            SITE_LOG_TARGET,
            "stream_added",
            f"{channel} ({username})",
        )
        return _success("stream_added", "YouTube stream added.")

    if action == "stream-remove":
        channel = str(form.get("channel") or "").strip()
        stream = app_state.youtube.streams.get(channel)
        if stream is None:
            return _error("YouTube stream not found", 404)

        username = str(stream.get("username") or "unknown")
        app_state.youtube.remove(channel)
        await broadcast_streams(app_state)
        await record_mod_action(
            app_state,
            moderator,
            SITE_LOG_TARGET,
            "stream_removed",
            f"{channel} ({username})",
        )
        return _success("stream_removed", "YouTube stream removed.")

    if action == "puzzle-delete":
        puzzle_id = str(form.get("puzzle_id") or "").strip()
        if not PUZZLE_ID_RE.fullmatch(puzzle_id):
            return _error("Enter a valid five-character puzzle ID", 400)

        result = await app_state.db.puzzle.delete_one({"_id": puzzle_id})
        if result.deleted_count == 0:
            return _error("Puzzle not found", 404)
        # A deleted puzzle must not stay referenced by the daily rotation,
        # otherwise the lobby renders a null puzzle and stops working.
        await drop_stale_daily_puzzle_keys(app_state, puzzle_id)
        await record_mod_action(app_state, moderator, SITE_LOG_TARGET, "puzzle_deleted", puzzle_id)
        return _success("puzzle_deleted", f"Puzzle {puzzle_id} deleted.")

    if action == "highscore":
        variant = str(form.get("variant") or "").strip()
        if variant not in VARIANTS:
            return _error("Select a valid site variant", 400)

        await generate_highscore(app_state, variant)
        await record_mod_action(
            app_state,
            moderator,
            SITE_LOG_TARGET,
            "highscore_regenerated",
            variant,
        )
        return _success("highscore_regenerated", f"{variant} highscore regenerated.")

    if action == "crosstable":
        raw_username = str(form.get("username") or "").strip()
        username = await resolve_existing_username(app_state, raw_username)
        if username is None:
            return _error("User not found", 404)

        await generate_crosstable(app_state, username)
        await record_mod_action(
            app_state,
            moderator,
            SITE_LOG_TARGET,
            "crosstable_regenerated",
            username,
        )
        return _success("crosstable_regenerated", f"Crosstables for {username} regenerated.")

    if action == "fishnet-create":
        name = str(form.get("name") or "").strip()
        if not FISHNET_NAME_RE.fullmatch(name):
            return _error("Use 3–40 letters, numbers, underscores, or hyphens", 400)
        if any(name.casefold() == existing.casefold() for existing in FISHNET_KEYS.values()):
            return _error("A fishnet worker with that name already exists", 409)

        key = await new_id(app_state.db.fishnet)
        await app_state.db.fishnet.insert_one({"_id": key, "name": name})
        FISHNET_KEYS[key] = name
        app_state.fishnet_monitor[name] = collections.deque([], 50)
        await record_mod_action(
            app_state,
            moderator,
            SITE_LOG_TARGET,
            "fishnet_key_created",
            name,
        )
        return _success(
            "fishnet_key_created",
            "Fishnet key created. Copy it now; it will not be shown again.",
            secret=key,
        )

    key_id = str(form.get("key_id") or "").strip()
    if not FISHNET_KEY_ID_RE.fullmatch(key_id):
        return _error("Invalid fishnet key identifier", 400)
    matches = [(key, name) for key, name in FISHNET_KEYS.items() if fishnet_key_id(key) == key_id]
    if not matches:
        return _error("Fishnet worker not found", 404)
    if len(matches) > 1:
        return _error("Fishnet key identifier collision", 409)

    key, name = matches[0]
    if await app_state.db.fishnet.find_one({"_id": key}, projection={"_id": 1}) is None:
        return _error(
            "This key comes from server configuration and cannot be permanently revoked here",
            409,
        )
    await app_state.db.fishnet.delete_one({"_id": key})
    del FISHNET_KEYS[key]
    app_state.workers.discard(key)
    app_state.fishnet_worker_last_seen.pop(key, None)
    if name not in FISHNET_KEYS.values():
        app_state.fishnet_monitor.pop(name, None)
        app_state.fishnet_versions.pop(name, None)
    await record_mod_action(
        app_state,
        moderator,
        SITE_LOG_TARGET,
        "fishnet_key_removed",
        name,
    )
    return _success("fishnet_key_removed", f"Fishnet key for {name} removed.")
