"""One-time blog collection migration safety checks."""

import unittest

from mongomock_motor import AsyncMongoMockClient
from ublog_post2_migration import MARKER_ID, migrate_ublog_post2


class UblogPost2MigrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMongoMockClient().test

    async def test_conversion_preserves_source_and_metadata(self):
        original = {
            "_id": "a",
            "author": "alice",
            "likes": ["bob"],
            "live": True,
            "markdown": '<img src="/static/images/diagram.svg" width="336">',
        }
        await self.db.ublog_post.insert_one(original)
        self.assertEqual(await migrate_ublog_post2(self.db), 1)
        migrated = await self.db.ublog_post2.find_one({"_id": "a"})
        self.assertEqual(migrated["markdown"], "![](/static/images/diagram.svg){width=336}\n")
        self.assertEqual(migrated["likes"], ["bob"])
        self.assertEqual(
            (await self.db.ublog_post.find_one({"_id": "a"}))["markdown"], original["markdown"]
        )
        self.assertIsNotNone(await self.db.config.find_one({"_id": MARKER_ID}))

    async def test_deleted_post_is_not_resurrected(self):
        await self.db.ublog_post.insert_one({"_id": "a", "markdown": "Hello"})
        await migrate_ublog_post2(self.db)
        await self.db.ublog_post2.delete_one({"_id": "a"})
        self.assertEqual(await migrate_ublog_post2(self.db), 0)
        self.assertIsNone(await self.db.ublog_post2.find_one({"_id": "a"}))

    async def test_interrupted_copy_resumes_without_overwriting(self):
        await self.db.ublog_post.insert_many(
            [
                {"_id": "a", "markdown": "original"},
                {"_id": "b", "markdown": "new"},
            ]
        )
        await self.db.ublog_post2.insert_one({"_id": "a", "markdown": "already copied"})
        self.assertEqual(await migrate_ublog_post2(self.db), 1)
        self.assertEqual(
            (await self.db.ublog_post2.find_one({"_id": "a"}))["markdown"], "already copied"
        )
        self.assertEqual((await self.db.ublog_post2.find_one({"_id": "b"}))["markdown"], "new\n")
