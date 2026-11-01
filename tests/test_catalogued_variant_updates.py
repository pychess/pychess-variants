import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from aiohttp import web
from catalogued.variants import (
    _catalogued_rename_source_query,
    _catalogued_same_name_update,
    _rename_catalogued_variant_document,
    _update_catalogued_variant_document,
)


class CataloguedVariantUpdateDocumentTest(unittest.IsolatedAsyncioTestCase):
    def test_same_name_update_preserves_uploads_and_concurrent_fields(self) -> None:
        created_at = datetime.now(UTC)
        existing = {
            "_id": "assetkeeper",
            "pieceNames": {"p": "Pawn"},
            "pieceFamilyOverride": "standard",
            "boardFamilyOverride": "standard8x8",
            "pieceSet": {"wP": {"svg": "<svg />", "size": 7}},
            "pieceSetUpdatedAt": created_at,
            "boardSvg": {"svg": "<svg />", "size": 7},
            "boardSvgUpdatedAt": created_at,
            "gameCount": 4,
            "favoriteCount": 2,
            "aiFailureCount": 2,
            "createdAt": created_at,
        }
        rebuilt = {
            "_id": "assetkeeper",
            "name": "assetkeeper",
            "description": "Updated",
            "pieceSet": existing["pieceSet"],
            "pieceSetUpdatedAt": created_at,
            "boardSvg": existing["boardSvg"],
            "boardSvgUpdatedAt": created_at,
            "gameCount": 4,
            "favoriteCount": 2,
            "aiFailureCount": 2,
            "createdAt": created_at,
        }

        update = _catalogued_same_name_update(rebuilt, existing)

        self.assertEqual(update["$set"]["description"], "Updated")
        for field in (
            "pieceSet",
            "pieceSetUpdatedAt",
            "boardSvg",
            "boardSvgUpdatedAt",
            "gameCount",
            "favoriteCount",
            "aiFailureCount",
            "createdAt",
        ):
            self.assertNotIn(field, update["$set"])
            self.assertNotIn(field, update.get("$unset", {}))
        self.assertEqual(
            update["$unset"],
            {
                "pieceNames": "",
                "pieceFamilyOverride": "",
                "boardFamilyOverride": "",
            },
        )

    async def test_same_name_save_uses_update_and_returns_database_document(self) -> None:
        existing = {"_id": "assetkeeper", "pieceSet": {"wP": {"svg": "<svg />", "size": 7}}}
        rebuilt: Any = {"_id": "assetkeeper", "name": "assetkeeper", "description": "Updated"}
        stored = {**existing, **rebuilt}
        collection = SimpleNamespace(
            update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)),
            find_one=AsyncMock(return_value=stored),
        )

        updated = await _update_catalogued_variant_document(
            collection,
            name="assetkeeper",
            existing=existing,
            doc=rebuilt,
        )

        self.assertIs(updated, stored)
        collection.update_one.assert_awaited_once()
        collection.find_one.assert_awaited_once_with({"_id": "assetkeeper"})


class CataloguedVariantRenameDocumentTest(unittest.IsolatedAsyncioTestCase):
    def test_rename_source_query_matches_asset_and_game_revision(self) -> None:
        updated_at = datetime.now(UTC)

        self.assertEqual(
            _catalogued_rename_source_query(
                "oldname", {"updatedAt": updated_at, "gameCount": 3, "favoriteCount": 2}
            ),
            {
                "_id": "oldname",
                "updatedAt": updated_at,
                "gameCount": 3,
                "favoriteCount": 2,
            },
        )

    async def test_rename_deletes_only_the_revision_that_was_read(self) -> None:
        updated_at = datetime.now(UTC)
        existing = {"_id": "oldname", "updatedAt": updated_at, "gameCount": 0, "favoriteCount": 0}
        doc: Any = {"_id": "newname", "name": "newname"}
        collection = SimpleNamespace(
            insert_one=AsyncMock(),
            delete_one=AsyncMock(return_value=SimpleNamespace(deleted_count=1)),
        )
        name_collection = SimpleNamespace(insert_one=AsyncMock())

        await _rename_catalogued_variant_document(
            collection,
            name_collection,
            old_name="oldname",
            new_name="newname",
            existing=existing,
            doc=doc,
        )

        name_collection.insert_one.assert_awaited_once()
        self.assertEqual(name_collection.insert_one.await_args.args[0]["_id"], "oldname")
        collection.insert_one.assert_awaited_once_with(doc)
        collection.delete_one.assert_awaited_once_with(
            {"_id": "oldname", "updatedAt": updated_at, "gameCount": 0, "favoriteCount": 0}
        )

    async def test_concurrent_change_rolls_back_rename(self) -> None:
        updated_at = datetime.now(UTC)
        existing = {"_id": "oldname", "updatedAt": updated_at, "gameCount": 0, "favoriteCount": 0}
        doc: Any = {"_id": "newname", "name": "newname"}
        collection = SimpleNamespace(
            insert_one=AsyncMock(),
            delete_one=AsyncMock(
                side_effect=[
                    SimpleNamespace(deleted_count=0),
                    SimpleNamespace(deleted_count=1),
                ]
            ),
        )
        name_collection = SimpleNamespace(insert_one=AsyncMock())

        with self.assertRaises(web.HTTPConflict) as exc:
            await _rename_catalogued_variant_document(
                collection,
                name_collection,
                old_name="oldname",
                new_name="newname",
                existing=existing,
                doc=doc,
            )

        self.assertIn("changed while it was being saved", exc.exception.text)
        name_collection.insert_one.assert_awaited_once()
        self.assertEqual(
            collection.delete_one.await_args_list[0].args[0],
            {"_id": "oldname", "updatedAt": updated_at, "gameCount": 0, "favoriteCount": 0},
        )
        self.assertEqual(collection.delete_one.await_args_list[1].args[0], {"_id": "newname"})


if __name__ == "__main__":
    unittest.main()
