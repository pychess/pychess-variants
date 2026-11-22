import aiohttp_jinja2
from aiohttp import web
from header_challenges import challenge_participants, cleanup_expired_direct_challenges
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext

from views import add_catalogued_variant_context, get_user_context


@aiohttp_jinja2.template("index.html")
async def direct_challenge(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)
    app_state = get_app_state(request.app)
    cleanup_expired_direct_challenges(app_state)

    seek_id = request.match_info["seekId"]
    context["view"] = "challenge"
    context["view_css"] = "invite.css"
    context["challengeid"] = seek_id
    context["title"] = "Challenge • PyChess"

    seek = app_state.seeks.get(seek_id)
    if (
        seek is None
        or (not seek.is_direct_challenge)
        or user.username not in challenge_participants(seek)
    ):
        return context

    context["variant"] = seek.variant
    await add_catalogued_variant_context(app_state, user, context, seek.variant)
    context["chess960"] = seek.chess960
    context["rated"] = seek.rated
    context["corr"] = seek.day > 0
    context["base"] = seek.base
    context["inc"] = seek.inc
    context["byo"] = seek.byoyomi_period
    return context
