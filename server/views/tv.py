import aiohttp_jinja2
from aiohttp import web
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext
from utils import load_game, tv_game, tv_game_user

from views import add_game_context, get_user_context


@aiohttp_jinja2.template("index.html")
async def tv(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)

    app_state = get_app_state(request.app)

    profileId = request.match_info.get("profileId")

    if profileId is not None:
        gameId = await tv_game_user(app_state.db, app_state.users, profileId)
    else:
        gameId = await tv_game(app_state)

    ply = request.rel_url.query.get("ply")

    if gameId is None:
        raise web.HTTPNotFound()

    game = await load_game(app_state, gameId, cache_finished=False)
    if game is None:
        raise web.HTTPNotFound()

    add_game_context(game, ply, user, context)

    context["ct"] = json_dumps(game.crosstable)

    context["view"] = "tv"
    context["view_css"] = "round.css"
    context["gameId"] = gameId
    context["profile"] = profileId

    return context
