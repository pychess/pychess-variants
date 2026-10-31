from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from legacy_blog_migration import stable_post_id
from mongomock_motor import AsyncMongoMockClient
from ublog_post2_migration import MARKER_ID

from scripts.migrate_legacy_blogs_to_ublog import apply_docs, migrate, parse_args, prepare_docs

SOURCE = """<h1 align="center">Yokai Shogi Arrives for Halloween!</h1>
<div class="meta-headline">
<div class="meta">2021.07.30 @CouchTomato87 Announcements</div>
<div class="headline">New variants</div>
</div>
</br>
![Yokai parade](https://github.com/pychess/pychess-variants/blob/master/static/images/Hyakki.jpg)
<br>
Hey everyone, Couch Tomato here!
<img src="https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/YokaiBoard.png" width="336">
"""


class LegacyBlogImportTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "Yokai Halloween.md"
        self.path.write_text(SOURCE, encoding="utf-8")
        self.options = [
            "--markdown-file",
            str(self.path),
            "--author",
            "CouchTomato87",
            "--title",
            "Yokai Shogi Arrives for Halloween!",
            "--intro",
            "New variants",
            "--date",
            "2026-10-31",
            "--image",
            "/images/Hyakki.jpg",
            "--topics",
            "announcement,shogi",
            "--official",
        ]
        self.db = AsyncMongoMockClient(tz_aware=True).test

    def prepare(self, *extra):
        return prepare_docs(parse_args(self.options + list(extra)))[0]

    def test_file_import_preserves_author_and_replaces_preamble(self):
        doc = self.prepare("--publish")
        self.assertEqual(doc["_id"], stable_post_id("Yokai_Halloween"))
        self.assertEqual(doc["legacyBlogId"], "Yokai_Halloween")
        self.assertEqual(doc["author"], "CouchTomato87")
        self.assertEqual(doc["slug"], "yokai-shogi-arrives-for-halloween")
        self.assertEqual(doc["title"], "Yokai Shogi Arrives for Halloween!")
        self.assertEqual(doc["intro"], "New variants")
        self.assertEqual(doc["topics"], ["announcement", "shogi"])
        self.assertTrue(doc["live"])
        self.assertTrue(doc["isOfficial"])
        self.assertEqual(doc["blogType"], "site")
        self.assertEqual(doc["publishedAt"], datetime(2026, 10, 31, tzinfo=UTC))
        self.assertEqual(doc["image"], "/static/images/Hyakki.jpg")
        self.assertNotIn("2021.07.30", doc["markdown"])
        self.assertNotIn("Yokai parade", doc["markdown"])
        self.assertNotIn("<", doc["markdown"])
        self.assertIn("Hey everyone, Couch Tomato here!", doc["markdown"])
        self.assertIn(
            "![](/static/images/YokaiShogiGuide/YokaiBoard.png){width=336}", doc["markdown"]
        )

    def test_draft_is_default_and_id_is_stable(self):
        draft = self.prepare()
        published = self.prepare("--publish")
        self.assertFalse(draft["live"])
        self.assertIsNone(draft["publishedAt"])
        self.assertEqual(draft["_id"], published["_id"])
        self.assertFalse(draft["discuss"])

    def test_community_file_and_explicit_id(self):
        options = self.options.copy()
        options.remove("--official")
        doc = prepare_docs(parse_args(options + ["--blog-id", "custom-id"]))[0]
        self.assertFalse(doc["isOfficial"])
        self.assertEqual(doc["blogType"], "community")
        self.assertEqual(doc["legacyBlogId"], "custom-id")
        self.assertEqual(doc["_id"], stable_post_id("custom-id"))

    def test_exact_catalog_selection_reads_only_selected_file(self):
        selected = {"_id": "Selected", "title": "Selected", "date": "2026-10-31"}
        with (
            patch("scripts.migrate_legacy_blogs_to_ublog.legacy_blogs", return_value=[selected]),
            patch("legacy_blog_migration.markdown_path", return_value=self.path),
        ):
            docs = prepare_docs(parse_args(["--blog-id", "Selected"]))
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["legacyBlogId"], "Selected")
        self.assertNotIn("<img", docs[0]["markdown"])

    def test_unknown_catalog_id_fails(self):
        for option in ("--blog-id", "--from-id"):
            with self.subTest(option=option), self.assertRaisesRegex(ValueError, "Unknown catalog"):
                prepare_docs(parse_args([option, "missing-blog"]))

    def test_invalid_options_are_rejected(self):
        invalid = [
            ["--markdown-file", str(self.path)],
            ["--author", "CouchTomato87"],
            ["--publish"],
            ["--blog-id", "Selected", "--limit", "1"],
            self.options + ["--from-id", "Selected"],
            self.options + ["--author-policy", "official-as-pychess"],
            ["--limit", "-1"],
        ]
        for argv in invalid:
            with (
                self.subTest(argv=argv),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                parse_args(argv)

    def test_invalid_date_or_content_fails(self):
        for extra in (
            ["--date", "not-a-date"],
            ["--image", "https://example.com/unsafe.jpg"],
            ["--title", "x"],
            ["--intro", "x"],
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.prepare(*extra)
        self.path.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "markdown"):
            self.prepare()

    async def test_dry_run_does_not_connect(self):
        with (
            patch("scripts.migrate_legacy_blogs_to_ublog.AsyncMongoClient") as client,
            redirect_stdout(io.StringIO()) as output,
        ):
            await migrate(parse_args(self.options))
        client.assert_not_called()
        self.assertIn("ublog_post2 (dry_run=True)", output.getvalue())
        self.assertIn("author=CouchTomato87", output.getvalue())

    async def test_apply_targets_current_collection_after_startup_migration(self):
        await self.db.user.insert_one({"_id": "CouchTomato87", "enabled": True})
        await self.db.config.insert_one({"_id": MARKER_ID, "status": "complete"})
        doc = self.prepare("--publish")
        self.assertEqual(await apply_docs(self.db, [doc]), (1, 0))
        stored = await self.db.ublog_post2.find_one({"_id": doc["_id"]})
        self.assertEqual(stored, doc)
        self.assertEqual(await self.db.ublog_post.count_documents({}), 0)
        self.assertEqual(await self.db.config.count_documents({}), 1)

    async def test_repeated_import_preserves_existing_post(self):
        await self.db.user.insert_one({"_id": "CouchTomato87"})
        doc = self.prepare()
        await apply_docs(self.db, [doc])
        await self.db.ublog_post2.update_one(
            {"_id": doc["_id"]},
            {"$set": {"markdown": "Edited by author", "likes": ["alice"], "views": 12}},
        )
        before = await self.db.ublog_post2.find_one({"_id": doc["_id"]})
        self.assertEqual(await apply_docs(self.db, [self.prepare("--publish")]), (0, 1))
        self.assertEqual(await self.db.ublog_post2.find_one({"_id": doc["_id"]}), before)

    async def test_invalid_author_prevents_all_writes(self):
        await self.db.user.insert_one({"_id": "CouchTomato87", "enabled": True})
        first = self.prepare()
        for user in (None, {"_id": "missing", "enabled": False}):
            with self.subTest(user=user):
                if user:
                    await self.db.user.insert_one(user)
                invalid = {**first, "_id": "other", "author": "missing"}
                with self.assertRaisesRegex(ValueError, "not an enabled PyChess user"):
                    await apply_docs(self.db, [first, invalid])
                self.assertEqual(await self.db.ublog_post2.count_documents({}), 0)
