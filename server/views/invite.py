import logging

import aiohttp_jinja2
from aiohttp import web
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from sse_utils import enqueue_sse_payload
from typing_defs import ViewContext
from utils import join_seek, load_game, remove_seek

from views import add_catalogued_variant_context, add_game_context, get_user_context

log = logging.getLogger(__name__)


def set_expired_invite_context(context: ViewContext, game_id: str) -> None:
    context["gameid"] = game_id
    context["inviter"] = "expired"
    # Keep these populated so the generic page model remains valid.
    context["variant"] = "chess"
    context["chess960"] = False
    context["rated"] = False
    context["corr"] = False
    context["base"] = 0
    context["inc"] = 0
    context["byo"] = 0
    context["seekempty"] = False
    context["title"] = "Invitation expired • PyChess"


@aiohttp_jinja2.template("index.html")
async def invite(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)

    app_state = get_app_state(request.app)

    gameId = request.match_info["gameId"]
    inviter = None
    seek = None

    if (gameId not in app_state.games) and (gameId in app_state.invites):
        seek_id = app_state.invites[gameId].id
        seek = app_state.seeks.get(seek_id)
        if seek is None:
            # Invite exists but corresponding seek has already been deleted.
            app_state.invites.pop(gameId, None)
        elif seek.is_expired():
            app_state.invites.pop(gameId, None)
            remove_seek(app_state.seeks, seek)
            set_expired_invite_context(context, gameId)
            return context
        else:
            if request.path.startswith("/invite/accept/"):
                player = request.match_info.get("player") or "any"
                seek_status = await join_seek(app_state, user, seek, gameId, join_as=player)

                if seek_status["type"] == "seek_joined":
                    inviter = "wait"
                elif seek_status["type"] == "seek_occupied":
                    inviter = "occupied"
                elif seek_status["type"] == "seek_yourself":
                    inviter = "yourself"
                elif seek_status["type"] == "new_game":
                    try:
                        # Put response data to sse subscriber queue
                        channels = app_state.invite_channels.get(gameId, set())
                        for queue in channels:
                            enqueue_sse_payload(
                                queue,
                                json_dumps({"gameId": gameId, "accept": True}),
                                replace_pending=True,
                            )
                    except ConnectionResetError:
                        log.error("/invite/accept/ ConnectionResetError for user %s", user.username)
            else:
                inviter = seek.creator.username if user.username != seek.creator.username else ""
    if inviter is not None:
        context["gameid"] = gameId
        context["variant"] = seek.variant
        await add_catalogued_variant_context(app_state, user, context, seek.variant)
        context["chess960"] = seek.chess960
        context["rated"] = seek.rated
        context["corr"] = seek.day > 0
        context["base"] = seek.base
        context["inc"] = seek.inc
        context["byo"] = seek.byoyomi_period
        context["inviter"] = inviter
        context["seekempty"] = seek.player1 is None and seek.player2 is None
    else:
        # The new invite game started
        game = await load_game(app_state, gameId, cache_finished=False)
        if game is None:
            # Friendly fallback for stale or missing invite/game ids.
            set_expired_invite_context(context, gameId)
            return context

        add_game_context(game, None, user, context)
        await add_catalogued_variant_context(app_state, user, context, game.variant, game=game)

        context["view"] = "round"
        context["view_css"] = "round.css"

    return context
