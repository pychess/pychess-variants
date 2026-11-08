import aiohttp_jinja2
from aiohttp import web
from pagination import page_href, page_number
from site_blogs import get_site_blog_page
from typing_defs import ViewContext

from views import get_user_context

BLOG_PAGE_SIZE = 20


@aiohttp_jinja2.template("blogs.html")
async def blogs(request: web.Request) -> ViewContext:
    _user, context = await get_user_context(request)

    tag = (request.rel_url.query.get("tags") or "").strip().lower()
    page = page_number(request)
    blogs, topics = await get_site_blog_page(
        request, tag=tag, limit=BLOG_PAGE_SIZE + 1, skip=(page - 1) * BLOG_PAGE_SIZE
    )
    context["site_tag"] = tag
    context["site_tags"] = topics
    context["blogs"] = blogs[:BLOG_PAGE_SIZE]
    context["prev_page_href"] = page_href(request, page - 1) if page > 1 else None
    context["next_page_href"] = (
        page_href(request, page + 1) if len(blogs) > BLOG_PAGE_SIZE else None
    )
    return context
