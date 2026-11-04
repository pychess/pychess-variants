from typing import TYPE_CHECKING

import aiohttp_jinja2
from aiohttp import web
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from simul.simuls import load_simul
from tournament.tournaments import get_tournament_name, load_tournament
from typing_defs import ViewContext
from utils import load_game, simul_games

from views import (
    add_catalogued_variant_context,
    add_corr_games_context,
    add_game_context,
    get_user_context,
)

if TYPE_CHECKING:
    from game import Game


@aiohttp_jinja2.template("index.html")
async def round_view(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)

    app_state = get_app_state(request.app)

    # play or analyze game
    gameId = request.match_info["gameId"]
    ply = request.rel_url.query.get("ply")

    game = await load_game(app_state, gameId, cache_finished=False)
    if game is None:
        raise web.HTTPNotFound()

    context["view"] = "round"
    context["view_css"] = "round.css"

    add_game_context(game, ply, user, context)
    await add_catalogued_variant_context(app_state, user, context, game.variant, game=game)

    context["ct"] = json_dumps(game.crosstable)

    if game.tournamentId is not None:
        if TYPE_CHECKING:
            assert isinstance(game, Game)
        tournament = await load_tournament(app_state, game.tournamentId)
        tournament_name = await get_tournament_name(request, game.tournamentId)
        context["tournamentid"] = game.tournamentId
        context["tournamentname"] = tournament_name
        context["system"] = tournament.system if tournament is not None else 0
        context["wberserk"] = game.wberserk
        context["bberserk"] = game.bberserk

    if game.corr and user.username in (game.wplayer.username, game.bplayer.username):
        await add_corr_games_context(app_state, user, context)

    simul_id: str | None = None
    if not game.server_variant.two_boards:
        if TYPE_CHECKING:
            assert isinstance(game, Game)
        simul_id = game.simulId
    if simul_id is not None:
        simul = app_state.simuls.get(simul_id)
        if simul is None:
            simul = await load_simul(app_state, simul_id)

        context["simulid"] = simul_id
        context["simulname"] = simul.name if simul is not None else "Simul"

        if (
            simul is not None
            and user.username in (game.wplayer.username, game.bplayer.username)
            and user.username == simul.created_by
        ):
            context["simulhost"] = True
            context["simul_games"] = json_dumps(simul_games(simul.games.values()))
            for simul_game in simul.games.values():
                await add_catalogued_variant_context(
                    app_state, user, context, simul_game.variant, game=simul_game
                )

    return context
