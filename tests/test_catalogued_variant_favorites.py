import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from catalogued.variants import (
    CATALOGUED_VARIANT_COLLECTION,
    _remove_catalogued_variant_favorites,
    _rename_catalogued_variant_favorites,
    set_catalogued_variant_favorite,
)


class FakeUsers:
    def __init__(self, user, cached_users=None):
        self.user = user
        self.cached_users = list(cached_users or [user])

    async def get(self, _username):
        return self.user

    def values(self):
        return self.cached_users


class FakeDatabase:
    def __init__(self, variant_collection, user_collection):
        self.variant_collection = variant_collection
        self.user = user_collection

    def __getitem__(self, name):
        if name == CATALOGUED_VARIANT_COLLECTION:
            return self.variant_collection
        raise KeyError(name)


class CataloguedVariantFavoriteTestCase(unittest.IsolatedAsyncioTestCase):
    async def call_handler(
        self, *, favorite, favorites, modified_count, stored_count, updated_count=None
    ):
        user = SimpleNamespace(catalogued_variant_favorites=set(favorites))
        user_collection = SimpleNamespace(
            update_one=AsyncMock(return_value=SimpleNamespace(modified_count=modified_count))
        )
        variant_collection = SimpleNamespace(
            find_one=AsyncMock(return_value={"_id": "variant", "favoriteCount": stored_count}),
            find_one_and_update=AsyncMock(
                return_value=(None if updated_count is None else {"favoriteCount": updated_count})
            ),
        )
        app_state = SimpleNamespace(
            db=FakeDatabase(variant_collection, user_collection),
            users=FakeUsers(user),
            catalogued_variants={"variant": {"favoriteCount": stored_count}},
        )
        request = SimpleNamespace(app=object(), match_info={"name": "variant"})

        with (
            patch("catalogued.variants.get_app_state", return_value=app_state),
            patch(
                "catalogued.variants._current_human_username",
                new=AsyncMock(return_value="alice"),
            ),
            patch(
                "catalogued.variants.read_json_data",
                new=AsyncMock(return_value={"favorite": favorite}),
            ),
        ):
            response = await set_catalogued_variant_favorite(request)

        return json.loads(response.text), app_state, user_collection, variant_collection

    async def test_first_favorite_increments_global_count_once(self):
        payload, app_state, user_collection, variant_collection = await self.call_handler(
            favorite=True,
            favorites=set(),
            modified_count=1,
            stored_count=3,
            updated_count=4,
        )

        self.assertTrue(payload["favorite"])
        self.assertEqual(payload["favoriteCount"], 4)
        self.assertEqual(app_state.users.user.catalogued_variant_favorites, {"variant"})
        self.assertEqual(app_state.catalogued_variants["variant"]["favoriteCount"], 4)
        user_collection.update_one.assert_awaited_once_with(
            {"_id": "alice"}, {"$addToSet": {"cvf": "variant"}}
        )
        variant_collection.find_one_and_update.assert_awaited_once()

    async def test_repeated_favorite_does_not_increment_global_count(self):
        payload, app_state, _user_collection, variant_collection = await self.call_handler(
            favorite=True,
            favorites={"variant"},
            modified_count=0,
            stored_count=4,
        )

        self.assertTrue(payload["favorite"])
        self.assertEqual(payload["favoriteCount"], 4)
        self.assertEqual(app_state.users.user.catalogued_variant_favorites, {"variant"})
        variant_collection.find_one_and_update.assert_not_awaited()

    async def test_unfavorite_uses_non_negative_atomic_counter_update(self):
        payload, app_state, _user_collection, variant_collection = await self.call_handler(
            favorite=False,
            favorites={"variant"},
            modified_count=1,
            stored_count=0,
            updated_count=0,
        )

        self.assertFalse(payload["favorite"])
        self.assertEqual(payload["favoriteCount"], 0)
        self.assertEqual(app_state.users.user.catalogued_variant_favorites, set())
        update = variant_collection.find_one_and_update.await_args.args[1]
        self.assertEqual(update[0]["$set"]["favoriteCount"]["$max"][0], 0)


class CataloguedVariantFavoriteCleanupTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_rename_migrates_database_and_cached_favorites(self):
        cached_favorite = SimpleNamespace(catalogued_variant_favorites={"oldname", "other"})
        cached_other = SimpleNamespace(catalogued_variant_favorites={"other"})
        user_collection = SimpleNamespace(update_many=AsyncMock())
        app_state = SimpleNamespace(
            db=SimpleNamespace(user=user_collection),
            users=FakeUsers(cached_favorite, [cached_favorite, cached_other]),
        )

        await _rename_catalogued_variant_favorites(app_state, "oldname", "newname")

        self.assertEqual(cached_favorite.catalogued_variant_favorites, {"newname", "other"})
        self.assertEqual(cached_other.catalogued_variant_favorites, {"other"})
        user_collection.update_many.assert_awaited_once()
        self.assertEqual(user_collection.update_many.await_args.args[0], {"cvf": "oldname"})
        update = user_collection.update_many.await_args.args[1]
        self.assertIn("$setUnion", update[0]["$set"]["cvf"])

    async def test_delete_removes_database_and_cached_favorites(self):
        cached = SimpleNamespace(catalogued_variant_favorites={"oldname", "other"})
        user_collection = SimpleNamespace(update_many=AsyncMock())
        app_state = SimpleNamespace(
            db=SimpleNamespace(user=user_collection),
            users=FakeUsers(cached),
        )

        await _remove_catalogued_variant_favorites(app_state, "oldname")

        self.assertEqual(cached.catalogued_variant_favorites, {"other"})
        user_collection.update_many.assert_awaited_once_with(
            {"cvf": "oldname"}, {"$pull": {"cvf": "oldname"}}
        )


if __name__ == "__main__":
    unittest.main()
