import aiohttp_jinja2
from aiohttp import web
from typing_defs import ViewContext

from views import get_user_context


@aiohttp_jinja2.template("accessibility.html")
async def accessibility(request: web.Request) -> ViewContext:
    """Render the accessibility guide for screen-reader and keyboard users."""
    _user, context = await get_user_context(request)

    context["title"] = "Accessibility • PyChess"
    context["view"] = "faq"
    context["view_css"] = "faq.css"
    return context
