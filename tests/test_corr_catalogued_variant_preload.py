from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from views import add_catalogued_variant_context, add_corr_games_context


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.sort_args: tuple[str, int] | None = None

    def sort(self, key: str, direction: int) -> FakeCursor:
        self.sort_args = (key, direction)
        return self

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for doc in self.docs:
            yield doc


class FakeGameCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.query: dict | None = None
        self.cursor: FakeCursor | None = None

    def find(self, query: dict) -> FakeCursor:
        self.query = query
        self.cursor = FakeCursor(self.docs)
        return self.cursor


class CorrespondenceCataloguedVariantPreloadTest(unittest.IsolatedAsyncioTestCase):
    async def test_adds_missing_variant_metadata_for_ongoing_game(self) -> None:
        game = SimpleNamespace(id="game-id", variant="archived-variant")
        user = SimpleNamespace(username="participant", correspondence_games=[game])
        context = {"catalogued_variants": "[]"}
        client_doc = {"name": "archived-variant", "archived": True, "enabled": False}

        with (
            patch("views.corr_games", return_value=[{"gameId": "game-id"}]),
            patch(
                "views.catalogued_variant_client_doc_for_game",
                AsyncMock(return_value=client_doc),
            ) as lookup,
        ):
            await add_corr_games_context(SimpleNamespace(), user, context)

        self.assertEqual(json.loads(context["corr_games"]), [{"gameId": "game-id"}])
        self.assertEqual(json.loads(context["catalogued_variants"]), [client_doc])
        lookup.assert_awaited_once_with(ANY, game, "participant")

    async def test_does_not_reload_variant_already_in_context(self) -> None:
        game = SimpleNamespace(id="game-id", variant="already-loaded")
        user = SimpleNamespace(username="participant", correspondence_games=[game])
        context = {"catalogued_variants": '[{"name":"already-loaded"}]'}

        with (
            patch("views.corr_games", return_value=[]),
            patch(
                "views.catalogued_variant_client_doc_for_game",
                AsyncMock(),
            ) as lookup,
        ):
            await add_corr_games_context(SimpleNamespace(), user, context)

        lookup.assert_not_awaited()
        self.assertEqual(
            json.loads(context["catalogued_variants"]),
            [{"name": "already-loaded"}],
        )

    async def test_completes_users_corr_games_while_background_restore_is_running(self) -> None:
        existing = SimpleNamespace(id="existing", variant="chess")
        user = SimpleNamespace(
            username="participant",
            anon=False,
            correspondence_games=[existing],
        )
        docs = [
            {"_id": "started", "s": -1},
            {"_id": "old-created", "s": -2},
        ]
        collection = FakeGameCollection(docs)
        app_state = SimpleNamespace(
            correspondence_games_loaded=asyncio.Event(),
            db=SimpleNamespace(game=collection),
        )
        context = {"catalogued_variants": '[{"name":"chess"}]'}

        async def load_doc(_app_state, doc):
            if all(game.id != doc["_id"] for game in user.correspondence_games):
                user.correspondence_games.append(SimpleNamespace(id=doc["_id"], variant="chess"))

        with (
            patch(
                "views.load_game_from_doc",
                AsyncMock(side_effect=load_doc),
            ) as load_game,
            patch(
                "views.corr_games",
                side_effect=lambda games: [{"gameId": game.id} for game in games],
            ),
        ):
            await add_corr_games_context(app_state, user, context)

        self.assertEqual(
            json.loads(context["corr_games"]),
            [
                {"gameId": "existing"},
                {"gameId": "started"},
                {"gameId": "old-created"},
            ],
        )
        self.assertEqual(
            collection.query,
            {
                "r": "d",
                "c": True,
                "us": "participant",
                "$or": [{"s": -2}, {"s": -1}],
            },
        )
        self.assertEqual(collection.cursor.sort_args, ("d", -1))
        self.assertEqual(load_game.await_count, 2)

    async def test_does_not_query_after_global_corr_restore_completed(self) -> None:
        loaded = asyncio.Event()
        loaded.set()
        collection = FakeGameCollection([])
        app_state = SimpleNamespace(
            correspondence_games_loaded=loaded,
            db=SimpleNamespace(game=collection),
        )
        user = SimpleNamespace(
            username="participant",
            anon=False,
            correspondence_games=[],
        )
        context = {"catalogued_variants": "[]"}

        with patch("views.corr_games", return_value=[]):
            await add_corr_games_context(app_state, user, context)

        self.assertIsNone(collection.query)
        self.assertEqual(json.loads(context["corr_games"]), [])


if __name__ == "__main__":
    unittest.main()


class OnDemandGameVariantMetadataTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_spectators_can_load_public_game_variant(self):
        user = SimpleNamespace(username="spectator", anon=False)
        game = SimpleNamespace(variant="custom")
        context = {"catalogued_variants": "[]"}
        with (
            patch("views.is_catalogued_variant", return_value=True),
            patch("views.catalogued_variant_client_doc_for_name", return_value={"name": "custom"}),
            patch(
                "views.catalogued_variant_client_doc_for_game", new_callable=AsyncMock
            ) as private_lookup,
        ):
            await add_catalogued_variant_context(
                SimpleNamespace(), user, context, "custom", game=game
            )
            self.assertEqual(json.loads(context["catalogued_variants"]), [{"name": "custom"}])
            private_lookup.assert_not_awaited()

    async def test_participants_can_load_archived_game_variant(self):
        user = SimpleNamespace(username="participant", anon=False)
        game = SimpleNamespace(variant="archived")
        context = {"catalogued_variants": "[]"}
        with (
            patch("views.is_catalogued_variant", return_value=True),
            patch("views.catalogued_variant_client_doc_for_name", return_value=None),
            patch(
                "views.catalogued_variant_client_doc_for_game",
                new_callable=AsyncMock,
                return_value={"name": "archived"},
            ) as private_lookup,
        ):
            await add_catalogued_variant_context(
                SimpleNamespace(), user, context, "archived", game=game
            )
            self.assertEqual(json.loads(context["catalogued_variants"]), [{"name": "archived"}])
            private_lookup.assert_awaited_once_with(ANY, game, "participant")
