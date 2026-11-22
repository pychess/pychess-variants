"""Account-owned local engine registrations; searches never pass through this API."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import aiohttp_session
from aiohttp import web
from bot_accounts import bot_token_hash, get_db_token_owner
from csrf import _same_origin, csrf_exempt
from pychess_global_app_state_utils import get_app_state

REGISTRATION_SECONDS = 90
MAX_REGISTRATION_BYTES = 96 * 1024


def response(data: Any, *, status: int = 200) -> web.Response:
    return web.json_response(
        data, status=status, headers={"Cache-Control": "no-store", "Vary": "Cookie"}
    )


async def token_owner(request: web.Request, scope: str = "engine:write") -> tuple[Any, str, str]:
    app_state = get_app_state(request.app)
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise web.HTTPUnauthorized()
    token = authorization[7:]
    if not token or len(token) > 256:
        raise web.HTTPUnauthorized()
    owner = await get_db_token_owner(app_state, token, mark_used=True, required_scope=scope)
    if owner is None:
        raise web.HTTPForbidden()
    doc = await app_state.db.bot_token.find_one(
        {"tokenHash": bot_token_hash(token), "revokedAt": {"$exists": False}}
    )
    if doc is None:
        raise web.HTTPForbidden()
    return app_state, str(owner["_id"]), str(doc["_id"])


async def session_owner(request: web.Request) -> tuple[Any, str]:
    if request.headers.get("Sec-Fetch-Site") == "cross-site" or (
        "Origin" in request.headers and not _same_origin(request, request.headers["Origin"])
    ):
        raise web.HTTPForbidden()
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    user = await app_state.users.get(session.get("user_name"))
    if user.anon or not user.enabled:
        raise web.HTTPUnauthorized()
    return app_state, user.username


def validate_engine(engine: Any) -> dict[str, Any]:
    if not isinstance(engine, dict):
        raise web.HTTPBadRequest(text="Invalid engine capabilities")
    name = engine.get("name")
    variants = engine.get("variants")
    if (
        not isinstance(name, str)
        or not name.strip()
        or len(name) > 200
        or not isinstance(variants, list)
        or len(variants) > 512
        or not all(
            isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", v) for v in variants
        )
        or type(engine.get("chess960")) is not bool
        or type(engine.get("customRules")) is not bool
    ):
        raise web.HTTPBadRequest(text="Invalid engine capabilities")
    for key, minimum, maximum in (
        ("maxThreads", 1, 1024),
        ("maxHash", 0, 1048576),
        ("maxMultiPv", 1, 20),
    ):
        value = engine.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            raise web.HTTPBadRequest(text="Invalid engine limits")
    parsed = {
        key: engine[key]
        for key in (
            "name",
            "variants",
            "chess960",
            "customRules",
            "maxThreads",
            "maxHash",
            "maxMultiPv",
        )
    }
    if "adapters" in engine:
        raise web.HTTPBadRequest(text="Only one engine can be registered per local app")
    if "variantRestrictions" in engine:
        restrictions = engine["variantRestrictions"]
        if not isinstance(restrictions, dict) or any(
            variant not in variants
            or not isinstance(flags, dict)
            or set(flags) != {"chess960", "customRules"}
            or any(
                type(value) is not bool or (value and not engine[key])
                for key, value in flags.items()
            )
            for variant, flags in restrictions.items()
        ):
            raise web.HTTPBadRequest(text="Invalid variant restrictions")
        parsed["variantRestrictions"] = restrictions
    return parsed


async def registration_body(request: web.Request) -> dict[str, Any]:
    if request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType()
    raw = bytearray()
    async for chunk in request.content.iter_chunked(16384):
        raw.extend(chunk)
        if len(raw) > MAX_REGISTRATION_BYTES:
            raise web.HTTPRequestEntityTooLarge(
                max_size=MAX_REGISTRATION_BYTES, actual_size=len(raw)
            )

    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise web.HTTPBadRequest(text="Invalid registration JSON") from None
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("instanceId"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", body["instanceId"])
    ):
        raise web.HTTPBadRequest(text="Invalid engine instance")
    return body


@csrf_exempt
async def register_engine(request: web.Request) -> web.Response:
    app_state, username, token_id = await token_owner(request)
    body = await registration_body(request)
    address = body.get("address")
    secret = body.get("clientSecret")
    if (
        not isinstance(address, str)
        or not isinstance(secret, str)
        or not re.fullmatch(r"[\x21-\x7e]{32,256}", secret)
    ):
        raise web.HTTPBadRequest(text="Invalid local connection")
    try:
        parsed = urlsplit(address)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.port == 0
        ):
            raise ValueError
        address = f"http://127.0.0.1:{parsed.port or 80}"
    except ValueError:
        raise web.HTTPBadRequest(text="Only IPv4 loopback engines can be registered") from None
    if type(body.get("protocolVersion")) is not int or body["protocolVersion"] != 1:
        raise web.HTTPBadRequest(text="Invalid protocol version")
    engine = validate_engine(body.get("engine"))
    await app_state.db.external_engine.update_one(
        {"_id": token_id},
        {
            "$set": {
                "user": username,
                "address": address,
                "clientSecret": secret,
                "engine": engine,
                "instanceId": body["instanceId"],
                "expiresAt": datetime.now(UTC) + timedelta(seconds=REGISTRATION_SECONDS),
            }
        },
        upsert=True,
    )
    return response({"id": token_id, "heartbeatSeconds": 30})


@csrf_exempt
async def heartbeat_engine(request: web.Request) -> web.Response:
    app_state, username, token_id = await token_owner(request)
    body = await registration_body(request)
    if request.match_info["engineId"] != token_id:
        raise web.HTTPForbidden()
    result = await app_state.db.external_engine.update_one(
        {"_id": token_id, "user": username, "instanceId": body["instanceId"]},
        {"$set": {"expiresAt": datetime.now(UTC) + timedelta(seconds=REGISTRATION_SECONDS)}},
    )
    if not result.matched_count:
        raise web.HTTPConflict(text="Engine registration was removed or replaced")
    return response({"ok": True})


@csrf_exempt
async def stop_engine(request: web.Request) -> web.Response:
    app_state, username, token_id = await token_owner(request)
    body = await registration_body(request)
    if request.match_info["engineId"] != token_id:
        raise web.HTTPForbidden()
    await app_state.db.external_engine.delete_one(
        {"_id": token_id, "user": username, "instanceId": body["instanceId"]}
    )
    return response({"ok": True})


async def list_engines(request: web.Request) -> web.Response:
    # API tokens may enumerate registrations, but only a signed-in browser
    # session can retrieve the loopback bearer credential used for analysis.
    # This also applies to tokens granted both engine:read and engine:write.
    include_secret = not request.headers.get("Authorization")
    if include_secret:
        app_state, username = await session_owner(request)
    else:
        app_state, username, _ = await token_owner(request, "engine:read")
    if app_state.db is None:
        return response([])
    tokens = await app_state.db.bot_token.find(
        {"user": username, "scopes": "engine:write", "revokedAt": {"$exists": False}}
    ).to_list(length=100)
    ids = [doc["_id"] for doc in tokens]
    docs = await app_state.db.external_engine.find(
        {"user": username, "_id": {"$in": ids}, "expiresAt": {"$gt": datetime.now(UTC)}}
    ).to_list(length=100)
    return response(
        [
            {
                "id": doc["_id"],
                "address": doc["address"],
                **({"token": doc["clientSecret"]} if include_secret else {}),
                "engine": doc["engine"],
            }
            for doc in docs
        ]
    )


async def delete_engine(request: web.Request) -> web.Response:
    app_state, username = await session_owner(request)
    result = await app_state.db.external_engine.delete_one(
        {"_id": request.match_info["engineId"], "user": username}
    )
    if not result.deleted_count:
        raise web.HTTPNotFound()
    return response({"ok": True})
