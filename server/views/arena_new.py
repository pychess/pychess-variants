import aiohttp_jinja2
from aiohttp import web
from catalogued.variants import public_catalogued_variants_for_forms
from const import ARENA, T_CREATED, T_STARTED
from pychess_global_app_state import PychessGlobalAppState
from settings import ADMINS
from team import PERMISSION_TOURNAMENTS, get_team, teams_for_user
from tournament.tournaments import (
    COMMUNITY_ARENA_MAX_CREATIONS_PER_24H,
    FIXED_ROUND_MAX_CREATIONS_PER_24H,
    creator_can_manage_tournament,
)
from tournament_director import is_tournament_director
from typedefs import pychess_global_app_state_key as app_state_key
from typing_defs import ViewContext
from variants import VARIANTS

from views import get_user_context


@aiohttp_jinja2.template("arena-new.html")
async def arena_new(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)
    app_state: PychessGlobalAppState = request.app[app_state_key]

    tournamentId = request.match_info.get("tournamentId")
    director = is_tournament_director(user, app_state)
    admin = user.username in ADMINS

    if user.anon or user.bot:
        raise web.HTTPForbidden(text="You must be logged in with a regular account.")

    tournament_variants = {
        key: variant for key, variant in VARIANTS.items() if not variant.two_boards
    }
    catalogued_variants = public_catalogued_variants_for_forms(app_state)
    favorite_names = user.catalogued_variant_favorites
    favorite_variants = {
        key: variant for key, variant in catalogued_variants.items() if key in favorite_names
    }
    community_variants = {
        key: variant for key, variant in catalogued_variants.items() if key not in favorite_names
    }
    context["variants"] = {**tournament_variants, **catalogued_variants}
    context["site_variants"] = tournament_variants
    context["favorite_variants"] = favorite_variants
    context["community_variants_for_tournaments"] = community_variants
    context["view_css"] = "arena-new.css"
    context["edit"] = tournamentId is not None
    context["admin"] = admin
    context["tournament_director"] = director
    context["community_arena_max_creations_per_24h"] = COMMUNITY_ARENA_MAX_CREATIONS_PER_24H
    context["fixed_round_max_creations_per_24h"] = FIXED_ROUND_MAX_CREATIONS_PER_24H
    context["tournament_delete_allowed"] = False
    tournament_teams = await teams_for_user(
        app_state, user.username, permission=PERMISSION_TOURNAMENTS
    )
    selected_team_id = request.rel_url.query.get("team", "")
    if tournamentId is None:
        context["rated"] = True
    else:
        tournament = app_state.tournaments.get(tournamentId)
        if tournament is None:
            raise web.HTTPNotFound()
        if not admin:
            if user.username != tournament.creator:
                raise web.HTTPNotFound()
            if not await creator_can_manage_tournament(app_state, tournament, user.username):
                raise web.HTTPForbidden(
                    text="You need the tournament permission in this team to edit this tournament."
                )
            if not director and (
                tournament.frequency
                or tournament.status != T_CREATED
                or (tournament.system != ARENA and not tournament.team_id)
            ):
                raise web.HTTPForbidden(text="This tournament cannot be edited by its creator.")
        selected_team_id = tournament.team_id
        if selected_team_id and not any(
            str(team["_id"]) == selected_team_id for team in tournament_teams
        ):
            team = await get_team(app_state, selected_team_id)
            if team is not None:
                tournament_teams.append(team)
        context["tournament"] = tournament
        if admin and tournament.system == ARENA and tournament.status not in (T_CREATED, T_STARTED):
            context["tournament_delete_allowed"] = not await tournament.has_pairing_history()

    if selected_team_id and not any(
        str(team["_id"]) == selected_team_id for team in tournament_teams
    ):
        selected_team_id = ""
    context["tournament_teams"] = tournament_teams
    context["selected_tournament_team_id"] = selected_team_id

    return context
