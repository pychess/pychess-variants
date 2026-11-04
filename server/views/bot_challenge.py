import aiohttp_jinja2
from aiohttp import web
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext
from utils import load_game, remove_seek

from views import get_user_context


def set_bot_challenge_context(
    context: ViewContext,
    *,
    game_id: str,
    opponent: str,
    status: str,
    decline_reason: str = "",
) -> None:
    context["view"] = "bot_challenge"
    context["view_css"] = "invite.css"
    context["gameid"] = game_id
    context["bot_challenge_opponent"] = opponent
    context["bot_challenge_status"] = status
    context["bot_challenge_decline_reason"] = decline_reason


@aiohttp_jinja2.template("index.html")
async def bot_challenge(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)
    app_state = get_app_state(request.app)

    game_id = request.match_info["gameId"]
    seek = app_state.invites.get(game_id)

    if seek is not None and seek.is_bot_challenge and seek.creator.username == user.username:
        context["title"] = "Challenge • PyChess"
        context["variant"] = seek.variant
        context["chess960"] = seek.chess960
        context["rated"] = seek.rated
        context["corr"] = seek.day > 0
        context["base"] = seek.base
        context["inc"] = seek.inc
        context["byo"] = seek.byoyomi_period

        if seek.is_expired():
            app_state.invites.pop(game_id, None)
            remove_seek(app_state.seeks, seek)
            set_bot_challenge_context(context, game_id=game_id, opponent="", status="expired")
            return context

        opponent = seek.player2.username if seek.player2 is not None else ""
        set_bot_challenge_context(
            context,
            game_id=game_id,
            opponent=opponent,
            status=seek.bot_challenge_status or "created",
            decline_reason=seek.bot_challenge_decline_reason or "",
        )
        return context

    game = await load_game(app_state, game_id, cache_finished=False)
    if game is not None and user.username in (game.wplayer.username, game.bplayer.username):
        raise web.HTTPFound("/%s" % game_id)

    context["title"] = "Challenge • PyChess"
    context["variant"] = "chess"
    context["chess960"] = False
    context["rated"] = False
    context["corr"] = False
    context["base"] = 0
    context["inc"] = 0
    context["byo"] = 0
    set_bot_challenge_context(context, game_id=game_id, opponent="", status="expired")
    return context


async def cancel_bot_challenge(request: web.Request) -> web.StreamResponse:
    user, _ = await get_user_context(request)
    app_state = get_app_state(request.app)
    game_id = request.match_info["gameId"]

    seek = app_state.invites.get(game_id)
    if seek is not None and seek.is_bot_challenge and seek.creator.username == user.username:
        app_state.invites.pop(game_id, None)
        remove_seek(app_state.seeks, seek)

    raise web.HTTPFound("/")
