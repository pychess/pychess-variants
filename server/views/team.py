from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import aiohttp_jinja2
from admin_api import record_team_action
from aiohttp import web
from forum.access import can_read_forum_categ, team_forum_categ_id
from forum.storage import ensure_team_forum
from pagination import page_href, page_number
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from settings import ADMINS
from team import (
    PERMISSION_ADMIN,
    PERMISSION_KICK,
    PERMISSION_PUBLIC,
    PERMISSION_REQUESTS,
    PERMISSION_SETTINGS,
    PERMISSION_TOURNAMENTS,
    PERMISSION_UPDATES,
    TEAM_FORUM_ACCESS_NONE,
    TEAM_FORUM_ACCESS_OPTIONS,
    TEAM_MAX_ADMINS,
    TEAM_MAX_CREATED_PER_7_DAYS,
    TEAM_MAX_JOINED,
    TEAM_MAX_LEADERS,
    TEAM_PERMISSION_DEFINITIONS,
    TEAM_REQUEST_DEFAULT_MESSAGE,
    TEAM_REQUEST_MAX_LENGTH,
    TEAM_UPDATE_MAX_LENGTH,
    TEAM_UPDATE_MAX_PER_7_DAYS,
    add_team_leader,
    cancel_join_request,
    close_team,
    create_team,
    get_team,
    get_team_any,
    get_team_member,
    has_team_permission,
    join_or_request_team,
    kick_team_member,
    latest_team_update,
    process_join_request,
    quit_team,
    reopen_team,
    send_team_update,
    set_team_update_subscription,
    team_update_quota_remaining,
    team_updates_by_team,
    team_updates_for_member,
    team_updates_for_user,
    teams_for_user,
    update_team,
    update_team_leader_permissions,
)
from typing_defs import ViewContext
from variants import C2V, CATALOGUED_VARIANT_ICON, get_server_variant

from views import get_user_context

TEAM_SHOW_MEMBER_LIMIT = 10
TEAM_MEMBERS_PAGE_SIZE = 50
TEAM_REQUESTS_PAGE_SIZE = 50


def _require_regular_user(user: Any) -> None:
    if user.anon:
        raise web.HTTPFound("/login")
    if user.bot:
        raise web.HTTPForbidden(text="BOT accounts cannot use teams.")


def _is_site_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


def _team_context(context: ViewContext) -> None:
    context["view_css"] = "team.css"
    context["title"] = "Teams • PyChess"


async def _request_manager_team_ids(app_state: Any, username: str) -> list[str]:
    if app_state.db is None:
        return []
    cursor = app_state.db.team_member.find({"user": username, "permissions": PERMISSION_REQUESTS})
    return [str(member["team"]) async for member in cursor]


def _team_request_redirect(value: object, team_id: str) -> str:
    fallback = f"/team/{team_id}"
    redirect = str(value or "")
    declined = f"{fallback}/declined-requests"
    if redirect == "/team/requests" or redirect == declined or redirect.startswith(f"{declined}?"):
        return redirect
    return fallback


def _declined_requests_href(team_id: str, page: int, search: str) -> str:
    query: dict[str, str] = {"page": str(page)}
    if search:
        query["search"] = search
    return f"/team/{team_id}/declined-requests?{urlencode(query)}"


@aiohttp_jinja2.template("teams.html")
async def teams(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    _team_context(context)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Teams require database access.")
    db = app_state.db

    cursor = (
        db.team.find({"enabled": True}).sort([("memberCount", -1), ("createdAt", -1)]).limit(60)
    )
    context["teams"] = await cursor.to_list(length=60)
    context["my_team_ids"] = set()
    if not user.anon and not user.bot:
        mine = await teams_for_user(app_state, user.username)
        context["my_team_ids"] = {str(team["_id"]) for team in mine}
    return context


@aiohttp_jinja2.template("teams.html")
async def my_teams(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    _team_context(context)
    mine = await teams_for_user(app_state, user.username)
    context["teams"] = mine
    context["my_team_ids"] = {str(team["_id"]) for team in mine}
    context["mine_only"] = True
    return context


@aiohttp_jinja2.template("team-requests.html")
async def team_requests(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    _team_context(context)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Teams require database access.")

    team_ids = await _request_manager_team_ids(app_state, user.username)
    requests: list[dict[str, Any]] = []
    teams_by_id: dict[str, dict[str, Any]] = {}
    page = page_number(request)
    total = 0
    if team_ids:
        query = {"team": {"$in": team_ids}, "declined": False}
        total = await app_state.db.team_request.count_documents(query)
        page = min(page, max(1, (total + TEAM_REQUESTS_PAGE_SIZE - 1) // TEAM_REQUESTS_PAGE_SIZE))
        requests = await (
            app_state.db.team_request.find(query)
            .sort([("createdAt", 1), ("_id", 1)])
            .skip((page - 1) * TEAM_REQUESTS_PAGE_SIZE)
            .limit(TEAM_REQUESTS_PAGE_SIZE)
            .to_list(length=TEAM_REQUESTS_PAGE_SIZE)
        )
        visible_team_ids = list({str(item["team"]) for item in requests})
        teams = (
            await app_state.db.team.find(
                {"_id": {"$in": visible_team_ids}, "enabled": True}
            ).to_list(length=len(visible_team_ids))
            if visible_team_ids
            else []
        )
        teams_by_id = {str(team["_id"]): team for team in teams}

    context.update(
        {
            "team_requests": requests,
            "team_requests_total": total,
            "team_request_teams": teams_by_id,
            "prev_page_href": page_href(request, page - 1) if page > 1 else None,
            "next_page_href": page_href(request, page + 1)
            if page * TEAM_REQUESTS_PAGE_SIZE < total
            else None,
            "title": f"{total} join requests • PyChess",
        }
    )
    return context


@aiohttp_jinja2.template("team-new.html")
async def team_new(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    _team_context(context)
    context["team_max_joined"] = TEAM_MAX_JOINED
    context["team_max_created_per_7_days"] = TEAM_MAX_CREATED_PER_7_DAYS
    context["team_forum_access_options"] = TEAM_FORUM_ACCESS_OPTIONS
    context["team_forum_access_none"] = TEAM_FORUM_ACCESS_NONE
    return context


async def team_create(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    team = await create_team(get_app_state(request.app), user.username, data)
    raise web.HTTPFound(f"/team/{team['_id']}")


@aiohttp_jinja2.template("team-show.html")
async def team_show(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    _team_context(context)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Teams require database access.")
    db = app_state.db
    team_id = request.match_info["teamId"]
    team = await get_team_any(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    team_closed = not bool(team.get("enabled", True))
    site_admin = bool(context.get("admin"))
    can_view_closed_details = not team_closed or site_admin

    member = (
        None if user.anon or user.bot else await get_team_member(app_state, team_id, user.username)
    )
    members: list[dict[str, Any]] = []
    leaders: list[dict[str, Any]] = []
    if can_view_closed_details:
        members = (
            await db.team_member.find({"team": team_id})
            .sort("joinedAt", -1)
            .limit(TEAM_SHOW_MEMBER_LIMIT)
            .to_list(length=TEAM_SHOW_MEMBER_LIMIT)
        )
        leaders = (
            await db.team_member.find({"team": team_id, "permissions": PERMISSION_PUBLIC})
            .sort("joinedAt", 1)
            .limit(TEAM_MAX_LEADERS)
            .to_list(length=TEAM_MAX_LEADERS)
        )
    requests: list[dict[str, Any]] = []
    can_manage_requests = False
    can_kick = False
    can_edit = False
    can_create_tournament = False
    can_manage_leaders = False
    can_send_update = False
    if member is not None and not team_closed:
        permissions = set(member.get("permissions") or ())
        can_manage_requests = PERMISSION_REQUESTS in permissions
        can_kick = PERMISSION_KICK in permissions
        can_edit = PERMISSION_SETTINGS in permissions
        can_create_tournament = PERMISSION_TOURNAMENTS in permissions
        can_manage_leaders = PERMISSION_ADMIN in permissions
        can_send_update = PERMISSION_UPDATES in permissions
        if can_manage_requests:
            requests = (
                await db.team_request.find({"team": team_id, "declined": False})
                .sort("createdAt", 1)
                .limit(50)
                .to_list(length=50)
            )

    pending_request = None
    declined_request = None
    if not team_closed and not user.anon and not user.bot and member is None:
        my_request = await db.team_request.find_one({"_id": f"{user.username}@{team_id}"})
        if my_request is not None:
            if my_request.get("declined"):
                declined_request = my_request
            else:
                pending_request = my_request

    latest_update = (
        await latest_team_update(app_state, team_id)
        if member is not None and not team_closed
        else None
    )

    forum_categ = await ensure_team_forum(app_state, team) if not team_closed else None
    forum_categ_id = team_forum_categ_id(team_id)
    viewer_username = None if user.anon else user.username
    can_see_forum = (
        not team_closed
        and forum_categ is not None
        and await can_read_forum_categ(app_state, forum_categ, viewer_username)
    )
    forum_topics: list[dict[str, Any]] = []
    if can_see_forum:
        forum_topics = await (
            db.forum_topic.find({"categId": forum_categ_id})
            .sort([("sticky", -1), ("updatedAt", -1)])
            .limit(5)
            .to_list(length=5)
        )

    team_tournaments: list[dict[str, Any]] = []
    if can_view_closed_details:
        team_tournaments = (
            await db.tournament.find({"teamId": team_id})
            .sort("startsAt", -1)
            .limit(20)
            .to_list(length=20)
        )
        for tournament in team_tournaments:
            variant_code = str(tournament.get("v") or "")
            variant_name = C2V.get(variant_code, variant_code)
            try:
                tournament["variantIcon"] = get_server_variant(
                    variant_name, bool(tournament.get("z"))
                ).icon
            except KeyError:
                # Keep historical tournaments readable if a catalogued variant
                # has since been archived or removed from the runtime catalogue.
                tournament["variantIcon"] = CATALOGUED_VARIANT_ICON

    context.update(
        {
            "team": team,
            "team_closed": team_closed,
            "team_is_site_admin": site_admin,
            "team_can_close": not team_closed
            and not user.anon
            and (site_admin or user.username == str(team.get("createdBy") or "")),
            "team_can_reopen": team_closed and site_admin and team.get("creatorErasedAt") is None,
            "team_member": member,
            "team_members": members,
            "team_leaders": leaders,
            "team_requests": requests,
            "team_pending_request": pending_request,
            "team_declined_request": declined_request,
            "team_can_manage_requests": can_manage_requests,
            "team_can_kick": can_kick,
            "team_can_edit": can_edit,
            "team_can_create_tournament": can_create_tournament,
            "team_can_manage_leaders": can_manage_leaders,
            "team_can_send_update": can_send_update,
            "team_latest_update": latest_update,
            "team_can_see_forum": can_see_forum,
            "team_forum_categ_id": forum_categ_id,
            "team_forum_topics": forum_topics,
            "team_public_permission": PERMISSION_PUBLIC,
            "team_tournaments": team_tournaments,
            "title": f"{team['name']} • PyChess",
        }
    )
    return context


@aiohttp_jinja2.template("team-members.html")
async def team_members(request: web.Request) -> ViewContext:
    _, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    _team_context(context)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Teams require database access.")

    team_id = request.match_info["teamId"]
    team = (
        await get_team_any(app_state, team_id)
        if context.get("admin")
        else await get_team(app_state, team_id)
    )
    if team is None:
        raise web.HTTPNotFound()

    try:
        page = max(1, int(request.rel_url.query.get("page", "1")))
    except ValueError:
        page = 1

    total = await app_state.db.team_member.count_documents({"team": team_id})
    skip = (page - 1) * TEAM_MEMBERS_PAGE_SIZE
    members = (
        await app_state.db.team_member.find({"team": team_id})
        .sort("joinedAt", -1)
        .skip(skip)
        .limit(TEAM_MEMBERS_PAGE_SIZE)
        .to_list(length=TEAM_MEMBERS_PAGE_SIZE)
    )

    prev_href = None if page <= 1 else f"/team/{team_id}/members?page={page - 1}"
    next_href = f"/team/{team_id}/members?page={page + 1}" if skip + len(members) < total else None
    context.update(
        {
            "team": team,
            "team_members": members,
            "team_members_total": total,
            "team_members_page": page,
            "team_members_prev_href": prev_href,
            "team_members_next_href": next_href,
            "title": f"{team['name']} • Members • PyChess",
        }
    )
    return context


@aiohttp_jinja2.template("team-declined-requests.html")
async def team_declined_requests(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    _team_context(context)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Teams require database access.")

    team_id = request.match_info["teamId"]
    team = await get_team(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    if not await has_team_permission(app_state, team_id, user.username, PERMISSION_REQUESTS):
        raise web.HTTPForbidden(text="You cannot manage join requests for this team.")

    try:
        page = max(1, int(request.rel_url.query.get("page", "1")))
    except ValueError:
        page = 1
    search = request.rel_url.query.get("search", "").strip()
    query: dict[str, Any] = {"team": team_id, "declined": True}
    if search:
        query["user"] = search

    total = await app_state.db.team_request.count_documents(query)
    skip = (page - 1) * TEAM_REQUESTS_PAGE_SIZE
    requests = (
        await app_state.db.team_request.find(query)
        .sort([("processedAt", -1), ("createdAt", -1)])
        .skip(skip)
        .limit(TEAM_REQUESTS_PAGE_SIZE)
        .to_list(length=TEAM_REQUESTS_PAGE_SIZE)
    )
    prev_href = None if page <= 1 else _declined_requests_href(team_id, page - 1, search)
    next_href = (
        _declined_requests_href(team_id, page + 1, search) if skip + len(requests) < total else None
    )
    current_href = _declined_requests_href(team_id, page, search)
    context.update(
        {
            "team": team,
            "team_declined_requests": requests,
            "team_declined_requests_total": total,
            "team_declined_requests_page": page,
            "team_declined_requests_search": search,
            "team_declined_requests_prev_href": prev_href,
            "team_declined_requests_next_href": next_href,
            "team_declined_requests_current_href": current_href,
            "title": f"{team['name']} • Declined requests • PyChess",
        }
    )
    return context


@aiohttp_jinja2.template("team-join.html")
async def team_join_form(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    _team_context(context)
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Teams require database access.")

    team_id = request.match_info["teamId"]
    team = await get_team(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    if await get_team_member(app_state, team_id, user.username) is not None:
        raise web.HTTPFound(f"/team/{team_id}")

    existing_request = await app_state.db.team_request.find_one(
        {"_id": f"{user.username}@{team_id}"}
    )
    if existing_request is not None:
        raise web.HTTPFound(f"/team/{team_id}")

    if not team.get("requestRequired") and not team.get("entryCodeHash"):
        raise web.HTTPFound(f"/team/{team_id}")

    context.update(
        {
            "team": team,
            "team_request_default_message": TEAM_REQUEST_DEFAULT_MESSAGE,
            "team_request_max_length": TEAM_REQUEST_MAX_LENGTH,
            "title": f"Join {team['name']} • PyChess",
        }
    )
    return context


async def team_join(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    team_id = request.match_info["teamId"]
    team = await get_team(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()

    needs_request_form = (
        bool(team.get("requestRequired")) and not str(data.get("message") or "").strip()
    )
    needs_entry_code = bool(team.get("entryCodeHash")) and not str(data.get("entryCode") or "")
    if needs_request_form or needs_entry_code:
        raise web.HTTPFound(f"/team/{team_id}/join")

    await join_or_request_team(app_state, team, user.username, data)
    raise web.HTTPFound(f"/team/{team_id}")


async def team_cancel_request(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    team_id = request.match_info["teamId"]
    await cancel_join_request(get_app_state(request.app), team_id, user.username)
    raise web.HTTPFound(f"/team/{team_id}")


async def team_quit(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    team_id = request.match_info["teamId"]
    await quit_team(get_app_state(request.app), team_id, user.username)
    raise web.HTTPFound(f"/team/{team_id}")


@aiohttp_jinja2.template("team-edit.html")
async def team_edit(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    team_id = request.match_info["teamId"]
    team = await get_team(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    if not await has_team_permission(app_state, team_id, user.username, PERMISSION_SETTINGS):
        raise web.HTTPForbidden(text="You cannot edit this team.")
    _team_context(context)
    context["team"] = team
    context["team_can_close"] = user.username == str(team.get("createdBy") or "") or bool(
        context.get("admin")
    )
    context["team_forum_access_options"] = TEAM_FORUM_ACCESS_OPTIONS
    context["team_forum_access_none"] = TEAM_FORUM_ACCESS_NONE
    context["title"] = f"Edit {team['name']} • PyChess"
    return context


async def team_update(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    team_id = request.match_info["teamId"]
    await update_team(get_app_state(request.app), team_id, user.username, data)
    raise web.HTTPFound(f"/team/{team_id}")


async def team_request_process(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    team_id = request.match_info["teamId"]
    target = request.match_info["username"]
    decision = request.match_info["decision"]
    await process_join_request(get_app_state(request.app), team_id, user.username, target, decision)
    redirect = _team_request_redirect(data.get("redirect"), team_id)
    raise web.HTTPFound(redirect)


async def team_kick(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    team_id = request.match_info["teamId"]
    target = request.match_info["username"]
    await kick_team_member(get_app_state(request.app), team_id, user.username, target)
    raise web.HTTPFound(f"/team/{team_id}")


def _team_lifecycle_redirect(value: object, team_id: str, *, site_admin: bool) -> str:
    redirect = str(value or "")
    if site_admin and (redirect == "/admin/teams" or redirect.startswith("/admin/teams?")):
        return redirect
    return f"/team/{team_id}"


async def team_close(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    app_state = get_app_state(request.app)
    team_id = request.match_info["teamId"]
    site_admin = _is_site_admin_username(user.username)
    reason = str(data.get("reason") or "").strip()[:500]
    await close_team(app_state, team_id, user.username, site_admin=site_admin)
    await record_team_action(app_state, user.username, team_id, "close_team", reason)
    raise web.HTTPFound(
        _team_lifecycle_redirect(data.get("redirect"), team_id, site_admin=site_admin)
    )


async def team_reopen(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    app_state = get_app_state(request.app)
    team_id = request.match_info["teamId"]
    site_admin = _is_site_admin_username(user.username)
    reason = str(data.get("reason") or "").strip()[:500]
    await reopen_team(app_state, team_id, user.username, site_admin=site_admin)
    await record_team_action(app_state, user.username, team_id, "reopen_team", reason)
    raise web.HTTPFound(
        _team_lifecycle_redirect(data.get("redirect"), team_id, site_admin=site_admin)
    )


@aiohttp_jinja2.template("team-updates.html")
async def team_updates(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    _team_context(context)
    context.update(
        {
            "team_update_teams": await team_updates_by_team(app_state, user.username),
            "team_updates": await team_updates_for_user(app_state, user.username),
            "updates_team": None,
            "team_updates_subscribed": True,
            "team_can_send_update": False,
            "title": "Team updates • PyChess",
        }
    )
    return context


@aiohttp_jinja2.template("team-updates.html")
async def team_updates_of(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    team_id = request.match_info["teamId"]
    team = await get_team(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    update_teams = await team_updates_by_team(app_state, user.username)
    updates, subscribed = await team_updates_for_member(app_state, team_id, user.username)
    _team_context(context)
    context.update(
        {
            "team_update_teams": update_teams,
            "team_updates": updates,
            "updates_team": team,
            "team_updates_subscribed": subscribed,
            "team_can_send_update": await has_team_permission(
                app_state, team_id, user.username, PERMISSION_UPDATES
            ),
            "title": f"{team['name']} updates • PyChess",
        }
    )
    return context


@aiohttp_jinja2.template("team-update-new.html")
async def team_update_new(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    team_id = request.match_info["teamId"]
    team = await get_team(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    if not await has_team_permission(app_state, team_id, user.username, PERMISSION_UPDATES):
        raise web.HTTPForbidden(text="You cannot send updates for this team.")
    _team_context(context)
    context.update(
        {
            "team": team,
            "team_update_max_length": TEAM_UPDATE_MAX_LENGTH,
            "team_update_max_per_7_days": TEAM_UPDATE_MAX_PER_7_DAYS,
            "team_update_quota_remaining": await team_update_quota_remaining(app_state, team_id),
            "title": f"New {team['name']} update • PyChess",
        }
    )
    return context


async def team_update_send(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    team_id = request.match_info["teamId"]
    await send_team_update(get_app_state(request.app), team_id, user.username, data.get("message"))
    raise web.HTTPFound(f"/team/{team_id}/updates")


async def team_update_subscribe(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    team_id = request.match_info["teamId"]
    subscribed = str(data.get("subscribe") or "").lower() in {"1", "true", "on"}
    await set_team_update_subscription(
        get_app_state(request.app), team_id, user.username, subscribed
    )
    raise web.HTTPFound(f"/team/{team_id}/updates")


@aiohttp_jinja2.template("team-leaders.html")
async def team_leaders(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    _require_regular_user(user)
    app_state = get_app_state(request.app)
    team_id = request.match_info["teamId"]
    team = await get_team(app_state, team_id)
    if team is None:
        raise web.HTTPNotFound()
    if not await has_team_permission(app_state, team_id, user.username, PERMISSION_ADMIN):
        raise web.HTTPForbidden(text="You cannot manage team leaders.")
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Teams require database access.")

    leaders = (
        await app_state.db.team_member.find({"team": team_id, "permissions.0": {"$exists": True}})
        .sort("joinedAt", 1)
        .limit(TEAM_MAX_LEADERS + 1)
        .to_list(length=TEAM_MAX_LEADERS + 1)
    )
    _team_context(context)
    context.update(
        {
            "team": team,
            "team_leaders": leaders,
            "team_permission_definitions": TEAM_PERMISSION_DEFINITIONS,
            "team_max_admins": TEAM_MAX_ADMINS,
            "team_max_leaders": TEAM_MAX_LEADERS,
            "title": f"{team['name']} leaders • PyChess",
        }
    )
    return context


async def team_leader_add(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    team_id = request.match_info["teamId"]
    await add_team_leader(
        get_app_state(request.app), team_id, user.username, str(data.get("username") or "")
    )
    raise web.HTTPFound(f"/team/{team_id}/leaders")


async def team_permissions_update(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    _require_regular_user(user)
    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()
    getall = getattr(data, "getall", None)
    if not callable(getall):
        raise web.HTTPBadRequest(text="Invalid permissions form.")

    leader_names = [str(value) for value in getall("leader", [])]
    if not leader_names or len(set(leader_names)) != len(leader_names):
        raise web.HTTPBadRequest(text="Invalid leader list.")
    leaders = {
        username: {str(value) for value in getall(f"perm:{username}", [])}
        for username in leader_names
    }
    team_id = request.match_info["teamId"]
    app_state = get_app_state(request.app)
    await update_team_leader_permissions(app_state, team_id, user.username, leaders)
    if await has_team_permission(app_state, team_id, user.username, PERMISSION_ADMIN):
        raise web.HTTPFound(f"/team/{team_id}/leaders")
    raise web.HTTPFound(f"/team/{team_id}")
