from __future__ import annotations

import re
from inspect import isawaitable
from typing import Any

import aiohttp_session
from aiohttp import web
from preferences import effective_game_category
from pychess_global_app_state_utils import get_app_state
from ublog import display_date, image_src, post_url


def _site_blog_pipeline(game_category: str, tag: str | None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"live": True, "blogType": "site"}
    if game_category != "all":
        query["$or"] = [{"category": {"$in": ["all", game_category]}}, {"category": None}]
    if tag:
        exact_tag = re.compile("^" + re.escape(tag.strip()) + "$", re.IGNORECASE)
        tag_query = {"$or": [{"tags": exact_tag}, {"topics": exact_tag}]}
        query = {"$and": [query, tag_query]}
    return [
        {"$match": query},
        {"$project": {"markdown": 0}},
        {
            "$lookup": {
                "from": "user",
                "localField": "author",
                "foreignField": "_id",
                "as": "_author",
            }
        },
        {"$unwind": "$_author"},
        {"$match": {"_author.enabled": {"$ne": False}}},
    ]


async def get_site_blog_page(
    request: web.Request,
    *,
    tag: str | None = None,
    limit: int = 21,
    skip: int = 0,
    include_topics: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return [], []
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user) if session_user else None
    game_category = effective_game_category(session, user)
    limit = max(1, min(limit, 100))
    pipeline = _site_blog_pipeline(game_category, tag)
    facets: dict[str, list[dict[str, Any]]] = {
        "posts": [
            {"$sort": {"sticky": -1, "publishedAt": -1, "createdAt": -1, "_id": -1}},
            {"$skip": max(0, skip)},
            {"$limit": limit},
            {"$project": {"_author": 0}},
        ],
    }
    if include_topics:
        # Only small tag metadata crosses the database boundary, independent of the page.
        facets["topics"] = [
            {"$project": {"topics": {"$ifNull": ["$topics", "$tags"]}}},
            {"$unwind": "$topics"},
            {"$match": {"topics": {"$type": "string", "$ne": ""}}},
            {"$group": {"_id": "$topics"}},
            {"$sort": {"_id": 1}},
            {"$limit": 100},
        ]
    if include_topics:
        pipeline.append({"$facet": facets})
    else:
        pipeline.extend(facets["posts"])
    result = app_state.db.ublog_post2.aggregate(pipeline)
    cursor = await result if isawaitable(result) else result
    if include_topics:
        batches = await cursor.to_list(length=1)
        batch = batches[0] if batches else {}
    else:
        batch = {"posts": await cursor.to_list(length=limit)}
    blogs: list[dict[str, Any]] = []
    for raw_doc in batch.get("posts", []):
        author = str(raw_doc.get("author") or "")
        category = raw_doc.get("category", "all")
        intro = str(raw_doc.get("intro") or raw_doc.get("subtitle") or "")
        image_alt = str(raw_doc.get("imageAlt") or raw_doc.get("alt") or "")
        tags_raw = raw_doc.get("tags")
        tags = [str(tag) for tag in tags_raw] if isinstance(tags_raw, list) else []
        topics_raw = raw_doc.get("topics")
        topics = (
            [str(topic) for topic in topics_raw]
            if isinstance(topics_raw, list)
            else [tag.lower() for tag in tags]
        )
        blogs.append(
            {
                "_id": str(raw_doc.get("legacyBlogId") or raw_doc.get("_id") or ""),
                "post_id": str(raw_doc.get("_id") or ""),
                "title": str(raw_doc.get("title") or ""),
                "intro": intro,
                "subtitle": intro,
                "author": author,
                "date": display_date(raw_doc),
                "image": str(raw_doc.get("image") or ""),
                "image_src": image_src(raw_doc),
                "imageAlt": image_alt,
                "alt": image_alt,
                "tags": tags,
                "topics": topics,
                "category": category,
                "categoryList": category if isinstance(category, list) else [category],
                "isOfficial": bool(raw_doc.get("isOfficial", True)),
                "blogType": "site",
                "url": post_url(raw_doc),
            }
        )
    titles = await app_state.public_users.get_titles(str(doc["author"]) for doc in blogs)
    for doc in blogs:
        title = titles.get(str(doc["author"]), "")
        doc["author_title"] = title
        doc["atitle"] = title
    topics = sorted({str(item["_id"]).casefold() for item in batch.get("topics", [])})
    return blogs, topics


async def get_blogs(
    request: web.Request, tag: str | None = None, limit: int = 3
) -> list[dict[str, Any]]:
    blogs, _ = await get_site_blog_page(request, tag=tag, limit=limit, include_topics=False)
    return blogs
