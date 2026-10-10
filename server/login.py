from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, TypedDict
from urllib.parse import urlencode

import aiohttp
import aiohttp_session
from aiohttp import web
from broadcast import round_broadcast
from const import STARTED, reserved
from json_utils import json_response
from newid import new_id
from oauth_config import oauth_config
from pychess_global_app_state_utils import get_app_state
from pymongo.errors import DuplicateKeyError
from request_utils import read_json_data
from security_evasion import (
    collect_client_signals,
    is_signup_blocked_by_signals,
    remember_user_signals,
)
from session_security import (
    auth_version_from_user_document,
    authenticate_session,
    revoke_user_sessions,
)
from settings import URI
from typedefs import REQUEST_NEW_SESSION_KEY
from typing_defs import UserDocument
from user_stats import DEFAULT_USER_COUNT
from websocket_utils import ws_send_json_many

log = logging.getLogger(__name__)

USERNAME_LOWER_FIELD = "username_lower"
REOPEN_TOKEN_TTL_MINUTES = 20
MAX_PENDING_OAUTH_FLOWS = 3

if TYPE_CHECKING:
    from user import User


class OAuthUserData(TypedDict, total=False):
    id: str
    username: str
    title: str
    closed: str
    tosViolation: str


class OAuthFlowData(TypedDict):
    provider: str
    code_verifier: str


def normalized_username(username: str) -> str:
    return username.lower()


async def username_exists(app_state, username: str) -> bool:
    username_lower = normalized_username(username)
    existing_user = await app_state.db.user.find_one(
        {
            "$or": [
                {"_id": username},
                {
                    USERNAME_LOWER_FIELD: {
                        "$eq": username_lower,
                        "$type": "string",
                    }
                },
            ]
        },
        projection={"_id": 1},
    )
    return existing_user is not None


def oauth_authorization_redirect(session: aiohttp_session.Session, provider: str) -> web.HTTPFound:
    config = oauth_config.get(provider)
    if config is None:
        raise web.HTTPBadRequest(text="Unknown sign-in provider")
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    flow: OAuthFlowData = {"provider": provider, "code_verifier": code_verifier}
    params = {
        "state": state,
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": URI + "/oauth/%s" % provider,
        "code_challenge": get_code_challenge(code_verifier),
        "code_challenge_method": "S256",
        "scope": config["scope"],
    }
    oauth_flows: dict[str, OAuthFlowData] = dict(session.get("oauth_flows", {}))
    oauth_flows[state] = flow
    session["oauth_flows"] = dict(list(oauth_flows.items())[-MAX_PENDING_OAUTH_FLOWS:])
    return web.HTTPFound(config["oauth_authorize_url"] + "?" + urlencode(params))


async def oauth(request: web.Request) -> web.StreamResponse:
    """Get oauth token with PKCE"""

    provider = request.match_info.get("provider")
    if TYPE_CHECKING:
        assert provider is not None
    redirect_uri = URI + "/oauth/%s" % provider

    config = oauth_config.get(provider)
    if config is None:
        raise web.HTTPBadRequest(text="Unknown sign-in provider")

    client_id = config["client_id"]
    client_secret = config.get("client_secret")

    oauth_token_url = config["oauth_token_url"]

    session = await aiohttp_session.get_session(request)
    code = request.rel_url.query.get("code")

    if code is None and "error" not in request.rel_url.query:
        return oauth_authorization_redirect(session, provider)
    else:
        returned_state = request.rel_url.query.get("state")
        oauth_flows: dict[str, OAuthFlowData] = dict(session.get("oauth_flows", {}))
        matching_state = next(
            (
                saved_state
                for saved_state in oauth_flows
                if returned_state is not None
                and secrets.compare_digest(returned_state, saved_state)
            ),
            None,
        )
        flow = oauth_flows.pop(matching_state, None) if matching_state is not None else None

        if oauth_flows:
            session["oauth_flows"] = oauth_flows
        else:
            session.pop("oauth_flows", None)

        if flow is None or flow["provider"] != provider:
            log.error("OAuth state value mismatch for provider '%s'", provider)
            return web.HTTPFound("/")

        if request.rel_url.query.get("error") is not None or not code:
            return web.HTTPFound("/")
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": flow["code_verifier"],
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }
        if client_secret is not None:
            data["client_secret"] = client_secret

        # print(oauth_token_url)
        # print(data)
        # print("----------------")

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with (
            aiohttp.ClientSession() as client_session,
            client_session.post(oauth_token_url, data=data, headers=headers) as resp,
        ):
            token_data: dict[str, str] = await resp.json()
            # print("OAUTH_DATA=", data)
            token = token_data.get("access_token")
            if token is not None:
                session["token"] = token
                return web.HTTPFound("/login/%s" % provider)
            else:
                log.error("Failed to get OAuth token for provider '%s'", provider)
                return web.HTTPFound("/")


async def login_choice(_request: web.Request) -> web.StreamResponse:
    """Open the provider chooser for provider-neutral login links."""
    return web.HTTPFound("/#login")


async def login(request: web.Request) -> web.StreamResponse:
    session = await aiohttp_session.get_session(request)

    provider = request.match_info.get("provider")
    if TYPE_CHECKING:
        assert provider is not None
    config = oauth_config.get(provider)
    if config is None:
        raise web.HTTPBadRequest(text="Unknown sign-in provider")
    redirect_path = "/oauth/%s" % provider

    if "token" not in session:
        return web.HTTPFound(redirect_path)

    account_api_url = config["account_api_url"]

    token: str = session["token"]
    user_data = await get_user_data(account_api_url, token)

    del session["token"]

    user_id = user_data.get("id")
    username = user_data.get("username", user_id)
    title = user_data.get("title", "")
    closed = user_data.get("closed", "")
    tosViolation = user_data.get("tosViolation", "")
    if TYPE_CHECKING:
        assert user_id is not None
        assert username is not None

    if reserved(username):
        log.error("User %s tried to log in.", username)
        return web.HTTPFound("/")

    elif tosViolation == "true":
        log.error("tosViolation user %s tried to log in.", username)
        return web.HTTPFound("/")

    elif closed == "true":
        log.error("closed user %s tried to log in.", username)
        return web.HTTPFound("/")

    log.info("+++ authenticated user: %s", username)
    app_state = get_app_state(request.app)
    signals = collect_client_signals(request)

    # For other OAuth providers, check if user needs to choose a username
    existing_user: UserDocument | None = await app_state.db.user.find_one(
        {"oauth_id": user_id, "oauth_provider": provider}
    )
    if existing_user:
        # User exists with this OAuth ID, use their existing username
        if not existing_user.get("enabled", True):
            closed_username = existing_user["_id"]
            can_self_reopen = existing_user.get("closeType") == "self" and not existing_user.get(
                "gdprErasedAt"
            )
            if can_self_reopen:
                log.info(
                    "Self-closed account %s tried to log in; redirecting to reopen flow.", username
                )
                now = datetime.now(UTC)
                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                await app_state.db.account_reopen_token.delete_many(
                    {
                        "$or": [
                            {"expiresAt": {"$lt": now}},
                            {"username": closed_username},
                        ]
                    }
                )
                token_id = await new_id(app_state.db.account_reopen_token)
                await app_state.db.account_reopen_token.insert_one(
                    {
                        "_id": token_id,
                        "username": closed_username,
                        "tokenHash": token_hash,
                        "createdAt": now,
                        "expiresAt": now + timedelta(minutes=REOPEN_TOKEN_TTL_MINUTES),
                        "oauthProvider": provider,
                    }
                )
                session["closed_account_user"] = closed_username
                return web.HTTPFound(f"/account/reopen?token={raw_token}")
            log.info("Disabled account %s tried to log in; self-reopen unavailable.", username)
            session.pop("closed_account_user", None)
            return web.HTTPFound("/contact")
        else:
            authenticate_session(
                session,
                existing_user["_id"],
                auth_version_from_user_document(existing_user),
            )
            request[REQUEST_NEW_SESSION_KEY] = True
            session.pop("closed_account_user", None)
            await remember_user_signals(app_state.db, existing_user["_id"], signals)

    else:
        blocked, match_reason = await is_signup_blocked_by_signals(app_state.db, signals)
        if blocked:
            log.warning(
                "Potential ban-evasion signup for %s (%s match); account will be auto-closed on confirmation",
                username,
                match_reason,
            )

        # New user from OAuth provider - needs to choose username
        session["oauth_id"] = user_id
        session["oauth_provider"] = provider
        session["oauth_username"] = username
        session["oauth_title"] = title
        session.pop("closed_account_user", None)
        return web.HTTPFound("/select-username")

    return web.HTTPFound("/")


async def get_user_data(url: str, token: str) -> OAuthUserData:
    async with aiohttp.ClientSession() as client_session:
        headers = {"Authorization": "Bearer %s" % token}
        async with client_session.get(url, headers=headers) as resp:
            data: OAuthUserData = await resp.json()
            # print("USER_DATA", data)
            return data


async def logout(request: web.Request | None, user: User | None = None) -> web.StreamResponse:
    if request is not None:
        # user clicked the logout
        app_state = get_app_state(request.app)
        session = await aiohttp_session.get_session(request)
        session_user = session.get("user_name")
        user = await app_state.users.get(session_user)
    else:
        # admin banned the user
        if TYPE_CHECKING:
            assert user is not None
        app_state = user.app_state

    if user is None:
        return web.HTTPFound("/")
    logout_response = {"type": "logout"}

    # Lose active games when ban() calls this from admin.py. Explicit browser
    # logout only disconnects sockets; it does not resign games.
    # TODO: this can't end game if logout came from an ongoing game
    # because its ws was already closed and removed from game_sockets
    if not user.enabled:
        for gameId in user.game_sockets:
            if gameId in app_state.games:
                game = app_state.games[gameId]
                if game.status <= STARTED:
                    game_end_response = await game.game_ended(user, "abandon")
                    await round_broadcast(game, game_end_response, full=True)

    await revoke_user_sessions(user)

    # Revocation is user-wide, matching the existing logout semantics. Notify
    # and then forcibly close every browser-authenticated websocket so a client
    # that ignores the logout message cannot keep using an already-open channel.
    sockets = set(user.authenticated_sockets)
    sockets.update(user.lobby_sockets)
    for ws_set in user.tournament_sockets.values():
        sockets.update(ws for ws in ws_set if ws is not None)
    for ws_set in user.simul_sockets.values():
        sockets.update(ws_set)
    for ws_set in user.study_sockets.values():
        sockets.update(ws_set)
    for ws_set in user.game_sockets.values():
        sockets.update(ws_set)

    await ws_send_json_many(sockets, logout_response)
    if sockets:
        await asyncio.gather(*(ws.close() for ws in sockets), return_exceptions=True)

    # SSE subscriptions are authenticated only when opened. Shut them down too
    # so they cannot outlive the session generation that authorized them.
    for queue in tuple(user.notify_channels | user.inbox_channels | user.challenge_channels):
        queue.shutdown(immediate=True)

    if request is not None:
        session.invalidate()

    return web.HTTPFound("/")


async def select_username(request: web.Request) -> web.StreamResponse:
    """Handle username selection for new OAuth users"""
    session = await aiohttp_session.get_session(request)

    # Check if user is in the middle of OAuth flow
    if "oauth_id" not in session:
        return web.HTTPFound("/")

    # This will be handled by the client-side view
    return web.HTTPFound("/")


async def check_username_availability(request: web.Request) -> web.StreamResponse:
    """API endpoint to check if username is available"""
    data = await read_json_data(request)
    if data is None:
        return web.Response(status=204)
    username = data.get("username", "").strip()

    if not username:
        return json_response({"available": False, "error": "Username cannot be empty"})

    if len(username) < 3:
        return json_response(
            {"available": False, "error": "Username must be at least 3 characters"}
        )

    if len(username) > 20:
        return json_response(
            {"available": False, "error": "Username must be at most 20 characters"}
        )

    # Check for invalid characters
    import re

    if not re.match(r"^[a-zA-Z0-9_-]+$", username):
        return json_response(
            {"available": False, "error": "Username can only contain letters, numbers, _ and -"}
        )

    if reserved(username):
        return json_response({"available": False, "error": "Username is reserved"})

    app_state = get_app_state(request.app)
    if await username_exists(app_state, username):
        return json_response({"available": False, "error": "Username is already taken"})

    return json_response({"available": True})


async def confirm_username(request: web.Request) -> web.StreamResponse:
    """Confirm username selection and complete OAuth registration"""
    session = await aiohttp_session.get_session(request)

    # Check if user is in the middle of OAuth flow
    if "oauth_id" not in session:
        return json_response({"error": "Invalid session"}, status=400)

    data = await read_json_data(request)
    if data is None:
        return web.Response(status=204)
    username = data.get("username", "").strip()

    # Validate username again by calling the validation logic directly
    if not username:
        return json_response({"error": "Username cannot be empty"}, status=400)

    if len(username) < 3:
        return json_response({"error": "Username must be at least 3 characters"}, status=400)

    if len(username) > 20:
        return json_response({"error": "Username must be at most 20 characters"}, status=400)

    # Check for invalid characters
    import re

    if not re.match(r"^[a-zA-Z0-9_-]+$", username):
        return json_response(
            {"error": "Username can only contain letters, numbers, _ and -"}, status=400
        )

    if reserved(username):
        return json_response({"error": "Username is reserved"}, status=400)

    app_state = get_app_state(request.app)
    username_lower = normalized_username(username)

    if await username_exists(app_state, username):
        return json_response({"error": "Username is already taken"}, status=400)

    # Create new user with OAuth information
    oauth_id: str = session["oauth_id"]
    oauth_provider: str = session["oauth_provider"]
    title: str = session.get("oauth_title", "")
    signals = collect_client_signals(request)

    blocked, match_reason = await is_signup_blocked_by_signals(app_state.db, signals)
    if blocked:
        auto_close_at = datetime.now(UTC)
        log.warning(
            "Auto-closing new account %s due to ban-evasion signal match (%s)",
            username,
            match_reason,
        )
        try:
            now = datetime.now(UTC)
            await app_state.db.user.insert_one(
                {
                    "_id": username,
                    USERNAME_LOWER_FIELD: username_lower,
                    "title": title,
                    "oauth_id": oauth_id,
                    "oauth_provider": oauth_provider,
                    "createdAt": now,
                    "perfs": {},
                    "pperfs": {},
                    "count": dict(DEFAULT_USER_COUNT),
                    "enabled": False,
                    "shadowban": False,
                    "security": {
                        "lastAutoCloseAt": auto_close_at,
                        "lastAutoCloseReason": match_reason,
                        "lastAutoCloseSource": "signup",
                    },
                }
            )
            await remember_user_signals(app_state.db, username, signals)
        except Exception as e:
            log.error("Failed to auto-close user %s: %s", username, e)

        session.pop("oauth_id", None)
        session.pop("oauth_provider", None)
        session.pop("oauth_username", None)
        session.pop("oauth_title", None)
        return json_response(
            {
                "error": (
                    "Account closed for suspected ban evasion. "
                    "If this is a mistake, contact site admins."
                )
            },
            status=403,
        )

    try:
        now = datetime.now(UTC)
        result = await app_state.db.user.insert_one(
            {
                "_id": username,
                USERNAME_LOWER_FIELD: username_lower,
                "title": title,
                "oauth_id": oauth_id,
                "oauth_provider": oauth_provider,
                "createdAt": now,
                "perfs": {},
                "pperfs": {},
                "count": dict(DEFAULT_USER_COUNT),
                "enabled": True,
                "shadowban": False,
            }
        )
        log.info("db insert user result %r", result.inserted_id)

        # Set session username and clean up OAuth data
        authenticate_session(session, username, 0)
        request[REQUEST_NEW_SESSION_KEY] = True
        session.pop("oauth_id", None)
        session.pop("oauth_provider", None)
        session.pop("oauth_username", None)
        session.pop("oauth_title", None)
        await remember_user_signals(app_state.db, username, signals)

        log.info("Created new user %s via OAuth signup", username)
        return json_response({"success": True})

    except DuplicateKeyError:
        log.info("Duplicate username rejected during OAuth signup: %s", username)
        return json_response({"error": "Username is already taken"}, status=400)

    except Exception as e:
        log.error("Failed to create user %s: %s", username, e)
        return json_response({"error": "Failed to create user"}, status=500)


def get_code_challenge(code_verifier: str) -> str:
    hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
    encoded = base64.urlsafe_b64encode(hashed)
    return encoded.decode("ascii")[:-1]
