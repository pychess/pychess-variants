import aiohttp_jinja2
from aiohttp import web
from typing_defs import ViewContext
from variants import VARIANT_ICONS, VARIANTS

from views import get_user_context


@aiohttp_jinja2.template("games.html")
async def games(request: web.Request) -> ViewContext:
    _user, context = await get_user_context(request, include_catalogued_variants=True)

    variant = request.match_info.get("variant")
    if (variant is not None) and (variant not in VARIANTS):
        variant = None

    context["variant"] = variant if variant is not None else ""
    context["variants"] = context["category_variants"]
    context["groups"] = context["category_variant_groups"]

    context["icons"] = VARIANT_ICONS

    return context
