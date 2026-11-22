import aiohttp_jinja2
from aiohttp import web
from catalogued.variants import catalogued_variant_client_doc_for_name
from fairy import FairyBoard
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext
from variants import ALL_VARIANTS, is_catalogued_variant

from views import add_catalogued_client_docs_context, get_user_context


@aiohttp_jinja2.template("index.html")
async def editor(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)

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
        add_catalogued_client_docs_context(
            get_app_state(request.app), user, context, [catalogued_doc]
        )

    chess960 = bool(server_variant.chess960)
    variant = server_variant.uci_variant

    fen = request.rel_url.query.get("fen")
    if fen is None:
        fen = FairyBoard.start_fen(variant, chess960)
    else:
        fen = fen.replace(".", "+").replace("_", " ")

    context["variant"] = variant
    context["chess960"] = chess960
    context["fen"] = fen

    return context
