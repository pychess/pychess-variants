from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypedDict, cast

import aiohttp_session
from aiohttp import web
from aiohttp_sse import sse_response
from const import SSE_SNAPSHOT_QUEUE_MAXSIZE
from json_utils import json_dumps, json_response
from misc import time_control_str
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from seek import (
    ACTIVE_DIRECT_CHALLENGE_STATUSES,
    DIRECT_CHALLENGE_CANCELED,
    DIRECT_CHALLENGE_CREATED,
    DIRECT_CHALLENGE_DECLINED,
    DIRECT_CHALLENGE_OFFLINE,
    resolve_decline_reason,
)
from session_security import session_expiry_timeout
from sse_utils import SSEResponse, consume_sse_queue, enqueue_sse_payload, send_sse_payload
from utils import join_seek, remove_seek

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from seek import Seek


class HeaderChallenge(TypedDict):
    id: str
    challenger: str
    challengerTitle: str
    opponent: str
    incoming: bool
    variant: str
    chess960: bool | None
    rated: bool
    color: str
    tc: str
    expireAt: str
    status: str
    declineReason: str


class HeaderChallengeEnvelope(TypedDict, total=False):
    challenges: list[HeaderChallenge]
    gameId: str


def challenge_participants(seek: Seek) -> tuple[str, ...]:
    usernames = [seek.creator.username]
    if seek.target:
        usernames.append(seek.target)
    # Preserve order while removing duplicates.
    return tuple(dict.fromkeys(usernames))


def serialize_challenge_for_user(seek: Seek, username: str) -> HeaderChallenge:
    incoming = seek.target == username and seek.creator.username != username
    opponent = seek.creator.username if incoming else seek.target
    expire_at = seek.expire_at.isoformat() if seek.expire_at is not None else ""
    return {
        "id": seek.id,
        "challenger": seek.creator.username,
        "challengerTitle": seek.creator.title,
        "opponent": opponent,
        "incoming": incoming,
        "variant": seek.variant,
        "chess960": seek.chess960,
        "rated": bool(seek.rated),
        "color": seek.color,
        "tc": time_control_str(seek.base, seek.inc, seek.byoyomi_period, seek.day),
        "expireAt": expire_at,
        "status": seek.challenge_status or DIRECT_CHALLENGE_CREATED,
        "declineReason": seek.challenge_decline_reason or "",
    }


def _remove_seek_from_state(app_state: PychessGlobalAppState, seek: Seek) -> None:
    if seek.game_id is not None:
        app_state.invites.pop(seek.game_id, None)
    remove_seek(app_state.seeks, seek)


def cleanup_expired_direct_challenges(app_state: PychessGlobalAppState) -> set[str]:
    affected_users: set[str] = set()
    for seek in tuple(app_state.seeks.values()):
        if not seek.is_direct_challenge or not seek.is_expired():
            continue
        affected_users.update(challenge_participants(seek))
        _remove_seek_from_state(app_state, seek)
    return affected_users


def direct_challenge_is_visible_for_user(seek: Seek, username: str) -> bool:
    if (
        not seek.is_direct_challenge
        or seek.pending
        or seek.is_expired()
        or seek.challenge_status is None
        or seek.challenge_status == DIRECT_CHALLENGE_CANCELED
    ):
        return False
    return not (seek.challenge_status == DIRECT_CHALLENGE_DECLINED and seek.target == username)


def set_direct_challenge_status(seek: Seek, status: str) -> bool:
    if not seek.is_direct_challenge or seek.challenge_status == status:
        return False
    seek.set_challenge_status(status)
    return True


async def reactivate_direct_challenges(app_state: PychessGlobalAppState, username: str) -> None:
    user = await app_state.users.get(username)
    changed_users: set[str] = set()
    for seek in tuple(user.seeks.values()):
        if (
            seek.is_direct_challenge
            and seek.creator.username == username
            and seek.challenge_status == DIRECT_CHALLENGE_OFFLINE
            and not seek.is_expired()
        ):
            seek.set_challenge_status(DIRECT_CHALLENGE_CREATED)
            changed_users.update(challenge_participants(seek))
    if changed_users:
        await broadcast_challenge_state(app_state, changed_users)


def schedule_direct_challenge_offline(
    app_state: PychessGlobalAppState, username: str, delay_seconds: int = 20
) -> None:
    user = app_state.users[username]
    task = getattr(user, "challenge_offline_task", None)
    if task is not None and not task.done():
        return

    async def mark_offline() -> None:
        await asyncio.sleep(delay_seconds)
        user.update_online()
        if user.online:
            return
        changed_users: set[str] = set()
        for seek in tuple(user.seeks.values()):
            if (
                seek.is_direct_challenge
                and seek.creator.username == username
                and seek.challenge_status == DIRECT_CHALLENGE_CREATED
                and not seek.is_expired()
            ):
                seek.set_challenge_status(DIRECT_CHALLENGE_OFFLINE)
                changed_users.update(challenge_participants(seek))
        if changed_users:
            await broadcast_challenge_state(app_state, changed_users)

    task = user.create_background_task(
        mark_offline(),
        name="direct-challenge-offline-%s" % username,
    )
    user.challenge_offline_task = task

    def _clear_done(done_task: asyncio.Task[None]) -> None:
        if user.challenge_offline_task is done_task:
            user.challenge_offline_task = None

    task.add_done_callback(_clear_done)


def cancel_direct_challenge_offline(user) -> None:
    task = getattr(user, "challenge_offline_task", None)
    if task is not None and not task.done():
        task.cancel()
    user.challenge_offline_task = None


def get_user_challenges(app_state: PychessGlobalAppState, username: str) -> list[HeaderChallenge]:
    cleanup_expired_direct_challenges(app_state)
    users = cast(dict[str, Any], getattr(app_state.users, "data", app_state.users))
    viewer = users.get(username)

    def visible_to_viewer(seek: Seek) -> bool:
        if viewer is None:
            return True
        opponent = seek.creator.username if seek.target == username else seek.target
        if opponent in viewer.blocked:
            return False
        if seek.creator.username == username:
            target_user = users.get(seek.target)
            return not (target_user is not None and username in target_user.blocked)
        return username not in seek.creator.blocked

    challenges = [
        serialize_challenge_for_user(seek, username)
        for seek in reversed(tuple(app_state.seeks.values()))
        if direct_challenge_is_visible_for_user(seek, username)
        and username in challenge_participants(seek)
        and visible_to_viewer(seek)
    ]
    challenges.sort(
        key=lambda challenge: (
            challenge["status"] not in ACTIVE_DIRECT_CHALLENGE_STATUSES,
            not challenge["incoming"],
            challenge["id"],
        ),
        reverse=False,
    )
    return challenges


def challenge_envelope(
    app_state: PychessGlobalAppState, username: str, game_id: str | None = None
) -> HeaderChallengeEnvelope:
    payload: HeaderChallengeEnvelope = {"challenges": get_user_challenges(app_state, username)}
    if game_id is not None:
        payload["gameId"] = game_id
    return payload


async def push_challenge_state(
    app_state: PychessGlobalAppState, username: str, game_id: str | None = None
) -> None:
    user = await app_state.users.get(username)
    payload = json_dumps(challenge_envelope(app_state, username, game_id))
    for queue in tuple(user.challenge_channels):
        enqueue_sse_payload(queue, payload, replace_pending=True)


async def broadcast_challenge_state(
    app_state: PychessGlobalAppState,
    usernames: tuple[str, ...] | list[str] | set[str],
    *,
    game_ids: dict[str, str] | None = None,
) -> None:
    for username in usernames:
        await push_challenge_state(
            app_state, username, None if game_ids is None else game_ids.get(username)
        )


async def get_header_challenges(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({"challenges": []})
    return json_response(challenge_envelope(app_state, session_user))


async def _consume_header_channels(
    response: SSEResponse,
    channels: dict[str, asyncio.Queue[str]],
) -> None:
    merged: asyncio.Queue[str] = asyncio.Queue(maxsize=max(1, len(channels)))

    async def forward(channel: str, source: asyncio.Queue[str]) -> None:
        while True:
            try:
                payload = await source.get()
            except asyncio.QueueShutDown:
                # Any revoked source ends the whole multiplexed subscription.
                # Wake the merged consumer so it reaches the handler's cleanup.
                merged.shutdown(immediate=True)
                return

            try:
                await merged.put(json_dumps({"channel": channel, "payload": payload}))
            except asyncio.QueueShutDown:
                return
            finally:
                source.task_done()

    tasks = [asyncio.create_task(forward(channel, queue)) for channel, queue in channels.items()]
    try:
        await consume_sse_queue(response, merged)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        merged.shutdown(immediate=True)


async def subscribe_header(request: web.Request) -> web.StreamResponse:
    """Multiplex header challenges and notifications over one SSE connection."""

    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({})

    user = await app_state.users.get(session_user)
    cancel_direct_challenge_offline(user)
    challenge_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SSE_SNAPSHOT_QUEUE_MAXSIZE)
    notify_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SSE_SNAPSHOT_QUEUE_MAXSIZE)
    user.challenge_channels.add(challenge_queue)
    user.notify_channels.add(notify_queue)
    user.update_online()
    await reactivate_direct_challenges(app_state, session_user)

    response: web.StreamResponse = web.Response(status=200)
    try:
        async with session_expiry_timeout(session, user), sse_response(request) as response:
            await send_sse_payload(
                response,
                json_dumps(
                    {
                        "channel": "challenges",
                        "payload": json_dumps(challenge_envelope(app_state, session_user)),
                    }
                ),
            )
            await _consume_header_channels(
                response,
                {
                    "challenges": challenge_queue,
                    "notifications": notify_queue,
                },
            )
    except Exception:
        pass
    finally:
        user.challenge_channels.discard(challenge_queue)
        user.notify_channels.discard(notify_queue)
        challenge_queue.shutdown(immediate=True)
        notify_queue.shutdown(immediate=True)
        user.update_online()
        if not user.online:
            schedule_direct_challenge_offline(app_state, session_user)
    return response


async def subscribe_challenges(request: web.Request) -> web.StreamResponse:
    # Compatibility for tabs running the pre-multiplexing client.
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({})

    user = await app_state.users.get(session_user)
    cancel_direct_challenge_offline(user)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SSE_SNAPSHOT_QUEUE_MAXSIZE)
    user.challenge_channels.add(queue)
    user.update_online()
    await reactivate_direct_challenges(app_state, session_user)
    response: web.StreamResponse = web.Response(status=200)
    try:
        async with session_expiry_timeout(session, user), sse_response(request) as response:
            await send_sse_payload(
                response,
                json_dumps(challenge_envelope(app_state, session_user)),
            )
            await consume_sse_queue(response, queue)
    except Exception:
        pass
    finally:
        user.challenge_channels.discard(queue)
        queue.shutdown(immediate=True)
        user.update_online()
        if not user.online:
            schedule_direct_challenge_offline(app_state, session_user)
    return response


async def challenge_seek_accept(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({"type": "error", "message": "Login required"}, status=401)

    cleanup_expired_direct_challenges(app_state)

    seek_id = request.match_info.get("seekId")
    if seek_id is None or seek_id not in app_state.seeks:
        return json_response({"type": "error", "message": "Challenge not found"}, status=404)

    user = await app_state.users.get(session_user)
    seek = app_state.seeks[seek_id]
    if (
        not seek.is_direct_challenge
        or seek.target != user.username
        or seek.challenge_status not in ACTIVE_DIRECT_CHALLENGE_STATUSES
    ):
        return json_response({"type": "error", "message": "Challenge not available"}, status=403)

    result = await join_seek(app_state, user, seek)
    if result["type"] == "error":
        return json_response(result, status=403)
    game_ids: dict[str, str] | None = None
    if result["type"] == "new_game" and len(seek.creator.lobby_sockets) == 0:
        game_ids = {seek.creator.username: result["gameId"]}

    await broadcast_challenge_state(app_state, challenge_participants(seek), game_ids=game_ids)
    await app_state.lobby.lobby_broadcast_seeks()
    return json_response(result)


async def challenge_seek_decline(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({"type": "error", "message": "Login required"}, status=401)

    cleanup_expired_direct_challenges(app_state)

    seek_id = request.match_info.get("seekId")
    if seek_id is None or seek_id not in app_state.seeks:
        return json_response({"type": "error", "message": "Challenge not found"}, status=404)

    user = await app_state.users.get(session_user)
    seek = app_state.seeks[seek_id]
    if (
        not seek.is_direct_challenge
        or seek.target != user.username
        or seek.challenge_status not in ACTIVE_DIRECT_CHALLENGE_STATUSES
    ):
        return json_response({"type": "error", "message": "Challenge not available"}, status=403)

    usernames = challenge_participants(seek)
    reason_data = await read_post_data(request)
    if reason_data is None:
        return json_response({})
    reason_key = reason_data.get("reason")
    decline_reason = resolve_decline_reason(None if reason_key is None else str(reason_key))
    seek.set_challenge_decline_reason(decline_reason)
    set_direct_challenge_status(seek, DIRECT_CHALLENGE_DECLINED)
    await broadcast_challenge_state(app_state, usernames)
    await app_state.lobby.lobby_broadcast_seeks()
    return json_response({"ok": True})


async def challenge_seek_cancel(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({"type": "error", "message": "Login required"}, status=401)

    cleanup_expired_direct_challenges(app_state)

    seek_id = request.match_info.get("seekId")
    if seek_id is None or seek_id not in app_state.seeks:
        return json_response({"type": "error", "message": "Challenge not found"}, status=404)

    user = await app_state.users.get(session_user)
    seek = app_state.seeks[seek_id]
    if (
        not seek.is_direct_challenge
        or seek.creator.username != user.username
        or seek.challenge_status not in ACTIVE_DIRECT_CHALLENGE_STATUSES
    ):
        return json_response({"type": "error", "message": "Challenge not available"}, status=403)

    usernames = challenge_participants(seek)
    set_direct_challenge_status(seek, DIRECT_CHALLENGE_CANCELED)
    await broadcast_challenge_state(app_state, usernames)
    await app_state.lobby.lobby_broadcast_seeks()
    return json_response({"ok": True})
