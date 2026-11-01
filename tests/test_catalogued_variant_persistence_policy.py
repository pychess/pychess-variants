import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from catalogued.variants import (
    _client_doc,
    _has_active_catalogued_games,
    _remove_legacy_catalogued_icon_fields,
    archive_catalogued_variant,
    catalogued_variant_client_doc_for_game,
    catalogued_variant_games_are_persisted,
    delete_catalogued_variant,
    ensure_catalogued_variant_from_game_doc,
    find_catalogued_variant_doc,
    restore_catalogued_variant,
)
from const import ABORTED, STARTED
from mongomock_motor import AsyncMongoMockClient
from variants import (
    CATALOGUED_VARIANT_ICON,
    is_catalogued_variant,
    register_catalogued_server_variant,
    unregister_catalogued_server_variant,
)


class CataloguedVariantIconPolicyTest(unittest.TestCase):
    def test_client_metadata_does_not_expose_legacy_stored_icon(self) -> None:
        client_doc = _client_doc(
            {
                "name": "legacy_icon_test",
                "displayName": "Legacy icon test",
                "ini": "[legacy_icon_test:chess]\n",
                "startFen": "8/8/8/8/8/8/8/K6k w - - 0 1",
                "width": 8,
                "height": 8,
                "pieces": ["k"],
                "icon": "◇",
            }
        )

        self.assertNotIn("icon", client_doc)

    def test_runtime_registration_uses_code_defined_icon(self) -> None:
        name = "runtime_icon_test"
        unregister_catalogued_server_variant(name)
        self.addCleanup(unregister_catalogued_server_variant, name)

        variant = register_catalogued_server_variant(name, "Runtime icon test")

        self.assertEqual(variant.icon, CATALOGUED_VARIANT_ICON)


class CataloguedVariantLegacyIconMigrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_removes_persisted_icon_fields(self) -> None:
        collection = SimpleNamespace(
            update_many=AsyncMock(return_value=SimpleNamespace(modified_count=2))
        )

        await _remove_legacy_catalogued_icon_fields(collection)

        collection.update_many.assert_awaited_once_with(
            {"icon": {"$exists": True}},
            {"$unset": {"icon": ""}},
        )


class CataloguedVariantPersistencePolicyTest(unittest.TestCase):
    def test_only_public_catalogued_variants_persist_new_games(self) -> None:
        app_state = SimpleNamespace(
            catalogued_variants={
                "private_test": {"visibility": "private"},
                "unlisted_test": {"visibility": "unlisted"},
                "public_test": {"visibility": "public"},
            }
        )

        self.assertFalse(catalogued_variant_games_are_persisted(app_state, "private_test"))
        self.assertFalse(catalogued_variant_games_are_persisted(app_state, "unlisted_test"))
        self.assertTrue(catalogued_variant_games_are_persisted(app_state, "public_test"))

    def test_unknown_catalogued_variant_preserves_old_persistence_behaviour(self) -> None:
        app_state = SimpleNamespace(catalogued_variants={})

        self.assertTrue(catalogued_variant_games_are_persisted(app_state, "missing_variant"))

    def test_active_game_guard_ignores_finished_games(self) -> None:
        app_state = SimpleNamespace(
            games={
                "active": SimpleNamespace(variant="sandbox", status=STARTED),
                "finished": SimpleNamespace(variant="sandbox", status=ABORTED),
                "other": SimpleNamespace(variant="other", status=STARTED),
            }
        )

        self.assertTrue(_has_active_catalogued_games(app_state, "sandbox"))
        app_state.games["active"].status = ABORTED
        self.assertFalse(_has_active_catalogued_games(app_state, "sandbox"))


class CataloguedVariantGameClientDocumentTest(unittest.IsolatedAsyncioTestCase):
    def make_game(self, name: str):
        server_variant = register_catalogued_server_variant(name, name)
        self.addCleanup(unregister_catalogued_server_variant, name)
        return SimpleNamespace(
            id="game-id",
            variant=name,
            server_variant=server_variant,
            wplayer=SimpleNamespace(username="author"),
            bplayer=SimpleNamespace(username="participant"),
        )

    async def test_participant_receives_non_public_variant_from_memory(self) -> None:
        name = "participant_private_test"
        game = self.make_game(name)
        doc = {"name": name, "visibility": "private"}
        app_state = SimpleNamespace(catalogued_variants={name: doc}, db=None)

        with patch("catalogued.variants._client_doc", return_value={"name": name}) as client_doc:
            result = await catalogued_variant_client_doc_for_game(app_state, game, "participant")

        self.assertEqual(result, {"name": name})
        client_doc.assert_called_once_with(doc)

    async def test_participant_receives_archived_variant_from_database(self) -> None:
        name = "participant_archived_test"
        game = self.make_game(name)
        doc = {"name": name, "archived": True, "enabled": False}
        collection = SimpleNamespace(find_one=AsyncMock(return_value=doc))
        app_state = SimpleNamespace(
            catalogued_variants={},
            db={"catalogued_variant": collection},
        )

        with patch("catalogued.variants._client_doc", return_value={"name": name}):
            result = await catalogued_variant_client_doc_for_game(app_state, game, "participant")

        self.assertEqual(result, {"name": name})
        collection.find_one.assert_awaited_once_with({"_id": name})

    async def test_non_participant_cannot_receive_game_variant_metadata(self) -> None:
        name = "non_participant_test"
        game = self.make_game(name)
        collection = SimpleNamespace(find_one=AsyncMock())
        app_state = SimpleNamespace(
            catalogued_variants={},
            db={"catalogued_variant": collection},
        )

        result = await catalogued_variant_client_doc_for_game(app_state, game, "stranger")

        self.assertIsNone(result)
        collection.find_one.assert_not_awaited()

    async def test_active_game_participant_can_open_archived_assets_and_rules(self) -> None:
        name = "participant_archived_assets_test"
        game = self.make_game(name)
        game.status = STARTED
        doc = {"name": name, "archived": True, "enabled": False}
        collection = SimpleNamespace(find_one=AsyncMock(return_value=doc))
        app_state = SimpleNamespace(
            games={game.id: game},
            catalogued_variants={},
            db={"catalogued_variant": collection},
        )

        result = await find_catalogued_variant_doc(app_state, name, "participant")

        self.assertIs(result, doc)
        collection.find_one.assert_awaited_once_with({"_id": name})

    async def test_archived_assets_remain_hidden_from_non_participants(self) -> None:
        name = "non_participant_archived_assets_test"
        game = self.make_game(name)
        game.status = STARTED
        doc = {"name": name, "archived": True, "enabled": False}
        collection = SimpleNamespace(find_one=AsyncMock(return_value=doc))
        app_state = SimpleNamespace(
            games={game.id: game},
            catalogued_variants={},
            db={"catalogued_variant": collection},
        )

        result = await find_catalogued_variant_doc(app_state, name, "stranger")

        self.assertIsNone(result)


class CataloguedVariantArchiveActiveGameTest(unittest.IsolatedAsyncioTestCase):
    async def test_delete_removes_live_and_persisted_seeks_for_variant(self) -> None:
        class DbStub(dict):
            seek: object

        name = "deleted_seek_variant_test"
        doc = {"_id": name, "name": name, "author": "author"}
        variant_collection = SimpleNamespace(delete_one=AsyncMock())
        name_collection = SimpleNamespace(insert_one=AsyncMock())
        seek_collection = SimpleNamespace(delete_many=AsyncMock())
        db = DbStub(
            {
                "catalogued_variant": variant_collection,
                "catalogued_variant_name": name_collection,
            }
        )
        db.seek = seek_collection

        creator = SimpleNamespace(seeks={})
        seek = SimpleNamespace(
            id="seek-id",
            variant=name,
            creator=creator,
            game_id="invite-game-id",
        )
        creator.seeks[seek.id] = seek
        lobby = SimpleNamespace(lobby_broadcast_seeks=AsyncMock())
        app_state = SimpleNamespace(
            db=db,
            games={},
            catalogued_variants={name: doc},
            seeks={seek.id: seek},
            invites={seek.game_id: seek},
            lobby=lobby,
        )
        request = SimpleNamespace()

        register_catalogued_server_variant(name, "Deleted seek variant test")
        self.addCleanup(unregister_catalogued_server_variant, name)

        with (
            patch(
                "catalogued.variants._load_owned_doc",
                AsyncMock(return_value=(app_state, "author", name, doc)),
            ),
            patch("catalogued.variants._has_games", AsyncMock(return_value=False)),
        ):
            response = await delete_catalogued_variant(request)

        self.assertEqual(response.status, 200)
        self.assertNotIn(seek.id, app_state.seeks)
        self.assertNotIn(seek.id, creator.seeks)
        self.assertNotIn(seek.game_id, app_state.invites)
        seek_collection.delete_many.assert_awaited_once_with({"variant": name})
        lobby.lobby_broadcast_seeks.assert_awaited_once()

    async def test_delete_removes_empty_tournament_for_variant(self) -> None:
        name = "deleted_empty_tournament_variant_test"
        doc = {"_id": name, "name": name, "author": "author"}
        db = AsyncMongoMockClient(tz_aware=True).db
        await db.tournament.insert_one(
            {"_id": "empty-tournament-id", "v": name, "nbPlayers": 0, "nbGames": 0}
        )
        app_state = SimpleNamespace(
            db=db,
            games={},
            catalogued_variants={name: doc},
            seeks={},
            invites={},
            tournaments={},
        )
        request = SimpleNamespace()

        with (
            patch(
                "catalogued.variants._load_owned_doc",
                AsyncMock(return_value=(app_state, "author", name, doc)),
            ),
            patch("catalogued.variants._has_games", AsyncMock(return_value=False)),
        ):
            response = await delete_catalogued_variant(request)

        self.assertEqual(response.status, 200)
        self.assertIsNone(await db.tournament.find_one({"_id": "empty-tournament-id"}))

    async def test_delete_rejects_variant_used_by_nonempty_tournament(self) -> None:
        name = "deleted_tournament_variant_test"
        doc = {"_id": name, "name": name, "author": "author"}
        db = AsyncMongoMockClient(tz_aware=True).db
        await db.tournament.insert_one(
            {"_id": "tournament-id", "v": name, "nbPlayers": 1, "nbGames": 0}
        )
        app_state = SimpleNamespace(
            db=db,
            games={},
            catalogued_variants={name: doc},
            seeks={},
            invites={},
        )
        request = SimpleNamespace()

        with (
            patch(
                "catalogued.variants._load_owned_doc",
                AsyncMock(return_value=(app_state, "author", name, doc)),
            ),
            patch("catalogued.variants._has_games", AsyncMock(return_value=False)),
            self.assertRaises(Exception) as raised,
        ):
            await delete_catalogued_variant(request)

        self.assertIn("Archive it instead", getattr(raised.exception, "text", ""))
        self.assertIsNone(await db.catalogued_variant_name.find_one({"_id": name}))
        self.assertIsNotNone(await db.tournament.find_one({"_id": "tournament-id"}))

    async def test_delete_permanently_reserves_internal_name(self) -> None:
        name = "deleted_name_test"
        doc = {"_id": name, "name": name, "author": "author"}
        variant_collection = SimpleNamespace(delete_one=AsyncMock())
        name_collection = SimpleNamespace(insert_one=AsyncMock())
        app_state = SimpleNamespace(
            db={
                "catalogued_variant": variant_collection,
                "catalogued_variant_name": name_collection,
            },
            games={},
            catalogued_variants={name: doc},
        )
        request = SimpleNamespace()

        with (
            patch(
                "catalogued.variants._load_owned_doc",
                AsyncMock(return_value=(app_state, "author", name, doc)),
            ),
            patch("catalogued.variants._has_games", AsyncMock(return_value=False)),
        ):
            response = await delete_catalogued_variant(request)

        self.assertEqual(response.status, 200)
        name_collection.insert_one.assert_awaited_once()
        reservation = name_collection.insert_one.await_args.args[0]
        self.assertEqual(reservation["_id"], name)
        self.assertEqual(reservation["author"], "author")
        variant_collection.delete_one.assert_awaited_once_with({"_id": name})

    async def test_archive_keeps_active_game_but_unregisters_new_game_entry(self) -> None:
        name = "archive_active_game_test"
        active_game = SimpleNamespace(variant=name, status=STARTED)
        collection = SimpleNamespace(update_one=AsyncMock())
        app_state = SimpleNamespace(
            db={"catalogued_variant": collection},
            games={"game-id": active_game},
            catalogued_variants={name: {"name": name, "visibility": "public"}},
        )
        request = SimpleNamespace()

        register_catalogued_server_variant(name, "Archive active game test")
        self.addCleanup(unregister_catalogued_server_variant, name)

        with patch(
            "catalogued.variants._load_owned_doc",
            AsyncMock(
                return_value=(app_state, "author", name, app_state.catalogued_variants[name])
            ),
        ):
            response = await archive_catalogued_variant(request)

        self.assertEqual(response.status, 200)
        collection.update_one.assert_awaited_once()
        self.assertIs(app_state.games["game-id"], active_game)
        self.assertEqual(active_game.status, STARTED)
        self.assertNotIn(name, app_state.catalogued_variants)
        self.assertFalse(is_catalogued_variant(name))

    async def test_archive_snapshots_tournament_variant_rules(self) -> None:
        name = "archive_tournament_snapshot_test"
        ini = f"[{name}:chess]\n"
        doc = {
            "_id": name,
            "name": name,
            "displayName": "Archive tournament snapshot",
            "author": "author",
            "ini": ini,
            "visibility": "public",
        }
        db = AsyncMongoMockClient(tz_aware=True).db
        await db.tournament.insert_one({"_id": "tournament-id", "v": name})
        app_state = SimpleNamespace(
            db=db,
            games={},
            catalogued_variants={name: doc},
            seeks={},
            invites={},
        )
        request = SimpleNamespace()

        register_catalogued_server_variant(name, "Archive tournament snapshot")
        self.addCleanup(unregister_catalogued_server_variant, name)

        with patch(
            "catalogued.variants._load_owned_doc",
            AsyncMock(return_value=(app_state, "author", name, doc)),
        ):
            response = await archive_catalogued_variant(request)

        self.assertEqual(response.status, 200)
        tournament_doc = await db.tournament.find_one({"_id": "tournament-id"})
        self.assertEqual(tournament_doc["vini"], ini)
        self.assertEqual(tournament_doc["vd"], "Archive tournament snapshot")
        self.assertEqual(tournament_doc["vby"], "author")

    async def test_restore_checks_quota_before_reactivating_archived_variant(self) -> None:
        name = "restore_quota_test"
        doc = {
            "name": name,
            "displayName": "Restore quota test",
            "author": "author",
            "archived": True,
            "enabled": False,
        }
        collection = SimpleNamespace(update_one=AsyncMock())
        app_state = SimpleNamespace(db={"catalogued_variant": collection}, catalogued_variants={})
        request = SimpleNamespace()

        with (
            patch(
                "catalogued.variants._load_owned_doc",
                AsyncMock(return_value=(app_state, "author", name, doc)),
            ),
            patch(
                "catalogued.variants._ensure_catalogued_variant_quota",
                AsyncMock(side_effect=Exception("quota checked")),
            ) as ensure_quota,
            self.assertRaisesRegex(Exception, "quota checked"),
        ):
            await restore_catalogued_variant(request)

        ensure_quota.assert_awaited_once_with(app_state, "author")
        collection.update_one.assert_not_awaited()

    async def test_restore_does_not_recheck_quota_for_already_active_variant(self) -> None:
        name = "restore_active_test"
        doc = {
            "name": name,
            "displayName": "Restore active test",
            "author": "author",
            "archived": False,
            "enabled": True,
        }
        collection = SimpleNamespace(update_one=AsyncMock())
        app_state = SimpleNamespace(db={"catalogued_variant": collection}, catalogued_variants={})
        request = SimpleNamespace()

        with (
            patch(
                "catalogued.variants._load_owned_doc",
                AsyncMock(return_value=(app_state, "author", name, doc)),
            ),
            patch(
                "catalogued.variants._ensure_catalogued_variant_quota",
                new=AsyncMock(),
            ) as ensure_quota,
            patch("catalogued.variants.register_catalogued_variant_doc"),
            patch("catalogued.variants._game_count", new=AsyncMock(return_value=0)),
            patch(
                "catalogued.variants._client_doc",
                return_value={"name": name},
            ),
        ):
            response = await restore_catalogued_variant(request)

        self.assertEqual(response.status, 200)
        ensure_quota.assert_not_awaited()
        collection.update_one.assert_awaited_once()

    def test_saved_game_inline_ini_restores_archived_variant_after_restart(self) -> None:
        name = "archive_reload_test"
        app_state = SimpleNamespace(catalogued_variants={})
        game_doc = {
            "_id": "saved-game-id",
            "v": name,
            "vini": f"[{name}:chess]\n",
            "vd": "Archive reload test",
            "vby": "author",
        }

        unregister_catalogued_server_variant(name)
        self.addCleanup(unregister_catalogued_server_variant, name)

        validation = SimpleNamespace(
            name=name,
            base_variant="chess",
            start_fen="8/8/8/8/8/8/8/K6k w - - 0 1",
            width=8,
            height=8,
            pieces=["k"],
            king_roles=["k"],
            pocket_roles=[],
            capture_to_hand=False,
            promotion_type="",
            promotion_roles=[],
            promotion_order=[],
            show_promoted=False,
            rules_gate=False,
            rules_pass=False,
            legal_moves_need_history=False,
            n_fold_is_draw=False,
            show_check_counters=False,
        )

        with patch(
            "catalogued.variants.validate_catalogued_ini", return_value=validation
        ) as validate_catalogued_ini:
            ensure_catalogued_variant_from_game_doc(app_state, game_doc)

        validate_catalogued_ini.assert_called_once_with(game_doc["vini"])
        self.assertTrue(is_catalogued_variant(name))
        self.assertIn(name, app_state.catalogued_variants)
        restored = app_state.catalogued_variants[name]
        self.assertNotIn("icon", restored)
        self.assertEqual(restored["ini"], game_doc["vini"])
        self.assertEqual(restored["displayName"], game_doc["vd"])
        self.assertEqual(restored["author"], game_doc["vby"])
        self.assertFalse(restored["archived"])
        self.assertTrue(restored["enabled"])


if __name__ == "__main__":
    unittest.main()
