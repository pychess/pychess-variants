import aiohttp_jinja2
from aiohttp import web
from typing_defs import ViewContext

from views import get_user_context


@aiohttp_jinja2.template("game_search.html")
async def game_search(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request, include_catalogued_variants=True)
    if user.anon:
        raise web.HTTPFound("/login")

    context["view"] = "game-search"
    context["view_css"] = "game-search.css"
    context["title"] = "Advanced game search • PyChess"
    context["search_query"] = request.rel_url.query
    return context
