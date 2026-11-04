import aiohttp_jinja2
from aiohttp import web
from const import HTTP_ANON_USER
from json_utils import json_dumps
from puzzle import (
    default_puzzle_perf,
    get_daily_puzzle,
    get_puzzle,
    next_puzzle,
)
from typing_defs import ViewContext
from variants import VARIANTS

from views import get_user_context


@aiohttp_jinja2.template("analysis.html")
async def puzzle(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)

    variant = request.match_info.get("variant")

    if request.path.endswith("/daily"):
        puzzle = await get_daily_puzzle(request)
    else:
        puzzleId = request.match_info.get("puzzleId")

        if puzzleId in VARIANTS:
            selected_puzzle_variant = puzzleId
            puzzleId = None
        elif variant in VARIANTS:
            selected_puzzle_variant = variant
        else:
            selected_puzzle_variant = None

        if user.username != HTTP_ANON_USER:
            user.puzzle_variant = selected_puzzle_variant

        if puzzleId is None:
            puzzle = await next_puzzle(
                request,
                user,
                puzzle_variant=selected_puzzle_variant,
                use_user_variant=user.username != HTTP_ANON_USER,
            )
        else:
            puzzle = await get_puzzle(request, puzzleId)

    if puzzle is None:
        raise web.HTTPNotFound()

    color = puzzle["f"].split()[1]
    chess960 = False
    dafault_perf = default_puzzle_perf(puzzle["e"])
    puzzle_rating = int(round(puzzle.get("perf", dafault_perf)["gl"]["r"], 0))
    variant = puzzle["v"]
    if color == "w":
        wrating = int(round(user.get_puzzle_rating(variant, chess960).mu, 0))
        brating = puzzle_rating
    else:
        brating = int(round(user.get_puzzle_rating(variant, chess960).mu, 0))
        wrating = puzzle_rating

    context["view_css"] = "analysis.css"
    context["variant"] = variant
    context["fen"] = puzzle["f"]
    context["wrating"] = wrating
    context["brating"] = brating
    context["puzzle"] = json_dumps(puzzle)

    return context
