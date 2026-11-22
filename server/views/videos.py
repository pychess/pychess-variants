from urllib.parse import quote

import aiohttp_jinja2
from aiohttp import web
from const import category_matches
from pagination import page_href, page_number
from pychess_global_app_state_utils import get_app_state
from typing_defs import ViewContext
from videos import VIDEO_CATEGORIES, VIDEO_TAGS, VIDEO_TARGETS

from views import get_user_context

VIDEO_PAGE_SIZE = 24


def _category_query(game_category: str) -> dict:
    if game_category == "all":
        return {}
    excluded_legacy_ids = [
        video_id
        for video_id, category in VIDEO_CATEGORIES.items()
        if not category_matches(game_category, category)
    ]
    return {
        "$or": [
            {"category": {"$in": ["all", game_category]}},
            {"$and": [{"category": None}, {"category": {"$exists": True}}]},
            {"category": {"$exists": False}, "_id": {"$nin": excluded_legacy_ids}},
        ]
    }


@aiohttp_jinja2.template("videos.html")
async def videos(request: web.Request) -> ViewContext:
    _user, context = await get_user_context(request)
    game_category = context["game_category"]

    app_state = get_app_state(request.app)

    tag = request.rel_url.query.get("tags")
    category_query = _category_query(game_category)
    query = {**category_query, **({"tags": tag} if tag is not None else {})}
    page = page_number(request)
    videos = await (
        app_state.db.video.find(query)
        .sort("_id", 1)
        .skip((page - 1) * VIDEO_PAGE_SIZE)
        .limit(VIDEO_PAGE_SIZE + 1)
        .to_list(length=VIDEO_PAGE_SIZE + 1)
    )

    lang = context["lang"]

    def video_tag(tag: str) -> str:
        return app_state.translations[lang].gettext(VIDEO_TAGS.get(tag, tag))

    def video_target(target: str) -> str:
        return app_state.translations[lang].gettext(VIDEO_TARGETS[target])

    context["videos"] = videos[:VIDEO_PAGE_SIZE]
    context["prev_page_href"] = page_href(request, page - 1) if page > 1 else None
    context["next_page_href"] = (
        page_href(request, page + 1) if len(videos) > VIDEO_PAGE_SIZE else None
    )
    if game_category != "all":
        # Keep tags available even when their videos occur on another page.
        available_tags = await app_state.db.video.distinct("tags", category_query)
        context["tags"] = [tag for tag in VIDEO_TAGS if tag in available_tags]
    else:
        context["tags"] = VIDEO_TAGS
    context["video_tag"] = video_tag
    context["video_target"] = video_target
    context["video_tag_query"] = lambda tag: quote(tag, safe="")

    return context
