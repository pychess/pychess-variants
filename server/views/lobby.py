import json

import aiohttp_jinja2
import aiohttp_session
from aiohttp import web
from catalogued.variants import catalogued_variant_client_doc_for_name
from json_utils import json_dumps
from puzzle import get_daily_puzzle
from pychess_global_app_state_utils import get_app_state
from timeline import TIMELINE_DISPLAY_MAX
from tournament_director import is_tournament_director
from typing_defs import ViewContext
from utils import get_blogs
from variants import ALL_VARIANTS, is_catalogued_variant

from views import add_corr_games_context, get_user_context


@aiohttp_jinja2.template("index.html")
async def lobby(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)
    context["prefetch_ffish"] = True

    app_state = get_app_state(request.app)

    # If OAuth data exists in session after oauth login, we need a new username
    session = await aiohttp_session.get_session(request)
    context["oauth_username_selection"] = (
        {
            "oauth_id": session.get("oauth_id"),
            "oauth_provider": session.get("oauth_provider"),
            "oauth_username": session.get("oauth_username"),
        }
        if session.get("oauth_id")
        else None
    )

    # Seek from Editor with custom start position
    variant = request.match_info.get("variant")
    if (variant is not None) and (variant not in ALL_VARIANTS):
        variant = "chess"
    if variant is not None:
        context["variant"] = variant

    fen = request.rel_url.query.get("fen")
    selected_variant = request.rel_url.query.get("variant")
    if selected_variant is not None and selected_variant in ALL_VARIANTS:
        catalogued_doc = None
        if is_catalogued_variant(selected_variant):
            catalogued_doc = catalogued_variant_client_doc_for_name(
                app_state, selected_variant, user.username if not user.anon else None
            )
            if catalogued_doc is not None:
                catalogued_variants = json.loads(str(context.get("catalogued_variants") or "[]"))
                if not any(item.get("name") == selected_variant for item in catalogued_variants):
                    catalogued_variants.append(catalogued_doc)
                    context["catalogued_variants"] = json_dumps(catalogued_variants)
        if catalogued_doc is not None or not is_catalogued_variant(selected_variant):
            context["variant"] = selected_variant

    if fen is not None:
        context["variant"] = variant
        context["fen"] = fen.replace(".", "+").replace("_", " ")
        context["view_css"] = "lobby.css"

    # Challenge user from user's profile or FSF from Editor
    profileId = request.match_info.get("profileId")

    # Play menu (Create a game)
    if request.rel_url.query.get("any") is not None:
        profileId = "any#"

    # Direct AI entry point used by custom/catalogued variant pages.  Keep it
    # query based so ?variant=... can preload unlisted catalogued variants too.
    if request.rel_url.query.get("ai") is not None:
        profileId = "Fairy-Stockfish"

    opens_lobby_dialog = profileId is not None and (
        "/challenge" in request.path
        or "/play" in request.path
        or request.rel_url.query.get("any") is not None
        or request.rel_url.query.get("ai") is not None
    )
    if opens_lobby_dialog:
        context["profile"] = profileId
        profile_user = (
            app_state.users[profileId]
            if isinstance(profileId, str) and profileId in app_state.users
            else None
        )
        context["profile_title"] = profile_user.title if profile_user is not None else ""
        context["bot_supported_variants"] = json_dumps(
            None
            if profileId in ("Fairy-Stockfish", "Random-Mover")
            else sorted(profile_user.bot_supported_variants or ())
            if profile_user is not None and profile_user.bot
            else None
        )
        context["view_css"] = "lobby.css"
        if user.anon and context["profile_title"] != "BOT" and profileId != "any#":
            raise web.HTTPNotFound()

    context["title"] = "PyChess • Free Online Chess Variants"
    context["tournamentdirector"] = is_tournament_director(user, app_state)

    puzzle = await get_daily_puzzle(request)
    context["puzzle"] = json_dumps(puzzle)

    await add_corr_games_context(app_state, user, context)

    blogs = await get_blogs(request, limit=3)
    context["blogs"] = json_dumps(blogs)
    context["timeline"] = json_dumps(
        []
        if user.anon
        else await app_state.timeline.entries_for(user.username, limit=TIMELINE_DISPLAY_MAX)
    )
    return context
