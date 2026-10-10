import json

import aiohttp_jinja2
from aiohttp import web
from catalogued_variants import catalogued_variant_client_doc_for_tournament
from const import ARENA, T_CREATED
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from team import get_team
from tournament.tournaments import (
    creator_can_manage_tournament,
    get_tournament_name,
    load_tournament,
)
from tournament_director import is_tournament_director
from typing_defs import ViewContext
from variants import is_catalogued_variant

from views import get_user_context


@aiohttp_jinja2.template("index.html")
async def tournament(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)

    app_state = get_app_state(request.app)

    tournamentId = request.match_info["tournamentId"]
    tournament = await load_tournament(app_state, tournamentId)

    if tournament is None:
        raise web.HTTPNotFound(text="Tournament not found.")

    if is_catalogued_variant(tournament.variant):
        catalogued_variants = json.loads(str(context.get("catalogued_variants") or "[]"))
        if not any(item.get("name") == tournament.variant for item in catalogued_variants):
            catalogued_doc = await catalogued_variant_client_doc_for_tournament(
                app_state, tournament.variant
            )
            if catalogued_doc is not None:
                catalogued_variants.append(catalogued_doc)
                context["catalogued_variants"] = json_dumps(catalogued_variants)

    director = is_tournament_director(user, app_state)
    creator_can_manage = (
        not user.anon
        and not user.bot
        and await creator_can_manage_tournament(app_state, tournament, user.username)
    )
    can_cancel = director or (
        not user.anon
        and not user.bot
        and creator_can_manage
        and not tournament.frequency
        and (tournament.system == ARENA or bool(tournament.team_id))
    )
    if can_cancel and tournament.status == T_CREATED and request.path.endswith("/cancel"):
        await tournament.abort()
        raise web.HTTPFound("/tournaments")

    if request.path.endswith("/pause") and tournament.get_player_by_name(user.username) is not None:
        await tournament.pause(user)
        raise web.HTTPFound(f"/tournament/{tournamentId}")

    tournament_name = await get_tournament_name(request, tournamentId)
    context["tournamentid"] = tournamentId
    context["tournamentdirector"] = director
    context["tournamentmanager"] = creator_can_manage
    context["tournamentname"] = tournament_name
    context["tournamentcreator"] = tournament.creator
    context["tournamentteamid"] = tournament.team_id
    context["tournamentteamname"] = ""
    if tournament.team_id:
        team = await get_team(app_state, tournament.team_id)
        context["tournamentteamname"] = (
            str(team["name"]) if team is not None else tournament.team_id
        )
    context["description"] = tournament.description
    context["variant"] = tournament.variant
    context["chess960"] = tournament.chess960
    context["rated"] = tournament.rated
    context["base"] = tournament.base
    context["inc"] = tournament.inc
    context["byo"] = tournament.byoyomi_period
    context["fen"] = tournament.fen
    context["before_start"] = tournament.before_start
    context["minutes"] = tournament.minutes
    context["date"] = tournament.starts_at
    context["rounds"] = tournament.rounds
    context["system"] = tournament.system
    context["frequency"] = tournament.frequency
    context["status"] = tournament.status
    context["title"] = tournament.browser_title

    return context
