import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from catalogued.http import get_catalogued_variants, set_catalogued_variant_favorite
from catalogued.models import CATALOGUED_VARIANT_COLLECTION
from catalogued.repository import (
    _remove_catalogued_variant_favorites,
    _rename_catalogued_variant_favorites,
)
from catalogued.variants import catalogued_variants_for_client
from multidict import MultiDict
from views import add_catalogued_client_docs_context


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
            patch("catalogued.http.get_app_state", return_value=app_state),
            patch(
                "catalogued.http._current_human_username",
                new=AsyncMock(return_value="alice"),
            ),
            patch(
                "catalogued.http.read_json_data",
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


class CataloguedVariantDependencyFavoriteTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        sample = {
            "startFen": "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
            "width": 8,
            "height": 8,
            "pieces": ["k"],
            "visibility": "public",
        }
        self.parent = {**sample, "name": "favorite-parent", "baseVariant": "chess"}
        self.child = {**sample, "name": "favorite-child", "baseVariant": "favorite-parent"}
        self.user = SimpleNamespace(
            username="alice", anon=False, catalogued_variant_favorites={"favorite-parent"}
        )
        self.app_state = SimpleNamespace(
            catalogued_variants={
                "favorite-parent": self.parent,
                "favorite-child": self.child,
            },
            users=FakeUsers(self.user),
        )

    async def test_named_api_preserves_favorite_on_an_inherited_parent(self):
        request = SimpleNamespace(
            app=object(), rel_url=SimpleNamespace(query=MultiDict({"name": "favorite-child"}))
        )
        with (
            patch("catalogued.http.get_app_state", return_value=self.app_state),
            patch("catalogued.http._optional_human_username", AsyncMock(return_value="alice")),
        ):
            response = await get_catalogued_variants(request)

        parent, child = json.loads(response.text)["variants"]
        self.assertEqual(parent["name"], "favorite-parent")
        self.assertTrue(parent["favorite"])
        self.assertEqual(child["name"], "favorite-child")
        self.assertNotIn("favorite", child)

    def test_selective_preloads_preserve_inherited_favorites_per_viewer(self):
        for favorites in ({"favorite-parent"}, set()):
            with self.subTest(favorites=favorites):
                parent, child = catalogued_variants_for_client(
                    self.app_state, "alice", favorite_names=favorites, names={"favorite-child"}
                )
                self.assertEqual(parent.get("favorite", False), bool(favorites))
                self.assertNotIn("favorite", child)
        self.assertNotIn("favorite", self.parent)

    def test_html_context_preserves_favorite_on_an_inherited_parent(self):
        context = {}
        add_catalogued_client_docs_context(self.app_state, self.user, context, [self.child])
        parent, child = json.loads(context["catalogued_variants"])
        self.assertTrue(parent["favorite"])
        self.assertNotIn("favorite", child)
        self.assertNotIn("favorite", self.parent)


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
