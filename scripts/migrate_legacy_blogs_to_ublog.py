from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from legacy_blog_catalog import legacy_blogs
from legacy_blog_migration import build_legacy_ublog_docs, to_ublog_doc
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from settings import MONGO_DB_NAME, MONGO_HOST
from ublog import (
    UBLOG_MAX_IMAGE_TEXT_LEN,
    UBLOG_MAX_INTRO_LEN,
    UBLOG_MAX_MARKDOWN_LEN,
    UBLOG_MAX_TITLE_LEN,
    normalize_topics,
    post_url,
    sanitize_image_url,
)
from ublog_markdown_migration import convert_legacy_blog_markdown


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import legacy site blogs or a single Markdown file into ublog_post2. "
            "Existing posts are skipped. Run with PYTHONPATH=server."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to MongoDB. Default behavior is dry-run.",
    )
    mode.add_argument(
        "--dry-run", action="store_true", help="Preview without connecting to MongoDB (default)."
    )
    parser.add_argument("--mongo-host", default=MONGO_HOST, help="Mongo URI (default: MONGO_HOST).")
    parser.add_argument("--mongo-db", default=MONGO_DB_NAME, help="Mongo database name.")
    parser.add_argument(
        "--author-policy",
        choices=("keep", "official-as-pychess"),
        default="keep",
        help="Author policy for catalog imports; single-file imports always keep --author.",
    )
    parser.add_argument("--limit", type=int, default=0, help="First N catalog posts (0 means all).")
    parser.add_argument("--from-id", default="", help="Start at this catalog blog ID (inclusive).")
    parser.add_argument(
        "--blog-id",
        default="",
        help="Import exactly this catalog ID, or override the ID derived from --markdown-file.",
    )
    parser.add_argument(
        "--keep-legacy-preamble", action="store_true", help="Keep inline title/meta/hero blocks."
    )
    parser.add_argument(
        "--markdown-file", type=Path, help="Import a local file, even if absent from the catalog."
    )
    parser.add_argument("--author", help="Existing PyChess username for a single-file import.")
    parser.add_argument("--title", help="Title for a single-file import.")
    parser.add_argument("--intro", help="Short introduction for a single-file import.")
    parser.add_argument(
        "--date", help="Explicit post date (YYYY-MM-DD); ignores inline legacy dates."
    )
    parser.add_argument("--image", help="Cover image URL or /static/images/... path.")
    parser.add_argument("--image-alt", help="Cover image description.")
    parser.add_argument("--topics", help="Comma-separated blog topics, e.g. announcement,shogi.")
    parser.add_argument("--official", action="store_true", help="Import the file as a site blog.")
    parser.add_argument(
        "--sticky", action="store_true", help="Pin the file above unpinned posts in blog listings."
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the file immediately; otherwise create a draft.",
    )
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit cannot be negative")
    if (args.markdown_file or args.blog_id) and (args.from_id or args.limit):
        parser.error("--from-id/--limit cannot be combined with --markdown-file or --blog-id")
    if args.markdown_file:
        for name in ("author", "title", "intro", "date"):
            value = getattr(args, name)
            if not value or not value.strip():
                parser.error(f"--{name} is required with --markdown-file")
        if args.author_policy != "keep":
            parser.error("--author-policy only applies to catalog imports")
    elif (
        any(
            getattr(args, name) is not None
            for name in ("author", "title", "intro", "date", "image", "image_alt", "topics")
        )
        or args.official
        or args.sticky
        or args.publish
    ):
        parser.error("Author/content/publishing options require --markdown-file")
    return args


def prepare_docs(args: argparse.Namespace) -> list[dict[str, Any]]:
    strip_preamble = not args.keep_legacy_preamble
    if args.markdown_file:
        legacy_id = args.blog_id or args.markdown_file.stem.replace(" ", "_")
        legacy = {
            "_id": legacy_id,
            "author": args.author.strip(),
            "title": args.title.strip(),
            "intro": args.intro.strip(),
            "date": args.date,
            "image": args.image or "",
            "imageAlt": args.image_alt or "",
            "tags": ["Announcement"] if args.official else [],
        }
        doc = to_ublog_doc(
            legacy,
            "keep",
            strip_preamble,
            markdown=args.markdown_file.read_text(encoding="utf-8"),
        )
        doc["topics"] = normalize_topics(args.topics or "")
        doc["live"] = args.publish
        doc["sticky"] = args.sticky
        if not args.publish:
            doc["publishedAt"] = None
        for field, minimum, maximum in (
            ("title", 3, UBLOG_MAX_TITLE_LEN),
            ("intro", 3, UBLOG_MAX_INTRO_LEN),
            ("markdown", 3, UBLOG_MAX_MARKDOWN_LEN),
            ("imageAlt", 0, UBLOG_MAX_IMAGE_TEXT_LEN),
        ):
            if not minimum <= len(doc[field]) <= maximum:
                raise ValueError(f"{field} must contain {minimum}–{maximum} characters")
        if doc["image"]:
            image = sanitize_image_url(doc["image"])
            if image is None:
                raise ValueError("Invalid cover image URL")
            doc["image"] = image
        docs = [doc]
    elif args.blog_id:
        matches = [blog for blog in legacy_blogs() if blog.get("_id") == args.blog_id]
        if not matches:
            raise ValueError(f"Unknown catalog blog ID: {args.blog_id!r}; use --markdown-file")
        docs = [to_ublog_doc(matches[0], args.author_policy, strip_preamble)]
    else:
        if args.from_id and not any(blog.get("_id") == args.from_id for blog in legacy_blogs()):
            raise ValueError(f"Unknown catalog blog ID: {args.from_id!r}")
        docs = build_legacy_ublog_docs(
            author_policy=args.author_policy,
            strip_preamble=strip_preamble,
            from_id=args.from_id,
            limit=args.limit,
        )
    for doc in docs:
        doc["markdown"] = convert_legacy_blog_markdown(doc["markdown"])
    return docs


async def apply_docs(db: Any, docs: list[dict[str, Any]]) -> tuple[int, int]:
    # Validate all authors before writing anything; ownership uses the exact username.
    for author in sorted({doc["author"] for doc in docs}):
        user = await db.user.find_one({"_id": author})
        if user is None or not user.get("enabled", True):
            raise ValueError(f"Author {author!r} is not an enabled PyChess user")

    inserted = 0
    for doc in docs:
        result = await db.ublog_post2.update_one(
            {"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True
        )
        inserted += result.upserted_id is not None
    return inserted, len(docs) - inserted


async def migrate(args: argparse.Namespace) -> None:
    docs = prepare_docs(args)
    print(
        f"Prepared {len(docs)} posts for {args.mongo_db}.ublog_post2 (dry_run={not args.apply})",
        flush=True,
    )
    for doc in docs:
        print(
            f"- {doc['legacyBlogId']} -> {doc['_id']} author={doc['author']} "
            f"official={doc['isOfficial']} live={doc['live']} sticky={doc['sticky']} "
            f"date={doc['createdAt'].date()} "
            f"title={doc['title']!r} image={doc['image']!r} "
            f"markdown_len={len(doc['markdown'])}\n  {post_url(doc)}",
            flush=True,
        )

    if not args.apply:
        return

    client = AsyncMongoClient(
        args.mongo_host,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
    )
    try:
        db = client[args.mongo_db]
        await db.command("ping")
        inserted, skipped = await apply_docs(db, docs)
        print(f"Applied migration: inserted={inserted}, skipped_existing={skipped}", flush=True)
    finally:
        await client.close()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(migrate(args))
    except (OSError, ValueError, PyMongoError) as exc:
        raise SystemExit(f"Migration failed: {exc}") from exc


if __name__ == "__main__":
    main()
