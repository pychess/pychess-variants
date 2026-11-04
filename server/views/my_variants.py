import aiohttp_jinja2
from aiohttp import web
from typing_defs import ViewContext

from views import get_user_context


@aiohttp_jinja2.template("index.html")
async def my_variants(request: web.Request) -> ViewContext:
    _user, context = await get_user_context(request)
    context["title"] = "Manage my variants • PyChess"
    return context
