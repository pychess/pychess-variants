from urllib.parse import quote, urlsplit

import aiohttp_jinja2
from aiohttp import web
from const import DASH, IMPORTED, RATED, SYSTEM_USER, T_FINISHED, TROPHIES
from custom_trophy_owners import CUSTOM_TROPHY_OWNERS
from glicko2.glicko2 import PROVISIONAL_PHI
from profile_counts import HISTORY_PAGE_SIZE, aggregate_results, completed_tournament_results
from pychess_global_app_state_utils import get_app_state
from settings import ADMINS, SIMULING
from study.storage import count_studies_for_owner_view
from team import profile_teams_for_user
from typedefs import REQUEST_PROFILE_RESTRICTED_KEY
from typing_defs import ViewContext
from ublog import display_date, image_src, post_url, summary_from_markdown
from variants import VARIANT_ICONS, VARIANTS

from views import get_user_context


def _thread_id(user1: str, user2: str) -> str:
    first, second = sorted((user1, user2), key=lambda x: (x.lower(), x))
    return f"{first}:{second}"


def _has_internal_referer(request: web.Request) -> bool:
    referer = request.headers.get("Referer")
    if not referer:
        return False

    try:
        parsed = urlsplit(referer)
    except ValueError:
        return False

    return (
        parsed.scheme in {"http", "https"} and parsed.netloc.casefold() == request.host.casefold()
    )


@aiohttp_jinja2.template("profile.html")
async def profile(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)

    profileId = request.match_info["profileId"]
    # Variant may come from the URL path (/@/<profile>/perf/<key>) or from the
    # query string (/@/<profile>/rated?variant=<key>), so the profile page tabs
    # and the variant filter can be combined instead of resetting each other.
    variant = request.match_info.get("variant") or request.rel_url.query.get("variant")
    if (variant is not None) and (variant not in VARIANTS):
        raise web.HTTPNotFound()

    app_state = get_app_state(request.app)

    rated: int | None = None

    if variant is not None:
        context["variant"] = variant

    context["icons"] = VARIANT_ICONS
    profile_restricted = user.anon and not _has_internal_referer(request)
    request[REQUEST_PROFILE_RESTRICTED_KEY] = profile_restricted
    context["profile_restricted"] = profile_restricted

    if user.anon and DASH in profileId:
        return context

    profile_user = await app_state.public_users.get_profile(
        profileId,
        cache=not profile_restricted,
        include_blocked=not profile_restricted,
    )
    if profile_user is None or not profile_user.enabled:
        raise web.HTTPNotFound()

    if request.path[-7:] == "/import":
        rated = IMPORTED
    elif request.path[-6:] == "/rated":
        rated = RATED
    elif request.path[-8:] == "/playing":
        rated = -2
    elif request.path[-3:] == "/me":
        rated = -1

    profile_system = profileId == SYSTEM_USER
    context["profile_system"] = profile_system

    if profile_restricted:
        # A direct anonymous profile request is likely to be enumeration
        # traffic. Render public identity/rating data, but avoid relationship
        # and inbox work that cannot produce actionable controls for an anon.
        context["can_block"] = False
        context["can_follow"] = False
        context["is_following"] = False
        context["can_message"] = False
        context["can_challenge"] = False
        context["can_export_games"] = False
    else:
        if profile_system:
            context["can_block"] = False
            context["can_follow"] = (not user.anon) and profileId != user.username
            context["is_following"] = profileId in user.following
            context["can_message"] = False
            context["can_challenge"] = False
            context["can_export_games"] = False
        else:
            follow_allowed = (profileId not in user.blocked) and (
                user.username not in profile_user.blocked
            )
            context["can_block"] = profileId not in user.blocked
            context["can_follow"] = follow_allowed
            context["is_following"] = profileId in user.following
            can_message = (
                (profileId not in user.blocked)
                and (user.username not in profile_user.blocked)
                and ((not profile_user.pm_friends_only) or (profileId in user.following))
            )
            if (
                (not can_message)
                and profile_user.pm_friends_only
                and follow_allowed
                and (app_state.db is not None)
            ):
                existing = await app_state.db.inbox_thread.find_one(
                    {"_id": _thread_id(user.username, profileId), "deletedBy": {"$ne": profileId}},
                    projection={"_id": 1},
                )
                can_message = existing is not None
            context["can_message"] = can_message
            context["can_challenge"] = (profileId not in user.blocked) and (
                user.username not in profile_user.blocked
            )
            context["can_export_games"] = (
                (not user.anon)
                and (not profile_user.bot)
                and (profileId == user.username or user.username in ADMINS)
            )

    allowed_variants = context["category_variant_set"]

    _id = "%s|%s" % (profileId, profile_user.title)
    context["trophies"] = [
        (v, "top10")
        for v in app_state.highscore
        if _id in app_state.highscore[v].keys()[:10]
        and (allowed_variants is None or v in allowed_variants)
    ]
    for i, (v, kind) in enumerate(context["trophies"]):
        if app_state.highscore[v].peekitem(0)[0] == _id:
            context["trophies"][i] = (v, "top1")
    context["trophies"] = sorted(context["trophies"], key=lambda x: x[1])

    if not profile_user.bot:
        shield_owners = app_state.shield_owners
        context["trophies"] += [
            (v, "shield")
            for v in shield_owners
            if shield_owners[v] == profileId and (allowed_variants is None or v in allowed_variants)
        ]

    if profileId in CUSTOM_TROPHY_OWNERS:
        trophies = CUSTOM_TROPHY_OWNERS[profileId]
        for v, kind in trophies:
            if v in VARIANTS and (allowed_variants is None or v in allowed_variants):
                context["trophies"].append((v, kind))

    context["title"] = "Profile • " + profileId
    context["icons"] = VARIANT_ICONS
    context["cup"] = TROPHIES

    if variant is not None:
        context["variant"] = variant

    perfs = [(key, perf) for key, perf in profile_user.perfs.items() if perf["nb"] > 0]
    if context["game_category"] != "all":
        perfs = [(k, v) for k, v in perfs if k in allowed_variants]

    context["ratings"] = {
        k: (
            "%s%s"
            % (
                int(round(v["gl"]["r"], 0)),
                "?" if v["gl"]["d"] > PROVISIONAL_PHI else "",
            ),
            v["nb"],
        )
        for (k, v) in sorted(
            perfs,
            key=lambda x: x[1]["nb"],
            reverse=True,
        )
    }
    context["profile_title"] = profile_user.title
    context["profile_tournament_points"] = profile_user.tournament_points
    context["profile_forum_posts"] = profile_user.forum_posts
    context["profile_variant_count"] = profile_user.variant_count
    context["profile_patron"] = profile_user.patron
    live_profile_user = app_state.users.data.get(profileId)
    context["profile_online"] = bool(live_profile_user is not None and live_profile_user.online)
    context["rated"] = rated

    context["view"] = "profile"
    context["view_css"] = "profile.css"
    context["profile"] = profileId
    context["lichess_id"] = (
        profile_user.oauth_id if profile_user.oauth_provider == "lichess" else ""
    )
    context["lishogi_id"] = (
        profile_user.oauth_id if profile_user.oauth_provider == "lishogi" else ""
    )
    context["profile_teams"] = []
    context["profile_simul_count"] = 0
    context["profile_study_count"] = 0
    context["ublog_posts"] = []
    context["ublog_post_count"] = 0
    if app_state.db is not None and not profile_restricted:
        if SIMULING and not user.anon and not profile_user.bot:
            context["profile_simul_count"] = await app_state.db.simul.count_documents(
                {"createdBy": profile_user.username, "status": T_FINISHED}
            )
        if not user.anon:
            context["profile_teams"] = await profile_teams_for_user(app_state, profileId)
        if not profile_user.bot:
            viewer = None if user.anon else user.username
            context["profile_study_count"] = await count_studies_for_owner_view(
                app_state, profile_user.username, viewer
            )
        context["ublog_post_count"] = await app_state.db.ublog_post.count_documents(
            {"author": profileId, "live": True}
        )
        posts = await (
            app_state.db.ublog_post.find({"author": profileId, "live": True})
            .sort([("sticky", -1), ("publishedAt", -1), ("createdAt", -1)])
            .limit(3)
            .to_list(3)
        )
        titles = await app_state.public_users.get_titles([profileId])
        author_title = titles.get(profileId, "")
        ublog_posts: list[dict[str, str]] = []
        for post in posts:
            summary = summary_from_markdown(str(post.get("markdown") or ""))
            intro = str(post.get("intro") or post.get("subtitle") or summary)
            ublog_posts.append(
                {
                    "_id": post["_id"],
                    "title": str(post.get("title") or ""),
                    "intro": intro,
                    "subtitle": intro,
                    "summary": summary,
                    "date": display_date(post),
                    "image": str(post.get("image") or ""),
                    "image_src": image_src(post),
                    "imageAlt": str(post.get("imageAlt") or ""),
                    "url": post_url(post),
                    "author": profileId,
                    "author_title": author_title,
                }
            )
        context["ublog_posts"] = ublog_posts

    return context


@aiohttp_jinja2.template("profile_tournaments.html")
async def tournament_history(request: web.Request) -> ViewContext:
    _user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    profile_user = await app_state.public_users.get_profile(profile_id)
    if profile_user is None or not profile_user.enabled:
        raise web.HTTPNotFound()

    try:
        page = max(1, int(request.query.get("page", "1")))
    except ValueError:
        page = 1
    entries = []
    if app_state.db is not None:
        entries = await aggregate_results(
            app_state.db,
            completed_tournament_results(profile_user.username)
            + [
                {"$sort": {"tournament.startsAt": -1, "tid": -1}},
                {"$skip": (page - 1) * HISTORY_PAGE_SIZE},
                {"$limit": HISTORY_PAGE_SIZE + 1},
                {
                    "$project": {
                        "_id": 0,
                        "id": "$tid",
                        "name": "$tournament.name",
                        "date": "$tournament.startsAt",
                        "points": 1,
                    }
                },
            ],
        )
    base_url = f"/@/{quote(profile_user.username, safe='')}/tournaments"
    context["title"] = f"{profile_user.username} • Tournament points"
    context["view"] = "tournaments"
    context["view_css"] = "tournaments.css"
    context["profile"] = profile_user.username
    context["profile_tournament_points"] = profile_user.tournament_points
    context["profile_tournament_entries"] = entries[:HISTORY_PAGE_SIZE]
    context["profile_tournament_prev"] = f"{base_url}?page={page - 1}" if page > 1 else ""
    context["profile_tournament_next"] = (
        f"{base_url}?page={page + 1}" if len(entries) > HISTORY_PAGE_SIZE else ""
    )
    return context
