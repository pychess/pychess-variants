from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import aiohttp_jinja2
from aiohttp import web
from forum.storage import recompute_categ_summary, refresh_post_author_count, topic_by_tree
from newid import new_id
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from settings import ADMINS
from typing_defs import ViewContext
from ublog import (
    UBLOG_MAX_IMAGE_TEXT_LEN,
    UBLOG_MAX_INTRO_LEN,
    UBLOG_MAX_MARKDOWN_LEN,
    UBLOG_MAX_TITLE_LEN,
    UBLOG_TOPIC_WHITELIST,
    display_date,
    image_src,
    is_owner,
    normalize_topics,
    post_url,
    safe_trim,
    sanitize_image_url,
    slugify_title,
    summary_from_markdown,
    to_bool,
)

from views import get_user_context

UBLOG_DISCUSS_CATEG_ID = "community-blog-discussions"
UBLOG_DISCUSS_CATEG_NAME = "Community Blog Discussions"
UBLOG_DISCUSS_CATEG_DESC = "Discuss community blog posts."
UBLOG_DISCUSS_CATEG_ORDER = 25
UBLOG_DISCUSS_TEXT_PREFIX = "Comments on "


def _safe_path_segment(value: str) -> str:
    return quote(value, safe="")


def _blog_post_edit_url(profile_id: str, post_id: str) -> str:
    return f"/blogs/@/{_safe_path_segment(profile_id)}/{_safe_path_segment(post_id)}/edit"


def _blog_drafts_url(profile_id: str) -> str:
    return f"/blogs/@/{_safe_path_segment(profile_id)}/drafts"


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


def _likes_from_doc(post: dict[str, Any]) -> set[str]:
    likes_raw = post.get("likes")
    if not isinstance(likes_raw, list):
        return set()
    return {str(username) for username in likes_raw if isinstance(username, str)}


def _ublog_discuss_slug(post_id: str) -> str:
    return f"ublog-{post_id.lower()}"


async def _ensure_ublog_discuss_categ(app_state: Any) -> None:
    if app_state.db is None:
        return
    await app_state.db.forum_categ.update_one(
        {"_id": UBLOG_DISCUSS_CATEG_ID},
        {
            "$set": {
                "name": UBLOG_DISCUSS_CATEG_NAME,
                "desc": UBLOG_DISCUSS_CATEG_DESC,
                "order": UBLOG_DISCUSS_CATEG_ORDER,
            },
            "$setOnInsert": {
                "nbTopics": 0,
                "nbPosts": 0,
                "lastPostId": None,
                "lastPostAt": None,
                "lastPostUser": "",
                "lastTopicSlug": "",
                "lastTopicName": "",
                "lastTopicPage": 1,
            },
        },
        upsert=True,
    )


async def _discuss_topic_url(app_state: Any, post: dict[str, Any]) -> str:
    if app_state.db is None:
        return "/forum"

    await _ensure_ublog_discuss_categ(app_state)
    post_id = str(post.get("_id") or "")
    slug = _ublog_discuss_slug(post_id)
    blog_url = post_url(post)
    topic = await topic_by_tree(app_state, UBLOG_DISCUSS_CATEG_ID, slug)
    if topic is None:
        now = datetime.now(UTC)
        topic_id = await new_id(app_state.db.forum_topic)
        discuss_post_id = await new_id(app_state.db.forum_post)
        author = str(post.get("author") or "")
        topic_doc = {
            "_id": topic_id,
            "categId": UBLOG_DISCUSS_CATEG_ID,
            "slug": slug,
            "name": str(post.get("title") or "Blog discussion"),
            "user": author,
            "createdAt": now,
            "updatedAt": now,
            "nbPosts": 1,
            "lastPostId": discuss_post_id,
            "lastPostAt": now,
            "lastPostUser": author,
            "closed": False,
            "sticky": False,
            "blogPostId": post_id,
            "blogPostUrl": blog_url,
        }
        discuss_post_doc = {
            "_id": discuss_post_id,
            "topicId": topic_id,
            "categId": UBLOG_DISCUSS_CATEG_ID,
            "user": author,
            "text": f"{UBLOG_DISCUSS_TEXT_PREFIX}{blog_url}",
            "createdAt": now,
            "updatedAt": None,
            "editCount": 0,
        }
        await app_state.db.forum_topic.insert_one(topic_doc)
        await app_state.db.forum_post.insert_one(discuss_post_doc)
        await refresh_post_author_count(app_state, discuss_post_doc)
        await recompute_categ_summary(app_state, UBLOG_DISCUSS_CATEG_ID)

    safe_categ = quote(UBLOG_DISCUSS_CATEG_ID, safe="")
    safe_slug = quote(slug, safe="")
    return f"/forum/{safe_categ}/{safe_slug}"


def _empty_form_values() -> dict[str, Any]:
    return {
        "title": "",
        "intro": "",
        "markdown": "",
        "topics": "",
        "language": "en",
        "image": "",
        "imageAlt": "",
        "imageCredit": "",
        "live": False,
        "discuss": False,
        "sticky": False,
        "siteBlog": False,
    }


def _to_card(post: dict[str, Any], author_title: str) -> dict[str, Any]:
    image = post.get("image") or ""
    summary = summary_from_markdown(str(post.get("markdown") or ""))
    intro = str(post.get("intro") or post.get("subtitle") or summary)
    return {
        "_id": post["_id"],
        "slug": post.get("slug", ""),
        "author": post.get("author", ""),
        "author_title": author_title,
        "title": post.get("title", ""),
        "intro": intro,
        "subtitle": intro,
        "summary": summary,
        "topics": post.get("topics", []),
        "image": image,
        "imageAlt": post.get("imageAlt") or "",
        "date": display_date(post),
        "live": bool(post.get("live")),
        "sticky": bool(post.get("sticky")),
        "url": post_url(post),
        "image_src": image_src(post),
    }


async def _cards_from_posts(app_state: Any, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(posts) == 0:
        return []

    authors = list(dict.fromkeys(str(post.get("author") or "") for post in posts))
    profiles = await asyncio.gather(
        *(app_state.public_users.get_profile(author) for author in authors)
    )
    enabled_authors = {
        author
        for author, profile in zip(authors, profiles, strict=True)
        if profile is not None and profile.enabled
    }
    visible_posts = [post for post in posts if str(post.get("author") or "") in enabled_authors]
    if len(visible_posts) == 0:
        return []

    titles = await app_state.public_users.get_titles(enabled_authors)
    return [_to_card(post, titles.get(str(post.get("author") or ""), "")) for post in visible_posts]


async def _profile_exists(app_state: Any, profile_id: str) -> bool:
    profile = await app_state.public_users.get_profile(profile_id)
    return profile is not None and profile.enabled


async def _load_post(app_state: Any, post_id: str, profile_id: str) -> dict[str, Any] | None:
    if app_state.db is None:
        return None
    post = await app_state.db.ublog_post2.find_one({"_id": post_id, "author": profile_id})
    if post is None:
        return None
    return post


def _form_values_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    values = _empty_form_values()
    values.update(
        {
            "title": str(doc.get("title") or ""),
            "intro": str(doc.get("intro") or ""),
            "markdown": str(doc.get("markdown") or ""),
            "topics": ",".join(doc.get("topics", [])),
            "language": str(doc.get("language") or "en"),
            "image": str(doc.get("image") or ""),
            "imageAlt": str(doc.get("imageAlt") or ""),
            "imageCredit": str(doc.get("imageCredit") or ""),
            "live": bool(doc.get("live")),
            "discuss": bool(doc.get("discuss")),
            "sticky": bool(doc.get("sticky")),
            "siteBlog": str(doc.get("blogType") or "") == "site",
        }
    )
    return values


def _build_form_context(
    context: ViewContext,
    profile_id: str,
    values: dict[str, Any],
    errors: list[str],
    post: dict[str, Any] | None = None,
) -> ViewContext:
    context["title"] = "Blog editor • PyChess"
    context["view_css"] = "ublog.css"
    context["profile"] = profile_id
    context["ublog_values"] = values
    context["ublog_errors"] = errors
    context["ublog_topic_whitelist"] = UBLOG_TOPIC_WHITELIST
    context["ublog_post"] = post
    context["ublog_create_mode"] = post is None
    context["ublog_cancel_url"] = f"/blogs/@/{profile_id}" if post is None else post_url(post)
    context["ublog_can_publish_site"] = bool(context.get("admin"))
    return context


def _extract_form_values(data: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    values = dict(defaults)
    values["title"] = safe_trim(str(data.get("title") or values["title"]), UBLOG_MAX_TITLE_LEN)
    values["intro"] = safe_trim(str(data.get("intro") or values["intro"]), UBLOG_MAX_INTRO_LEN)
    values["markdown"] = safe_trim(
        str(data.get("markdown") or values["markdown"]), UBLOG_MAX_MARKDOWN_LEN
    )
    topic_values: list[str] = []
    getall = getattr(data, "getall", None)
    if callable(getall):
        for raw_topic in getall("topics", []):
            topic = safe_trim(str(raw_topic), 48)
            if topic != "":
                topic_values.append(topic)
        values["topics"] = safe_trim(",".join(topic_values), 300)
    else:
        values["topics"] = safe_trim(str(data.get("topics") or values["topics"]), 300)
    values["language"] = safe_trim(str(data.get("language") or values["language"]), 16) or "en"
    values["image"] = safe_trim(str(data.get("image") or values["image"]), 400)
    values["imageAlt"] = safe_trim(
        str(data.get("imageAlt") or values["imageAlt"]), UBLOG_MAX_IMAGE_TEXT_LEN
    )
    values["imageCredit"] = safe_trim(
        str(data.get("imageCredit") or values["imageCredit"]), UBLOG_MAX_IMAGE_TEXT_LEN
    )
    values["live"] = to_bool(data.get("live"))
    values["discuss"] = to_bool(data.get("discuss"))
    values["sticky"] = to_bool(data.get("sticky"))
    values["siteBlog"] = to_bool(data.get("siteBlog"))
    return values


def _validate_content(values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if len(values["title"]) < 3:
        errors.append("title_too_short")
    if len(values["intro"]) < 3:
        errors.append("intro_too_short")
    if len(values["markdown"]) < 3:
        errors.append("body_too_short")
    return errors


def _validate_media(values: dict[str, Any]) -> list[str]:
    image = sanitize_image_url(values["image"])
    if values["image"] != "" and image is None:
        return ["invalid_image_url"]
    return []


def _validate_full(values: dict[str, Any]) -> list[str]:
    errors = _validate_content(values)
    errors.extend(_validate_media(values))
    return errors


@aiohttp_jinja2.template("ublog_community.html")
async def community(request: web.Request) -> ViewContext:
    _user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    topic = (request.rel_url.query.get("topic") or "").strip().lower()
    if app_state.db is None:
        context["community_posts"] = []
        context["community_topic"] = topic
        context["community_topics"] = []
        context["title"] = "Community blogs • PyChess"
        context["view_css"] = "ublog.css"
        return context

    query: dict[str, Any] = {
        "live": True,
        "$or": [{"blogType": {"$exists": False}}, {"blogType": {"$ne": "site"}}],
    }
    if topic != "":
        query["topics"] = topic
    cursor = app_state.db.ublog_post2.find(query).sort(
        [("sticky", -1), ("publishedAt", -1), ("createdAt", -1)]
    )
    posts = await cursor.limit(60).to_list(60)
    context["community_posts"] = await _cards_from_posts(app_state, posts)
    context["community_topic"] = topic
    context["community_topics"] = sorted(
        t
        for t in await app_state.db.ublog_post2.distinct(
            "topics",
            {
                "live": True,
                "$or": [{"blogType": {"$exists": False}}, {"blogType": {"$ne": "site"}}],
            },
        )
        if isinstance(t, str)
    )
    context["title"] = "Community blogs • PyChess"
    context["view_css"] = "ublog.css"
    return context


async def discuss(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    post_id = request.match_info["postId"]
    if app_state.db is None:
        raise web.HTTPFound("/forum")

    post = await app_state.db.ublog_post2.find_one({"_id": post_id, "live": True})
    if post is None:
        raise web.HTTPFound("/forum")

    discuss_url = await _discuss_topic_url(app_state, post)
    raise web.HTTPFound(discuss_url)


async def like(request: web.Request) -> web.StreamResponse:
    user, _context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    post_id = request.match_info["postId"]
    wants_json = (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    if not await _profile_exists(app_state, profile_id):
        if wants_json:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        raise web.HTTPNotFound()

    doc = await _load_post(app_state, post_id, profile_id)
    if doc is None or not bool(doc.get("live")):
        if wants_json:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        raise web.HTTPNotFound()
    if app_state.db is None:
        if wants_json:
            return web.json_response({"ok": False, "error": "db_unavailable"}, status=503)
        raise web.HTTPServiceUnavailable(text="Database unavailable")
    if user.anon or is_owner(user.username, profile_id, user.anon):
        if wants_json:
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)
        raise web.HTTPFound(post_url(doc))

    likes = _likes_from_doc(doc)
    liked = user.username in likes
    if user.username in likes:
        await app_state.db.ublog_post2.update_one(
            {"_id": post_id, "author": profile_id},
            {"$pull": {"likes": user.username}},
        )
        liked = False
    else:
        result = await app_state.db.ublog_post2.update_one(
            {"_id": post_id, "author": profile_id},
            {"$addToSet": {"likes": user.username}},
        )
        liked = True
        if result.modified_count > 0:
            await app_state.timeline.publish(
                "ublog-post-like",
                user,
                {
                    "profile": profile_id,
                    "slug": str(doc.get("slug") or ""),
                    "postId": post_id,
                    "title": str(doc.get("title") or ""),
                },
            )

    if wants_json:
        updated = await app_state.db.ublog_post2.find_one(
            {"_id": post_id, "author": profile_id}, {"likes": 1}
        )
        updated_likes = _likes_from_doc(updated or {})
        return web.json_response({"ok": True, "liked": liked, "likes": len(updated_likes)})
    raise web.HTTPFound(post_url(doc))


async def like_redirect(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    post_id = request.match_info["postId"]
    if not await _profile_exists(app_state, profile_id):
        raise web.HTTPNotFound()

    doc = await _load_post(app_state, post_id, profile_id)
    if doc is None:
        raise web.HTTPFound("/blogs/community")
    raise web.HTTPFound(post_url(doc))


@aiohttp_jinja2.template("ublog_index.html")
async def user_blog(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    if not await _profile_exists(app_state, profile_id):
        raise web.HTTPNotFound()

    if app_state.db is None:
        context["ublog_posts"] = []
    else:
        posts = await (
            app_state.db.ublog_post2.find({"author": profile_id, "live": True})
            .sort([("sticky", -1), ("publishedAt", -1), ("createdAt", -1)])
            .limit(50)
            .to_list(50)
        )
        context["ublog_posts"] = await _cards_from_posts(app_state, posts)

    context["profile"] = profile_id
    context["ublog_is_owner"] = is_owner(user.username, profile_id, user.anon)
    context["ublog_is_drafts"] = False
    context["title"] = f"By {profile_id} • PyChess"
    context["view_css"] = "ublog.css"
    return context


@aiohttp_jinja2.template("ublog_index.html")
async def drafts(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    if not is_owner(user.username, profile_id, user.anon):
        raise web.HTTPForbidden()

    if app_state.db is None:
        context["ublog_posts"] = []
    else:
        posts = await (
            app_state.db.ublog_post2.find({"author": profile_id, "live": False})
            .sort([("updatedAt", -1), ("createdAt", -1)])
            .limit(50)
            .to_list(50)
        )
        context["ublog_posts"] = await _cards_from_posts(app_state, posts)

    context["profile"] = profile_id
    context["ublog_is_owner"] = True
    context["ublog_is_drafts"] = True
    context["title"] = f"{profile_id} drafts • PyChess"
    context["view_css"] = "ublog.css"
    return context


@aiohttp_jinja2.template("ublog_post.html")
async def post(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    post_id = request.match_info["postId"]
    slug = request.match_info["slug"]
    if not await _profile_exists(app_state, profile_id):
        raise web.HTTPNotFound()

    doc = await _load_post(app_state, post_id, profile_id)
    if doc is None:
        raise web.HTTPNotFound()

    owner = is_owner(user.username, profile_id, user.anon)
    if not bool(doc.get("live")) and not owner:
        raise web.HTTPNotFound()

    canonical = post_url(doc)
    if not canonical.endswith(f"/{slug}/{post_id}"):
        raise web.HTTPFound(canonical)

    if (
        app_state.db is not None
        and request.method == "GET"
        and bool(doc.get("live"))
        and not user.anon
    ):
        result = await app_state.db.ublog_post2.update_one(
            {
                "_id": post_id,
                "author": profile_id,
                "live": True,
                "viewers": {"$ne": user.username},
            },
            {
                "$addToSet": {"viewers": user.username},
                "$inc": {"views": 1},
            },
        )
        if result.modified_count == 1:
            doc["views"] = int(doc.get("views", 0)) + 1

    related_docs: list[dict[str, Any]] = []
    if app_state.db is not None:
        related_docs = await (
            app_state.db.ublog_post2.find(
                {"author": profile_id, "live": True, "_id": {"$ne": doc["_id"]}},
            )
            .sort([("publishedAt", -1), ("createdAt", -1)])
            .limit(3)
            .to_list(3)
        )

    cards = await _cards_from_posts(app_state, [doc] + related_docs)
    post_card = cards[0]
    related_cards = cards[1:]
    post_card["markdown"] = str(doc.get("markdown") or "")
    post_card["imageCredit"] = str(doc.get("imageCredit") or "")
    post_card["views"] = int(doc.get("views", 0))
    post_card["discuss"] = bool(doc.get("discuss")) or str(doc.get("blogType") or "") == "site"
    post_card["language"] = str(doc.get("language") or "en")
    post_card["image_src"] = image_src(doc)
    likes = _likes_from_doc(doc)
    post_card["likes"] = len(likes)
    post_card["liked"] = (not user.anon) and (user.username in likes)

    author_profile = await app_state.public_users.get_profile(profile_id, include_blocked=False)
    context["profile"] = profile_id
    context["ublog_is_owner"] = owner
    context["ublog_author_online"] = profile_id in app_state.users
    context["ublog_author_patron"] = bool(author_profile is not None and author_profile.patron)
    context["ublog_post"] = post_card
    context["ublog_related"] = related_cards
    context["title"] = f"{post_card['title']} • PyChess"
    context["view_css"] = "ublog.css"
    return context


@aiohttp_jinja2.template("ublog_form.html")
async def new_form(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    if not await _profile_exists(app_state, profile_id):
        raise web.HTTPNotFound()
    if not is_owner(user.username, profile_id, user.anon):
        raise web.HTTPForbidden()

    return _build_form_context(context, profile_id, _empty_form_values(), [])


async def create(request: web.Request) -> web.Response:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database unavailable")
    if not await _profile_exists(app_state, profile_id):
        raise web.HTTPNotFound()
    if not is_owner(user.username, profile_id, user.anon):
        raise web.HTTPForbidden()

    data = await read_post_data(request)
    if data is None:
        raise web.HTTPBadRequest(text="Invalid form data")

    values = _extract_form_values(data, _empty_form_values())
    errors = _validate_full(values)

    if errors:
        ctx = _build_form_context(context, profile_id, values, errors)
        return await aiohttp_jinja2.render_template_async(
            "ublog_form.html", request, ctx, status=400
        )

    now = datetime.now(UTC)
    post_id = await new_id(app_state.db.ublog_post2)
    topics = normalize_topics(values["topics"])
    image = sanitize_image_url(values["image"])
    doc = {
        "_id": post_id,
        "author": profile_id,
        "slug": slugify_title(values["title"]),
        "title": values["title"],
        "intro": values["intro"],
        "markdown": values["markdown"],
        "topics": topics,
        "language": values["language"],
        "image": image or "",
        "imageAlt": values["imageAlt"],
        "imageCredit": values["imageCredit"],
        "live": False,
        "discuss": False,
        "sticky": False,
        "views": 0,
        "viewers": [],
        "likes": [],
        "createdAt": now,
        "updatedAt": now,
        "publishedAt": None,
    }
    await app_state.db.ublog_post2.insert_one(doc)
    raise web.HTTPFound(_blog_post_edit_url(profile_id, post_id))


@aiohttp_jinja2.template("ublog_form.html")
async def edit_form(request: web.Request) -> ViewContext:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    post_id = request.match_info["postId"]
    if not is_owner(user.username, profile_id, user.anon):
        raise web.HTTPForbidden()
    doc = await _load_post(app_state, post_id, profile_id)
    if doc is None:
        raise web.HTTPNotFound()
    values = _form_values_from_doc(doc)
    return _build_form_context(context, profile_id, values, [], post=doc)


async def update(request: web.Request) -> web.Response:
    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    post_id = request.match_info["postId"]
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database unavailable")
    if not is_owner(user.username, profile_id, user.anon):
        raise web.HTTPForbidden()

    doc = await _load_post(app_state, post_id, profile_id)
    if doc is None:
        raise web.HTTPNotFound()

    data = await read_post_data(request)
    if data is None:
        raise web.HTTPBadRequest(text="Invalid form data")

    action = str(data.get("action") or "apply")
    values = _extract_form_values(data, _form_values_from_doc(doc))
    errors = _validate_full(values)

    if errors:
        ctx = _build_form_context(context, profile_id, values, errors, post=doc)
        return await aiohttp_jinja2.render_template_async(
            "ublog_form.html", request, ctx, status=400
        )

    image = sanitize_image_url(values["image"])
    next_live = values["live"]
    can_publish_site = _is_admin_username(user.username)
    update_fields: dict[str, Any] = {
        "updatedAt": datetime.now(UTC),
        "title": values["title"],
        "intro": values["intro"],
        "markdown": values["markdown"],
        "topics": normalize_topics(values["topics"]),
        "language": values["language"],
        "slug": slugify_title(values["title"]),
        "image": image or "",
        "imageAlt": values["imageAlt"],
        "imageCredit": values["imageCredit"],
        "live": next_live,
        "discuss": values["discuss"],
        "sticky": values["sticky"],
    }
    if can_publish_site:
        # Admins can publish posts into the official "By PyChess" stream.
        if bool(values.get("siteBlog")):
            update_fields["blogType"] = "site"
            update_fields["isOfficial"] = True
        else:
            update_fields["blogType"] = "community"
            update_fields["isOfficial"] = False
    if next_live and not bool(doc.get("live")):
        update_fields["publishedAt"] = datetime.now(UTC)
    elif not next_live:
        update_fields["publishedAt"] = None

    await app_state.db.ublog_post2.update_one({"_id": post_id}, {"$set": update_fields})
    updated = await _load_post(app_state, post_id, profile_id)
    if updated is None:
        raise web.HTTPNotFound()

    if next_live and not bool(doc.get("live")):
        await app_state.timeline.publish(
            "ublog-post",
            user,
            {
                "postId": post_id,
                "slug": str(updated.get("slug") or ""),
                "title": str(updated.get("title") or ""),
            },
        )

    if action == "view-post" and bool(updated.get("live")):
        raise web.HTTPFound(post_url(updated))
    raise web.HTTPFound(_blog_post_edit_url(profile_id, post_id))


async def delete(request: web.Request) -> web.Response:
    user, _context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]
    post_id = request.match_info["postId"]
    if app_state.db is None:
        raise web.HTTPServiceUnavailable(text="Database unavailable")
    if not is_owner(user.username, profile_id, user.anon):
        raise web.HTTPForbidden()
    await app_state.db.ublog_post2.delete_one({"_id": post_id, "author": profile_id})
    raise web.HTTPFound(_blog_drafts_url(profile_id))
