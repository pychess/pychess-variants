import json

import aiohttp_jinja2
from aiohttp import web
from catalogued.variants import catalogued_variant_client_doc_for_name
from fairy import FairyBoard
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext
from utils import load_game
from variants import ALL_VARIANTS, is_catalogued_variant

from views import add_game_context, get_user_context


@aiohttp_jinja2.template("analysis.html")
async def analysis(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)

    gameId = request.match_info.get("gameId")
    variant_key = request.match_info.get("variant") or "chess"
    catalogued_doc = None
    if is_catalogued_variant(variant_key):
        catalogued_doc = catalogued_variant_client_doc_for_name(
            get_app_state(request.app), variant_key, user.username if not user.anon else None
        )
        if catalogued_doc is None:
            variant_key = "chess"
    server_variant = ALL_VARIANTS.get(variant_key)
    if server_variant is None:
        server_variant = ALL_VARIANTS["chess"]
    elif catalogued_doc is not None:
        catalogued_variants = json.loads(str(context.get("catalogued_variants") or "[]"))
        if not any(item.get("name") == variant_key for item in catalogued_variants):
            catalogued_variants.append(catalogued_doc)
            context["catalogued_variants"] = json_dumps(catalogued_variants)
    chess960 = bool(server_variant.chess960)
    variant = server_variant.uci_variant
    ply = request.rel_url.query.get("ply")

    if gameId is None:
        fen = request.rel_url.query.get("fen")
        if fen is None:
            fen = FairyBoard.start_fen(variant, chess960)
        else:
            fen = fen.replace(".", "+").replace("_", " ")
        context["fen"] = fen
        context["variant"] = variant
        context["chess960"] = chess960
    else:
        app_state = get_app_state(request.app)
        game = await load_game(app_state, gameId, cache_finished=False)
        if game is None:
            raise web.HTTPNotFound()

        add_game_context(game, ply, user, context)

        context["view"] = "analysis"
        context["view_css"] = "analysis.css"

        if not request.path.startswith("/corr"):
            context["ct"] = json_dumps(game.crosstable)

    return context
