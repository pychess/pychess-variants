from aiohttp import web
from const import category_matches
from pychess_global_app_state_utils import get_app_state
from ublog import post_url

from views import get_user_context


async def blog(request: web.Request) -> web.StreamResponse:
    _user, context = await get_user_context(request)
    app_state = get_app_state(request.app)

    blog_id = request.match_info.get("blogId")
    if app_state.db is None or blog_id is None:
        raise web.HTTPNotFound()

    migrated = await app_state.db.ublog_post2.find_one(
        {"legacyBlogId": blog_id, "live": True, "blogType": "site"},
        {"_id": 1, "author": 1, "slug": 1, "category": 1},
    )
    if migrated is None:
        raise web.HTTPNotFound()

    author = str(migrated.get("author") or "")
    author_profile = await app_state.public_users.get_profile(author)
    if author_profile is None or not author_profile.enabled:
        raise web.HTTPNotFound()

    category = migrated.get("category", "all")
    game_category = context["game_category"]
    if game_category != "all" and not category_matches(game_category, category):
        raise web.HTTPNotFound()

    raise web.HTTPFound(post_url(migrated))
