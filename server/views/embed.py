import aiohttp_jinja2
from aiohttp import web
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext
from utils import load_game

from views import add_catalogued_variant_context, add_game_context, get_user_context


@aiohttp_jinja2.template("embed.html")
async def embed(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)

    app_state = get_app_state(request.app)

    gameId = request.match_info["gameId"]
    ply = request.rel_url.query.get("ply")

    game = await load_game(app_state, gameId, cache_finished=False)
    if game is None:
        raise web.HTTPNotFound()

    add_game_context(game, ply, user, context)
    await add_catalogued_variant_context(app_state, user, context, game.variant, game=game)

    context["view_css"] = "embed.css"

    return context
