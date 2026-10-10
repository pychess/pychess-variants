from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime

import aiohttp_session
from aiohttp import web
from aiohttp_sse import sse_response
from const import SSE_EVENT_QUEUE_MAXSIZE, SYSTEM_USER
from json_utils import json_dumps
from json_utils import json_response as raw_json_response
from link_filter import sanitize_user_message
from newid import id8, new_id
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from session_security import session_expiry_timeout
from sse_utils import consume_sse_queue, enqueue_sse_payload, send_sse_payload
from utils import notification_items_for_user

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
MAX_MSG_LEN = 2000
THREAD_MSG_PAGE_SIZE = 100
THREAD_LIST_LIMIT = 80

INBOX_ERROR_CODES = {
    "Login required": "login_required",
    "Invalid contact": "invalid_contact",
    "User not found": "user_not_found",
    "Invalid before value": "invalid_before",
    "Invalid request": "invalid_request",
    "Message is empty": "message_empty",
    "Too many similar messages. Please wait and retry.": "too_many_similar_messages",
    "Cannot send messages from this account": "cannot_send_from_account",
    "User is blocked": "user_blocked",
    "Cannot message this user": "cannot_message_user",
    "Only friends can message this user": "friends_only",
}


def inbox_error_code(message: str) -> str | None:
    if message.startswith("Message too long (max "):
        return "message_too_long"
    if message == f"{SYSTEM_USER} doesn't accept new messages.":
        return "system_user_no_messages"
    if message == f"{SYSTEM_USER} system messages cannot be deleted.":
        return "system_messages_cannot_delete"
    return INBOX_ERROR_CODES.get(message)


def json_response(payload: dict[str, object], *, status: int = 200) -> web.Response:
    if payload.get("type") == "error" and "code" not in payload:
        message = payload.get("message")
        if isinstance(message, str):
            code = inbox_error_code(message)
            if code is not None:
                payload = {**payload, "code": code}
    return raw_json_response(payload, status=status)


def _thread_id(user1: str, user2: str) -> str:
    first, second = sorted((user1, user2), key=lambda x: (x.lower(), x))
    return f"{first}:{second}"


def _message_doc(
    sender: str, recipient: str, text: str, now: datetime, *, message_id: str
) -> dict[str, object]:
    return {
        "_id": message_id,
        "tid": _thread_id(sender, recipient),
        "from": sender,
        "to": recipient,
        "text": text,
        "createdAt": now,
    }


def _thread_update(sender: str, recipient: str, text: str, now: datetime) -> dict[str, object]:
    return {
        "$set": {
            "users": [sender, recipient],
            "updatedAt": now,
            "lastMsg": {
                "user": sender,
                "text": text,
                "createdAt": now,
            },
            "readBy": [sender],
        },
        "$pull": {"deletedBy": {"$in": [sender, recipient]}},
    }


async def send_system_inbox_messages(
    app_state, recipients: list[str], text: str, *, batch_size: int = 200
) -> int:
    """Persist one PyChess inbox message per recipient without loading offline users."""
    if app_state.db is None or not recipients:
        return 0

    now = datetime.now(UTC)
    sent = 0
    unique_recipients = list(dict.fromkeys(user for user in recipients if user != SYSTEM_USER))

    for offset in range(0, len(unique_recipients), batch_size):
        batch = unique_recipients[offset : offset + batch_size]
        message_docs = [
            _message_doc(
                SYSTEM_USER,
                recipient,
                text,
                now,
                message_id=id8() + id8(),
            )
            for recipient in batch
        ]
        await app_state.db.inbox_msg.insert_many(message_docs, ordered=False)

        thread_ids = {_thread_id(SYSTEM_USER, recipient) for recipient in batch}
        existing_ids = {
            doc["_id"]
            async for doc in app_state.db.inbox_thread.find(
                {"_id": {"$in": list(thread_ids)}}, projection={"_id": 1}
            )
        }
        if existing_ids:
            await app_state.db.inbox_thread.update_many(
                {"_id": {"$in": list(existing_ids)}},
                {
                    "$set": {
                        "updatedAt": now,
                        "lastMsg": {
                            "user": SYSTEM_USER,
                            "text": text,
                            "createdAt": now,
                        },
                        "readBy": [SYSTEM_USER],
                        "deletedBy": [],
                    }
                },
            )

        new_threads = [
            {
                "_id": _thread_id(SYSTEM_USER, recipient),
                "users": [SYSTEM_USER, recipient],
                "updatedAt": now,
                "lastMsg": {
                    "user": SYSTEM_USER,
                    "text": text,
                    "createdAt": now,
                },
                "readBy": [SYSTEM_USER],
            }
            for recipient in batch
            if _thread_id(SYSTEM_USER, recipient) not in existing_ids
        ]
        if new_threads:
            await app_state.db.inbox_thread.insert_many(new_threads, ordered=False)
        sent += len(batch)

        for recipient in batch:
            if recipient in app_state.users.data:
                await _push_inbox_state(app_state, recipient, SYSTEM_USER)
        await asyncio.sleep(0)

    return sent


def _other_user(users: list[str], me: str) -> str | None:
    for user in users:
        if user != me:
            return user
    return None


async def _can_send_to_contact(app_state, me, contact: str, profile) -> bool:
    if not profile.pm_friends_only:
        return True
    if contact in me.following:
        return True
    if app_state.db is None:
        return False
    existing = await app_state.db.inbox_thread.find_one(
        {"_id": _thread_id(me.username, contact), "deletedBy": {"$ne": contact}},
        projection={"_id": 1},
    )
    return existing is not None


async def _session_username(request: web.Request) -> str | None:
    session = await aiohttp_session.get_session(request)
    return session.get("user_name")


async def _unread_count(app_state, username: str) -> int:
    if app_state.db is None:
        return 0
    return await app_state.db.inbox_thread.count_documents(
        {
            "users": username,
            "deletedBy": {"$ne": username},
            "lastMsg.user": {"$ne": username},
            "readBy": {"$ne": username},
        }
    )


async def _push_inbox_state(app_state, username: str, thread_contact: str | None = None) -> None:
    if app_state.db is None:
        return
    # Inbox delivery must not load an otherwise-offline recipient into the
    # process-wide Users cache. Persisted threads are read from MongoDB when the
    # recipient next connects; this helper only pushes to existing live streams.
    user = app_state.users.data.get(username)
    if user is None:
        return

    inbox_channels = tuple(user.inbox_channels)
    if inbox_channels:
        payload = json_dumps(
            {
                "unread": await _unread_count(app_state, username),
                "thread": thread_contact,
            }
        )
        for queue in inbox_channels:
            enqueue_sse_payload(queue, payload)

    notify_channels = tuple(user.notify_channels)
    if notify_channels:
        notify_payload = json_dumps(await notification_items_for_user(app_state, user, 0))
        for queue in notify_channels:
            enqueue_sse_payload(queue, notify_payload, replace_pending=True)


async def inbox_unread(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _session_username(request)
    if username is None:
        return json_response({"unread": 0})
    return json_response({"unread": await _unread_count(app_state, username)})


async def inbox_threads(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _session_username(request)
    if username is None or app_state.db is None:
        return json_response({"threads": []})

    cursor = app_state.db.inbox_thread.find({"users": username, "deletedBy": {"$ne": username}})
    cursor.sort("updatedAt", -1)
    cursor.limit(THREAD_LIST_LIMIT)
    docs = await cursor.to_list(length=THREAD_LIST_LIMIT)

    contacts = [
        contact
        for contact in (_other_user(doc.get("users", []), username) for doc in docs)
        if contact is not None
    ]
    ordinary_contacts = [contact for contact in contacts if contact != SYSTEM_USER]
    titles, patrons = await app_state.public_users.get_titles_and_patrons(ordinary_contacts)

    threads: list[dict[str, object]] = []
    for doc in docs:
        users = doc.get("users", [])
        contact = _other_user(users, username)
        if contact is None:
            continue
        live_contact = app_state.users.data.get(contact)
        last_msg = doc.get("lastMsg", {})
        read_by = set(doc.get("readBy", []))
        unread = last_msg.get("user") != username and username not in read_by
        threads.append(
            {
                "user": contact,
                "title": "" if contact == SYSTEM_USER else titles.get(contact, ""),
                "system": contact == SYSTEM_USER,
                "online": bool(live_contact and live_contact.online),
                "patron": contact in patrons,
                "updatedAt": doc.get("updatedAt"),
                "unread": unread,
                "lastMsg": {
                    "user": last_msg.get("user", ""),
                    "text": last_msg.get("text", ""),
                    "createdAt": last_msg.get("createdAt"),
                },
            }
        )

    return json_response({"threads": threads})


async def inbox_thread(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _session_username(request)
    contact = request.match_info.get("contact", "")

    if username is None or app_state.db is None:
        return json_response({"type": "error", "message": "Login required"}, status=401)

    if not USERNAME_RE.match(contact) or contact == username:
        return json_response({"type": "error", "message": "Invalid contact"}, status=400)

    me = await app_state.users.get(username)
    profile = await app_state.public_users.get_profile(contact)
    if profile is None or not profile.enabled or profile.username.startswith("Anon-"):
        return json_response({"type": "error", "message": "User not found"}, status=404)
    system_contact = contact == SYSTEM_USER
    blocked_by_me = False if system_contact else contact in me.blocked
    blocked_by_them = False if system_contact else username in profile.blocked
    can_message = (
        (not system_contact)
        and (not blocked_by_me)
        and (not blocked_by_them)
        and await _can_send_to_contact(app_state, me, contact, profile)
    )

    tid = _thread_id(username, contact)
    before = request.rel_url.query.get("before")
    query: dict[str, object] = {"tid": tid, "deletedBy": {"$ne": username}}
    if before is not None:
        try:
            before_dt = datetime.fromtimestamp(int(before) / 1000.0, tz=UTC)
        except ValueError:
            return json_response({"type": "error", "message": "Invalid before value"}, status=400)
        query["createdAt"] = {"$lt": before_dt}

    cursor = app_state.db.inbox_msg.find(query)
    cursor.sort("createdAt", -1)
    cursor.limit(THREAD_MSG_PAGE_SIZE)
    msgs_desc = await cursor.to_list(length=THREAD_MSG_PAGE_SIZE)
    msgs = list(reversed(msgs_desc))

    has_more = False
    if msgs:
        oldest_created_at = msgs[0].get("createdAt")
        if isinstance(oldest_created_at, datetime):
            older = await app_state.db.inbox_msg.find_one(
                {
                    "tid": tid,
                    "deletedBy": {"$ne": username},
                    "createdAt": {"$lt": oldest_created_at},
                },
                projection={"_id": 1},
            )
            has_more = older is not None

    return json_response(
        {
            "contact": {
                "name": profile.username,
                "title": "" if system_contact else profile.title,
                "system": system_contact,
                "patron": profile.patron,
                "online": bool(
                    app_state.users.data.get(profile.username)
                    and app_state.users.data[profile.username].online
                ),
                "canMessage": can_message,
                "blockedByMe": blocked_by_me,
                "blockedByThem": blocked_by_them,
            },
            "messages": msgs,
            "hasMore": has_more,
        }
    )


async def inbox_post(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _session_username(request)
    contact = request.match_info.get("contact", "")

    if username is None or app_state.db is None:
        return json_response({"type": "error", "message": "Login required"}, status=401)

    if not USERNAME_RE.match(contact) or contact == username:
        return json_response({"type": "error", "message": "Invalid contact"}, status=400)
    if contact == SYSTEM_USER:
        return json_response(
            {"type": "error", "message": f"{SYSTEM_USER} doesn't accept new messages."},
            status=403,
        )

    data = await read_post_data(request)
    if data is None:
        return json_response({"type": "error", "message": "Invalid request"}, status=400)

    text = str(data.get("text") or "").strip()
    if len(text) == 0:
        return json_response({"type": "error", "message": "Message is empty"}, status=400)
    if len(text) > MAX_MSG_LEN:
        return json_response(
            {"type": "error", "message": f"Message too long (max {MAX_MSG_LEN})"},
            status=400,
        )
    text = sanitize_user_message(text)
    if not app_state.chat_flood.allow_message(f"inbox:{username}:{contact}", text):
        return json_response(
            {"type": "error", "message": "Too many similar messages. Please wait and retry."},
            status=429,
        )

    me = await app_state.users.get(username)
    if bool(getattr(me, "shadowban", False)):
        return json_response(
            {"type": "error", "message": "Cannot send messages from this account"},
            status=403,
        )
    if contact in me.blocked:
        return json_response({"type": "error", "message": "User is blocked"}, status=403)

    profile = await app_state.public_users.get_profile(contact)
    if profile is None or not profile.enabled or profile.username.startswith("Anon-"):
        return json_response({"type": "error", "message": "User not found"}, status=404)
    if username in profile.blocked:
        return json_response({"type": "error", "message": "Cannot message this user"}, status=403)
    if not await _can_send_to_contact(app_state, me, contact, profile):
        return json_response(
            {"type": "error", "message": "Only friends can message this user"},
            status=403,
        )

    now = datetime.now(UTC)
    tid = _thread_id(username, contact)

    msg_id = await new_id(app_state.db.inbox_msg)
    msg_doc = _message_doc(username, contact, text, now, message_id=msg_id)

    await app_state.db.inbox_msg.insert_one(msg_doc)
    await app_state.db.inbox_thread.update_one(
        {"_id": tid},
        _thread_update(username, contact, text, now),
        upsert=True,
    )

    await _push_inbox_state(app_state, username, contact)
    await _push_inbox_state(app_state, contact, username)

    return json_response({"ok": True, "message": msg_doc})


async def inbox_read(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _session_username(request)
    contact = request.match_info.get("contact", "")

    if username is None or app_state.db is None:
        return json_response({"type": "error", "message": "Login required"}, status=401)

    if not USERNAME_RE.match(contact) or contact == username:
        return json_response({"type": "error", "message": "Invalid contact"}, status=400)

    tid = _thread_id(username, contact)
    update_result = await app_state.db.inbox_thread.update_one(
        {"_id": tid, "lastMsg.user": {"$ne": username}},
        {"$addToSet": {"readBy": username}},
    )
    if update_result.modified_count > 0:
        await _push_inbox_state(app_state, username, contact)
    return json_response({"ok": True})


async def inbox_delete(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    username = await _session_username(request)
    contact = request.match_info.get("contact", "")

    if username is None or app_state.db is None:
        return json_response({"type": "error", "message": "Login required"}, status=401)

    if not USERNAME_RE.match(contact) or contact == username:
        return json_response({"type": "error", "message": "Invalid contact"}, status=400)
    if contact == SYSTEM_USER:
        return json_response(
            {"type": "error", "message": f"{SYSTEM_USER} system messages cannot be deleted."},
            status=403,
        )

    tid = _thread_id(username, contact)
    await app_state.db.inbox_msg.update_many({"tid": tid}, {"$addToSet": {"deletedBy": username}})
    await app_state.db.inbox_thread.update_one(
        {"_id": tid},
        {"$addToSet": {"deletedBy": username}},
    )
    await _push_inbox_state(app_state, username, contact)
    return json_response({"ok": True})


async def subscribe_inbox(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    username = session.get("user_name")
    if username is None:
        return json_response({})

    user = await app_state.users.get(username)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SSE_EVENT_QUEUE_MAXSIZE)
    user.inbox_channels.add(queue)
    response: web.StreamResponse = web.Response(status=200)

    try:
        async with session_expiry_timeout(session, user), sse_response(request) as response:
            await send_sse_payload(
                response,
                json_dumps({"unread": await _unread_count(app_state, username)}),
            )
            await consume_sse_queue(response, queue)
    except Exception:
        pass
    finally:
        user.inbox_channels.discard(queue)
        queue.shutdown(immediate=True)

    return response
