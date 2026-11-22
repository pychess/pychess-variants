import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp_jinja2
from aiohttp import web
from const import ARENA, T_CREATED, T_STARTED, TRANSLATED_PAIRING_SYSTEM_NAMES
from misc import time_control_str
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from settings import ADMINS
from tournament.tournaments import (
    create_or_update_tournament,
    creator_can_manage_tournament,
    get_latest_tournaments,
    load_tournament,
)
from tournament_director import is_tournament_director
from typing_defs import ViewContext
from variants import VARIANT_ICONS

from views import get_user_context

log = logging.getLogger(__name__)


@aiohttp_jinja2.template("tournaments.html")
async def tournaments(request: web.Request) -> ViewContext | web.Response:
    user, context = await get_user_context(request)

    app_state = get_app_state(request.app)
    director = is_tournament_director(user, app_state)
    admin = user.username in ADMINS
    regular_creator = not user.anon and not user.bot

    if request.path.endswith("/abort"):
        if not admin:
            raise web.HTTPForbidden(text="Only site admins can abort tournaments.")
        tournamentId = request.match_info.get("tournamentId")
        tournament = app_state.tournaments.get(tournamentId) if tournamentId else None
        if tournament is None:
            raise web.HTTPNotFound(text="Tournament not found.")
        if tournament.status not in (T_CREATED, T_STARTED):
            raise web.HTTPBadRequest(text="Tournament has already ended.")
        await tournament.abort()
        raise web.HTTPFound(f"/tournament/{tournament.id}")

    if request.path.endswith("/delete"):
        if not admin:
            raise web.HTTPForbidden(text="Only site admins can delete tournaments.")
        tournamentId = request.match_info.get("tournamentId")
        tournament = await load_tournament(app_state, tournamentId) if tournamentId else None
        if tournament is None:
            raise web.HTTPNotFound(text="Tournament not found.")
        if tournament.system != ARENA:
            raise web.HTTPBadRequest(text="Only Arena tournaments can be deleted here.")
        if tournament.status in (T_CREATED, T_STARTED):
            raise web.HTTPBadRequest(text="Abort the tournament before deleting it.")
        if await tournament.has_pairing_history():
            raise web.HTTPBadRequest(text="Only Arena tournaments without pairings can be deleted.")
        await tournament.destroy()
        raise web.HTTPFound("/tournaments")

    if request.path.endswith("/new"):
        if not (director or regular_creator):
            raise web.HTTPForbidden(text="You must be logged in with a regular account.")
        data = await read_post_data(request)
        if data is None:
            raise web.HTTPNoContent()
        created = await create_or_update_tournament(
            app_state,
            user.username,
            data,
            creator_is_director=director,
        )
        # The same authenticated creation flow can serve automated local clients
        # without parsing the rendered tournament listing to discover the ID.
        if request.headers.get("Accept") == "application/json":
            return web.json_response({"tournamentId": created.id})

    elif request.path.endswith("/edit"):
        data = await read_post_data(request)
        if data is None:
            raise web.HTTPNoContent()

        tournamentId = request.match_info.get("tournamentId")
        tournament = app_state.tournaments.get(tournamentId) if tournamentId else None

        if tournament is None and tournamentId is not None:
            raise web.HTTPNotFound(text="Tournament not found.")
        if tournament and not admin:
            if user.username != tournament.creator:
                raise web.HTTPForbidden(
                    text="Only the tournament creator can edit this tournament."
                )
            if not await creator_can_manage_tournament(app_state, tournament, user.username):
                raise web.HTTPForbidden(
                    text="You need the tournament permission in this team to edit this tournament."
                )
            if not director and (
                not regular_creator
                or tournament.frequency
                or tournament.status != T_CREATED
                or (tournament.system != ARENA and not tournament.team_id)
            ):
                raise web.HTTPForbidden(text="This tournament cannot be edited by its creator.")

        if TYPE_CHECKING:
            assert tournament is not None
        task = tournament.clock_task
        if task is not None:
            taskname = task.get_name()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                log.debug("%s cancelled for tournament %s", taskname, tournament.id)
                tournament.clock_task = None

        try:
            await create_or_update_tournament(
                app_state,
                user.username,
                data,
                tournament,
                creator_is_director=director,
                editor_is_admin=admin,
            )
        finally:
            # Restored tournaments have with_clock=False, so initialize() does not
            # restart their clock. Rejected edits must also resume the old schedule.
            if (
                not app_state.shutdown
                and tournament.status in (T_CREATED, T_STARTED)
                and (tournament.clock_task is None or tournament.clock_task.done())
            ):
                tournament.clock_task = asyncio.create_task(
                    tournament.clock(), name="tournament-clock"
                )

    lang = context["lang"]
    gettext = app_state.translations[lang].gettext

    def pairing_system_name(system: int) -> str:
        return gettext(TRANSLATED_PAIRING_SYSTEM_NAMES[system])

    context["icons"] = VARIANT_ICONS
    context["pairing_system_name"] = pairing_system_name
    context["time_control_str"] = time_control_str
    tables = await get_latest_tournaments(app_state, lang)
    if context["game_category"] != "all":
        allowed_variants = context["category_variant_set"]
        started, scheduled, completed = tables
        started = [
            t for t in started if (t.variant + ("960" if t.chess960 else "")) in allowed_variants
        ]
        scheduled = [
            t for t in scheduled if (t.variant + ("960" if t.chess960 else "")) in allowed_variants
        ]
        completed = [
            t for t in completed if (t.variant + ("960" if t.chess960 else "")) in allowed_variants
        ]
        tables = (started, scheduled, completed)
    context["tables"] = tables
    context["td"] = director or regular_creator

    return context
