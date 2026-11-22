"""One-time, restart-safe copy of legacy blogs into the strict Markdown collection.

The source is deliberately immutable. The completion marker prevents deleted posts
from being reintroduced on subsequent Heroku restarts.
"""

from __future__ import annotations

import logging

from ublog_markdown_migration import convert_legacy_blog_markdown

log = logging.getLogger(__name__)
MARKER_ID = "ublog_post2_migration_v1"


async def migrate_ublog_post2(db) -> int:
    """Migrate once, before requests are served. Safe to resume after interruption."""
    if await db.config.find_one({"_id": MARKER_ID}):
        return 0

    count = 0
    async for original in db.ublog_post.find({}):
        converted = dict(original)
        converted["markdown"] = convert_legacy_blog_markdown(original.get("markdown") or "")
        # Never overwrite an existing target document (even if a restart interrupted us).
        result = await db.ublog_post2.update_one(
            {"_id": converted["_id"]}, {"$setOnInsert": converted}, upsert=True
        )
        count += result.upserted_id is not None

    # Do not declare success unless all source IDs exist in the destination.
    async for original in db.ublog_post.find({}, {"_id": 1}):
        if not await db.ublog_post2.find_one({"_id": original["_id"]}, {"_id": 1}):
            raise RuntimeError("Blog migration incomplete; refusing to start")

    await db.config.update_one(
        {"_id": MARKER_ID}, {"$setOnInsert": {"status": "complete"}}, upsert=True
    )
    log.info("[startup] blog migration complete: %s posts copied to ublog_post2", count)
    return count
