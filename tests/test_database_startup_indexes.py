from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from database.schema import INDEXES, OBSOLETE_INDEXES
from database.startup import (
    StartupMode,
    drop_obsolete_indexes,
    ensure_indexes,
    prepare_database_schema,
)
from mongomock_motor import AsyncMongoMockClient


class ObsoleteIndexCleanupTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_old_public_study_search_index_is_replaced_by_full_index(self) -> None:
        db = AsyncMongoMockClient().test
        await db.create_collection("study")
        await db.study.create_index(
            [("searchTokens", 1), ("updatedAt", -1), ("_id", 1)],
            name="public_searchTokens_updatedAt",
            partialFilterExpression={"visibility": "public"},
        )
        current = next(
            spec
            for spec in INDEXES
            if spec.collection == "study" and spec.name == "searchTokens_updatedAt"
        )

        dropped = await drop_obsolete_indexes(db, OBSOLETE_INDEXES)
        created = await ensure_indexes(db, (current,))

        self.assertEqual(dropped, ("study.public_searchTokens_updatedAt",))
        self.assertEqual([result.created_name for result in created], ["searchTokens_updatedAt"])
        indexes = await db.study.index_information()
        self.assertNotIn("public_searchTokens_updatedAt", indexes)
        self.assertNotIn("partialFilterExpression", indexes["searchTokens_updatedAt"])

    async def test_unexpected_definition_is_not_dropped(self) -> None:
        db = AsyncMongoMockClient().test
        await db.create_collection("study")
        await db.study.create_index(
            [("searchTokens", 1), ("updatedAt", -1), ("_id", 1)],
            name="public_searchTokens_updatedAt",
            partialFilterExpression={"visibility": "private"},
        )

        dropped = await drop_obsolete_indexes(db, OBSOLETE_INDEXES)

        self.assertEqual(dropped, ())
        indexes = await db.study.index_information()
        self.assertIn("public_searchTokens_updatedAt", indexes)


class NotificationRetentionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_database_uses_28_day_notification_ttl(self) -> None:
        db = AsyncMongoMockClient().test

        result = await prepare_database_schema(db, local_development=False)

        self.assertEqual(result.mode, StartupMode.FRESH)
        indexes = await db.notify.index_information()
        self.assertEqual(indexes["createdAt_1"]["key"], [("createdAt", 1)])
        self.assertEqual(indexes["createdAt_1"]["expireAfterSeconds"], 28 * 24 * 60 * 60)
        self.assertNotIn("expireAt_1", indexes)

    async def test_production_startup_expires_legacy_notifications_and_is_idempotent(self) -> None:
        db = AsyncMongoMockClient(tz_aware=True).test
        await db.notify.create_index("expireAt", expireAfterSeconds=0)
        now = datetime.now(UTC)
        documents = [
            {
                "_id": f"{age_days}-{read}-{has_expiry}",
                "notifies": "alice",
                "type": "corrMove",
                "createdAt": now - timedelta(days=age_days),
                "read": read,
                **({"expireAt": "2099-01-01T00:00:00+00:00"} if has_expiry else {}),
            }
            for age_days in (27, 29, 365)
            for read in (False, True)
            for has_expiry in (False, True)
        ]
        await db.notify.insert_many(documents)
        self.assertEqual(await db.notify.count_documents({}), len(documents))

        result = await prepare_database_schema(db, local_development=False)

        self.assertEqual(result.mode, StartupMode.PRODUCTION)
        self.assertIn("notify.expireAt_1", result.dropped_indexes)
        self.assertIn(
            "createdAt_1",
            [
                item.created_name
                for item in result.created_indexes
                if item.spec.collection == "notify"
            ],
        )
        indexes = await db.notify.index_information()
        self.assertNotIn("expireAt_1", indexes)
        self.assertIn("notifies_1", indexes)
        self.assertIn("content.arr_1", indexes)
        remaining_ids = {doc["_id"] async for doc in db.notify.find({})}
        self.assertEqual(
            remaining_ids,
            {doc["_id"] for doc in documents if doc["createdAt"] > now - timedelta(days=28)},
        )

        repeated = await prepare_database_schema(db, local_development=False)
        self.assertEqual(repeated.dropped_indexes, ())
        self.assertEqual(repeated.created_indexes, ())

    async def test_custom_legacy_expiry_definition_is_preserved(self) -> None:
        db = AsyncMongoMockClient().test
        await db.notify.create_index("expireAt", expireAfterSeconds=3600)

        await prepare_database_schema(db, local_development=False)

        indexes = await db.notify.index_information()
        self.assertEqual(indexes["expireAt_1"]["expireAfterSeconds"], 3600)
        self.assertEqual(indexes["createdAt_1"]["expireAfterSeconds"], 28 * 24 * 60 * 60)


if __name__ == "__main__":
    unittest.main()
