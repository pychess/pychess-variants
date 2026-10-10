import asyncio
import json
import time
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import game_api
import header_challenges
import inbox_api
import test_logger
import utils
from aiohttp.client_exceptions import ClientConnectionResetError
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp_session import Session
from bson.int64 import Int64
from compress import encode_move_standard
from const import SHIELD, STARTED, SWISS, T_FINISHED
from game import Game
from game_api import (
    _seen_discontinued_variants,
    duplicate_key_only_bulk_write_error,
    persist_variant_count_docs,
    safe_write_eof,
    variant_counts_aggregation,
    variant_counts_from_docs,
)
from glicko2.glicko2 import new_default_perf
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from pymongo.errors import BulkWriteError
from seek import BOT_CHALLENGE_DECLINED
from settings import MONGO_DB_NAME
from user import User
from variants import VARIANTS, get_server_variant, unregister_catalogued_server_variant

from server import make_app

test_logger.init_test_logger()


class GamesApiCategoryFilterTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        self.user = User(app_state, username="testuser", game_category="chess")
        self.profile_probe = "profileprobe"
        self.winner_probe = "winnerprobe"
        self.shield_probe = "shieldprobe"
        app_state.users[self.user.username] = self.user

        wplayer = User(app_state, username="white")
        bplayer = User(app_state, username="black")
        app_state.users[wplayer.username] = wplayer
        app_state.users[bplayer.username] = bplayer

        chess_game = Game(app_state, "g1", "chess", "", wplayer, bplayer)
        chess_game.status = STARTED
        app_state.games[chess_game.id] = chess_game

        shogi_game = Game(app_state, "g2", "shogi", "", wplayer, bplayer)
        shogi_game.status = STARTED
        app_state.games[shogi_game.id] = shogi_game

        chess960_game = Game(app_state, "g3", "chess", "", wplayer, bplayer, chess960=True)
        chess960_game.status = STARTED
        app_state.games[chess960_game.id] = chess960_game

        chess_code = get_server_variant("chess", False).code
        await app_state.db.user.insert_many(
            [
                {"_id": self.profile_probe, "title": "NM"},
                {"_id": self.winner_probe, "title": "IM"},
                {"_id": self.shield_probe, "title": "GM"},
            ]
        )
        await app_state.db.game.insert_one(
            {
                "_id": "db1",
                "us": [self.user.username, wplayer.username],
                "v": chess_code,
                "z": 0,
                "r": "a",
                "m": [],
                "s": STARTED,
                "d": datetime(2025, 1, 1),
                "y": 1,
            }
        )
        await app_state.db.game.insert_one(
            {
                "_id": "profiledb1",
                "us": [self.profile_probe, self.user.username],
                "v": chess_code,
                "z": 0,
                "r": "a",
                "m": [],
                "s": STARTED,
                "d": datetime(2025, 1, 2, tzinfo=UTC),
                "y": 1,
            }
        )
        await app_state.db.tournament.insert_many(
            [
                {
                    "_id": "Winner01",
                    "v": chess_code,
                    "z": 0,
                    "status": T_FINISHED,
                    "startsAt": datetime(2025, 1, 3, tzinfo=UTC),
                    "winner": self.winner_probe,
                    "nbGames": 1,
                    "nbPlayers": 3,
                },
                {
                    "_id": "Shield01",
                    "v": chess_code,
                    "z": 0,
                    "status": T_FINISHED,
                    "startsAt": datetime(2025, 1, 4, tzinfo=UTC),
                    "winner": self.shield_probe,
                    "fr": SHIELD,
                    "nbGames": 1,
                    "nbPlayers": 3,
                },
            ]
        )

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_games_filtered_by_category(self):
        self.set_session_user(self.user.username)

        response = await self.client.get("/api/games")
        self.assertEqual(response.status, 200)
        payload = await response.json()

        variants = {(item["variant"], item["chess960"]) for item in payload}
        self.assertIn(("chess", False), variants)
        self.assertIn(("chess", True), variants)
        self.assertNotIn(("shogi", False), variants)

    async def test_direct_anonymous_profile_uses_restricted_rendering(self):
        app_state = get_app_state(self.app)
        await app_state.db.ublog_post.insert_one(
            {
                "_id": "restricted-profile-post",
                "author": self.profile_probe,
                "title": "Restricted profile blog probe",
                "slug": "restricted-profile-blog-probe",
                "markdown": "This should not be loaded for a direct anonymous profile request.",
                "live": True,
            }
        )

        response = await self.client.get(f"/@/{self.profile_probe}")

        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn('data-profile-restricted="True"', body)
        self.assertNotIn("Restricted profile blog probe", body)
        self.assertNotIn(self.profile_probe, app_state.public_users._profiles)
        self.assertNotIn(self.profile_probe, app_state.public_users._titles)

    async def test_internal_profile_navigation_keeps_full_rendering(self):
        app_state = get_app_state(self.app)
        await app_state.db.ublog_post.insert_one(
            {
                "_id": "internal-profile-post",
                "author": self.profile_probe,
                "title": "Internal profile blog probe",
                "slug": "internal-profile-blog-probe",
                "markdown": "This should be loaded after an internal navigation.",
                "live": True,
            }
        )

        response = await self.client.get(
            f"/@/{self.profile_probe}",
            headers={"Referer": str(self.client.make_url("/"))},
        )

        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn('data-profile-restricted="False"', body)
        self.assertIn("Internal profile blog probe", body)
        self.assertIn(self.profile_probe, app_state.public_users._profiles)
        self.assertIn(self.profile_probe, app_state.public_users._titles)

    async def test_profile_page_and_games_api_do_not_cache_public_user(self):
        self.set_session_user(self.user.username)
        app_state = get_app_state(self.app)

        self.assertNotIn(self.profile_probe, app_state.users)

        response = await self.client.get(f"/@/{self.profile_probe}")
        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn(self.profile_probe, body)
        self.assertIn(f"/variants/community?author={self.profile_probe}", body)
        self.assertNotIn(self.profile_probe, app_state.users)

        response = await self.client.get(f"/api/games/user/{self.profile_probe}")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(["profiledb1"], [item["_id"] for item in payload])
        self.assertNotIn(self.profile_probe, app_state.users)

    async def test_profile_sidebar_lists_only_variants_with_rated_games(self):
        self.set_session_user(self.user.username)
        app_state = get_app_state(self.app)
        self.user.update_game_category("all")

        played_perf = new_default_perf()
        played_perf["gl"]["r"] = 1625.0
        played_perf["nb"] = 3
        unplayed_perf = new_default_perf()
        unplayed_perf["gl"]["r"] = 1550.0
        await app_state.db.user.update_one(
            {"_id": self.profile_probe},
            {
                "$set": {
                    "perfs": {
                        "chess": played_perf,
                        "antichess": unplayed_perf,
                    }
                }
            },
        )

        response = await self.client.get(f"/@/{self.profile_probe}")
        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn(f"/@/{self.profile_probe}/perf/chess", body)
        self.assertNotIn(f"/@/{self.profile_probe}/perf/antichess", body)

        response = await self.client.get(f"/@/{self.profile_probe}/perf/antichess")
        self.assertEqual(response.status, 200)

    async def test_winners_and_shields_pages_do_not_cache_public_users(self):
        self.set_session_user(self.user.username)
        app_state = get_app_state(self.app)

        response = await self.client.get("/tournaments/winners/chess")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn(self.winner_probe, html)
        self.assertIn("IM", html)
        self.assertNotIn(self.winner_probe, app_state.users)

        response = await self.client.get("/tournaments/shields/chess")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn(self.shield_probe, html)
        self.assertIn("GM", html)
        self.assertNotIn(self.shield_probe, app_state.users)

    async def test_profile_perf_unknown_variant_returns_not_found_page(self):
        self.set_session_user(self.user.username)

        response = await self.client.get(f"/@/{self.user.username}/perf/notavariant")
        self.assertEqual(response.status, 404)
        text = await response.text()
        self.assertIn("Page not found!", text)

    async def test_api_profile_perf_unknown_variant_returns_empty(self):
        self.set_session_user(self.user.username)

        response = await self.client.get(
            f"/api/games/user/{self.user.username}?filter=perf&variant=notavariant"
        )
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(payload, [])

    async def insert_archived_variant_game(self, name, *, inline_rules=True):
        self.user.game_category = "all"
        self.set_session_user(self.user.username)
        app_state = get_app_state(self.app)
        self.addCleanup(unregister_catalogued_server_variant, name)
        start_fen = "lnsgqkgsnl/1r6b1/pppppppppp/10/10/10/10/PPPPPPPPPP/1B6R1/LNSGKQGSNL[-] w 0 1"
        ini = f"[{name}:shogi]\nmaxRank = 10\nmaxFile = 10\nqueen = q\nstartFen = {start_fen}"
        await app_state.db.catalogued_variant.insert_one(
            {
                "_id": name,
                "name": name,
                "displayName": "Archived shogi",
                "ini": ini,
                "enabled": False,
                "archived": True,
            }
        )
        doc = {
            "_id": "archived-variant-game",
            "us": [self.profile_probe, self.user.username],
            "v": name,
            "z": 0,
            "r": "a",
            "m": [encode_move_standard("c2c3")],
            "s": 1,
            "d": datetime(2026, 10, 7, tzinfo=UTC),
            "y": 0,
            "if": start_fen,
        }
        if inline_rules:
            doc.update({"vini": ini, "vd": "Saved shogi"})
        await app_state.db.game.insert_one(doc)
        return app_state

    async def test_user_games_restores_archived_variant_from_saved_rules(self):
        name = "api_archived_inline"
        app_state = await self.insert_archived_variant_game(name)
        # Saved rules suffice even if the catalogue entry has been deleted.
        await app_state.db.catalogued_variant.delete_one({"_id": name})

        response = await self.client.get(f"/api/games/user/{self.profile_probe}")

        self.assertEqual(response.status, 200)
        payload = await response.json()
        saved_game = next(doc for doc in payload if doc["_id"] == "archived-variant-game")
        self.assertEqual(saved_game["v"], name)
        self.assertEqual(saved_game["lm"], "c3c4")
        self.assertEqual(saved_game["r"], "1-0")
        self.assertNotIn(name, app_state.catalogued_variants)

    async def test_user_games_restores_legacy_archived_variant_from_catalogue(self):
        name = "api_archived_legacy"
        app_state = await self.insert_archived_variant_game(name, inline_rules=False)

        response = await self.client.get(f"/api/games/user/{self.profile_probe}")

        self.assertEqual(response.status, 200)
        payload = await response.json()
        saved_game = next(doc for doc in payload if doc["_id"] == "archived-variant-game")
        self.assertEqual(saved_game["v"], name)
        self.assertEqual(saved_game["lm"], "c3c4")
        self.assertNotIn(name, app_state.catalogued_variants)
        archived_doc = await app_state.db.catalogued_variant.find_one({"_id": name})
        self.assertTrue(archived_doc["archived"])
        self.assertFalse(archived_doc["enabled"])

    async def test_user_games_skips_orphaned_variant_and_keeps_other_games(self):
        name = "api_archived_missing"
        app_state = await self.insert_archived_variant_game(name, inline_rules=False)
        await app_state.db.catalogued_variant.delete_one({"_id": name})

        with patch("game_api.log.error") as error:
            response = await self.client.get(f"/api/games/user/{self.profile_probe}")

        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual([doc["_id"] for doc in payload], ["profiledb1"])
        error.assert_called_once_with("get_user_games() KeyError. Unknown variant %r", name)

    async def test_advanced_search_treats_all_variant_as_no_filter(self):
        self.set_session_user(self.user.username)

        for variant_value in ("all", "ALL", ""):
            with self.subTest(variant=variant_value):
                response = await self.client.get(
                    f"/api/games/search?player1={self.user.username}&variant={variant_value}"
                )
                self.assertEqual(response.status, 200)
                payload = await response.json()
                self.assertIn("db1", [item["_id"] for item in payload["games"]])

    async def test_advanced_search_move_limit_includes_legacy_games_without_ply_field(self):
        self.set_session_user(self.user.username)

        response = await self.client.get(
            f"/api/games/search?player1={self.user.username}&maxMoves=3"
        )
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertIn("db1", [item["_id"] for item in payload["games"]])

    async def test_advanced_search_resolves_player_names_case_insensitively(self):
        self.set_session_user(self.user.username)
        app_state = get_app_state(self.app)
        username = "CaseSensitive"
        chess_code = get_server_variant("chess", False).code
        await app_state.db.user.insert_one(
            {"_id": username, "username_lower": username.lower(), "title": ""}
        )
        await app_state.db.game.insert_one(
            {
                "_id": "searchcase1",
                "us": [username, "white"],
                "v": chess_code,
                "z": 0,
                "r": "a",
                "m": [],
                "s": STARTED,
                "d": datetime(2025, 1, 5, tzinfo=UTC),
                "y": 1,
            }
        )

        response = await self.client.get(
            "/api/games/search?player1=%40casesensitive&white=CASESENSITIVE"
        )
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(["searchcase1"], [item["_id"] for item in payload["games"]])


class VariantStatsTestCase(unittest.TestCase):
    def test_discontinued_variants_logged_once(self):
        variant_counts = {variant: [] for variant in VARIANTS}
        docs = [
            {"_id": {"p": "202501", "v": "m", "z": 1}, "c": 1},
            {"_id": {"p": "202501", "v": "m", "z": 1}, "c": 2},
            {"_id": {"p": "202501", "v": "o", "z": 0}, "c": 3},
            {"_id": {"p": "202501", "v": "o", "z": 0}, "c": 4},
        ]

        _seen_discontinued_variants.clear()
        try:
            with patch("game_api.log.info") as info:
                variant_counts_from_docs(variant_counts, docs)

            warned_variants = {call.args[1] for call in info.call_args_list}
            self.assertEqual({"makruk960", "gothic"}, warned_variants)
            self.assertEqual(2, info.call_count)
        finally:
            _seen_discontinued_variants.clear()

    def test_user_defined_variants_are_ignored(self):
        variant_counts = {variant: [] for variant in VARIANTS}
        docs = [
            {"_id": {"p": "202501", "v": "annexation", "z": 0}, "c": 5},
            {
                "_id": {
                    "p": "202502",
                    "v": get_server_variant("chess", False).code,
                    "z": 0,
                },
                "c": 7,
            },
        ]

        _seen_discontinued_variants.clear()
        try:
            variant_counts_from_docs(variant_counts, docs)

            self.assertEqual([7], variant_counts["chess"])
            self.assertEqual({"annexation"}, _seen_discontinued_variants)
        finally:
            _seen_discontinued_variants.clear()


class VariantStatsAggregationTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_aggregation_excludes_user_defined_game_documents(self):
        game_collection = AsyncMock()
        game_collection.aggregate.return_value = AsyncMock()
        game_collection.aggregate.return_value.__aiter__.return_value = []
        app_state = SimpleNamespace(
            db=SimpleNamespace(
                game=game_collection,
                stats=AsyncMock(),
                stats_humans=AsyncMock(),
            )
        )

        await variant_counts_aggregation(app_state, humans=True, query_period="202501")

        pipeline = game_collection.aggregate.await_args.args[0]
        self.assertEqual({"$exists": False}, pipeline[0]["$match"]["vini"])
        self.assertIn("$expr", pipeline[0]["$match"])
        self.assertIn("$and", pipeline[0]["$match"])


class VariantStatsPersistenceTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_persist_variant_count_docs_ignores_duplicate_key_bulk_write_errors(self):
        stats_collection = AsyncMock()
        duplicate_error = BulkWriteError(
            {
                "writeErrors": [
                    {
                        "index": 0,
                        "code": 11000,
                        "errmsg": "duplicate key",
                    }
                ],
                "writeConcernErrors": [],
            }
        )
        stats_collection.insert_many.side_effect = duplicate_error
        app_state = SimpleNamespace(
            db=SimpleNamespace(stats=stats_collection, stats_humans=AsyncMock())
        )
        docs = [{"_id": {"p": "202603", "v": "n", "z": 0}, "c": 7}]

        with patch("game_api.log.info") as info:
            await persist_variant_count_docs(app_state, False, docs)

        stats_collection.insert_many.assert_awaited_once_with(docs, ordered=False)
        info.assert_called_once()

    async def test_persist_variant_count_docs_reraises_non_duplicate_bulk_write_errors(self):
        stats_collection = AsyncMock()
        write_error = BulkWriteError(
            {
                "writeErrors": [
                    {
                        "index": 0,
                        "code": 121,
                        "errmsg": "document validation failure",
                    }
                ],
                "writeConcernErrors": [],
            }
        )
        stats_collection.insert_many.side_effect = write_error
        app_state = SimpleNamespace(
            db=SimpleNamespace(stats=stats_collection, stats_humans=AsyncMock())
        )
        docs = [{"_id": {"p": "202603", "v": "n", "z": 0}, "c": 7}]

        with self.assertRaises(BulkWriteError):
            await persist_variant_count_docs(app_state, False, docs)


class VariantStatsEndpointTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    async def test_get_variant_stats_ignores_duplicate_key_race(self):
        docs = [
            {"_id": {"p": "202603", "v": get_server_variant("chess", False).code, "z": 0}, "c": 1}
        ]
        with patch("game_api.variant_counts_aggregation", new=AsyncMock(return_value=docs)) as agg:
            response = await self.client.get("/api/stats")

        self.assertEqual(response.status, 200)
        payload = await response.json()
        chess_series = next(item for item in payload if item["name"] == "chess")
        self.assertEqual([1], chess_series["data"])
        agg.assert_awaited_once()


class VariantStatsBulkWriteErrorTestCase(unittest.TestCase):
    def test_duplicate_key_only_bulk_write_error(self):
        self.assertTrue(
            duplicate_key_only_bulk_write_error(
                BulkWriteError(
                    {
                        "writeErrors": [{"index": 0, "code": 11000}],
                        "writeConcernErrors": [],
                    }
                )
            )
        )
        self.assertFalse(
            duplicate_key_only_bulk_write_error(
                BulkWriteError(
                    {
                        "writeErrors": [{"index": 0, "code": 11000}],
                        "writeConcernErrors": [{"code": 64}],
                    }
                )
            )
        )
        self.assertFalse(
            duplicate_key_only_bulk_write_error(
                BulkWriteError(
                    {
                        "writeErrors": [{"index": 0, "code": 121}],
                        "writeConcernErrors": [],
                    }
                )
            )
        )


class ExportPGNTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        user = User(app_state, username="testuser")
        other_user = User(app_state, username="otheruser")
        app_state.users[user.username] = user
        app_state.users[other_user.username] = other_user

        export_docs = [
            {"_id": f"g{i}", "us": ["testuser"], "v": "Z", "d": datetime(2025, 12, 1 + i)}
            for i in range(6)
        ]
        await app_state.db.game.insert_many(export_docs)

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_export_aggregates_legacy_failures(self):
        self.set_session_user("testuser")
        with (
            patch("game_api.pgn", side_effect=ValueError("invalid move")) as pgn_mock,
            patch("game_api.log.error") as error,
            patch("game_api.log.info") as info,
        ):
            response = await self.client.get("/api/games/user/testuser/pgn")
            self.assertEqual(response.status, 200)
            await response.text()

        self.assertEqual(6, pgn_mock.call_count)
        error.assert_not_called()

        summary_calls = [
            call
            for call in info.call_args_list
            if call.args and call.args[0] == "PGN export skipped invalid/legacy games: %s"
        ]
        self.assertEqual(1, len(summary_calls))
        self.assertIn("g5 ataxx 2025.12.06", summary_calls[0].args[1])
        self.assertNotIn("g0 ataxx 2025.12.01", summary_calls[0].args[1])

    async def test_export_returns_empty_for_anonymous_session(self):
        with (
            patch("game_api.asyncio.sleep", new=AsyncMock()) as sleep_mock,
            patch("game_api.pgn") as pgn_mock,
        ):
            response = await self.client.get("/api/games/user/testuser/pgn")

        self.assertEqual(response.status, 200)
        self.assertEqual(await response.text(), "")
        sleep_mock.assert_awaited_once_with(3)
        pgn_mock.assert_not_called()

    async def test_export_forbids_other_logged_in_users(self):
        self.set_session_user("otheruser")

        with patch("game_api.pgn") as pgn_mock:
            response = await self.client.get("/api/games/user/testuser/pgn")

        self.assertEqual(response.status, 403)
        pgn_mock.assert_not_called()

    async def test_export_supports_latest_n_via_max_query(self):
        self.set_session_user("testuser")
        with patch("game_api.pgn", side_effect=lambda doc: f"{doc['_id']}\n"):
            response = await self.client.get("/api/games/user/testuser/pgn?max=2")
            self.assertEqual(response.status, 200)
            body = await response.text()

        self.assertEqual("g5\ng4\n", body)


class UserGamesQueryParamsTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        user = User(app_state, username="testuser")
        other_user = User(app_state, username="otheruser")
        app_state.users[user.username] = user
        app_state.users[other_user.username] = other_user

        await app_state.db.user.insert_many(
            [
                {"_id": "testuser", "title": ""},
                {"_id": "otheruser", "title": ""},
                {"_id": "opponent", "title": ""},
            ]
        )

        chess_code = get_server_variant("chess", False).code
        await app_state.db.game.insert_many(
            [
                {
                    "_id": "g_old_loss",
                    "us": ["testuser", "opponent"],
                    "v": chess_code,
                    "z": 0,
                    "r": "b",
                    "m": [],
                    "s": STARTED + 1,
                    "d": datetime(2025, 1, 1, tzinfo=UTC),
                    "y": 1,
                },
                {
                    "_id": "g_mid_win",
                    "us": ["testuser", "opponent"],
                    "v": chess_code,
                    "z": 0,
                    "r": "a",
                    "m": [],
                    "s": STARTED + 1,
                    "d": datetime(2025, 1, 2, tzinfo=UTC),
                    "y": 1,
                },
                {
                    "_id": "g_new_win",
                    "us": ["testuser", "opponent"],
                    "v": chess_code,
                    "z": 0,
                    "r": "a",
                    "m": [],
                    "s": STARTED + 1,
                    "d": datetime(2025, 1, 3, tzinfo=UTC),
                    "y": 1,
                    "ts": [Int64(60000), Int64(59000)],
                },
            ]
        )

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_json_unified_endpoint_supports_max_latest_n(self):
        self.set_session_user("testuser")

        response = await self.client.get("/api/games/user/testuser?max=2")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(["g_new_win", "g_mid_win"], [item["_id"] for item in payload])

    async def test_json_unified_endpoint_filter_win_and_max(self):
        self.set_session_user("testuser")

        response = await self.client.get("/api/games/user/testuser?filter=win&max=1")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(["g_new_win"], [item["_id"] for item in payload])

    async def test_json_unified_endpoint_handles_bson_int64_fields(self):
        self.set_session_user("testuser")

        response = await self.client.get("/api/games/user/testuser?max=1")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual([60000, 59000], payload[0]["ts"])

    async def test_pgn_unified_endpoint_uses_same_filter_and_max(self):
        self.set_session_user("testuser")

        with patch("game_api.pgn", side_effect=lambda doc: f"{doc['_id']}\n"):
            response = await self.client.get("/api/games/user/testuser/pgn?filter=win&max=1")
            self.assertEqual(response.status, 200)
            body = await response.text()

        self.assertEqual("g_new_win\n", body)

    async def test_json_and_pgn_reject_invalid_filter(self):
        self.set_session_user("testuser")

        json_response_obj = await self.client.get("/api/games/user/testuser?filter=nope")
        self.assertEqual(json_response_obj.status, 400)

        pgn_response_obj = await self.client.get("/api/games/user/testuser/pgn?filter=nope")
        self.assertEqual(pgn_response_obj.status, 400)


class ExportTournamentTrfTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    async def test_export_swiss_tournament_trf(self):
        tournament = SimpleNamespace(system=SWISS)
        trf_text = "001    1      player\n"

        with (
            patch("game_api.load_tournament", new=AsyncMock(return_value=tournament)),
            patch("tournament.swiss.build_trf_export_text", return_value=trf_text) as build_trf,
        ):
            response = await self.client.get("/games/export/tournament/abc12345/trf")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "text/plain")
        self.assertEqual(await response.text(), trf_text)
        self.assertIn("pychess_tournament_abc12345.trf", response.headers["Content-Disposition"])
        build_trf.assert_called_once_with(tournament)

    async def test_export_trf_rejects_non_swiss_tournament(self):
        tournament = SimpleNamespace(system=0)

        with patch("game_api.load_tournament", new=AsyncMock(return_value=tournament)):
            response = await self.client.get("/games/export/tournament/abc12345/trf")

        self.assertEqual(response.status, 400)


class ExportWriteEofTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_safe_write_eof_ignores_client_disconnect(self):
        response = AsyncMock()
        response.write_eof.side_effect = ClientConnectionResetError(
            "Cannot write to closing transport"
        )

        with patch("game_api.log.exception") as error, patch("game_api.log.debug") as debug:
            await safe_write_eof(response)

        error.assert_not_called()
        debug.assert_called_once_with("Connection closed before PGN export EOF write.")


class SSESubscribeErrorFallbackTestCase(unittest.IsolatedAsyncioTestCase):
    class _UserStub(SimpleNamespace):
        def __init__(self, **kwargs):
            super().__init__(
                username="sse-user", enabled=True, anon=False, auth_version=0, **kwargs
            )

    @staticmethod
    def _session():
        return Session(
            None,
            new=False,
            data={"created": int(time.time()), "session": {"user_name": "sse-user"}},
        )

    class _TrackingSet(set):
        added = None

        def add(self, item):
            self.added = item
            super().add(item)

    class _UsersStub:
        def __init__(self, user):
            self.user = user

        async def get(self, _username):
            return self.user

    class _CapturingResponse:
        def __init__(self):
            self.connected = True
            self.payloads = []

        def is_connected(self):
            return self.connected

        async def send(self, payload):
            self.payloads.append(payload)
            self.connected = False

    @staticmethod
    @asynccontextmanager
    async def _capturing_sse_response(response, _request):
        yield response

    async def test_subscribe_notify_handles_sse_setup_error(self):
        notify_channels = self._TrackingSet()
        notify_user = self._UserStub(notify_channels=notify_channels)
        app_state = SimpleNamespace(users=self._UsersStub(notify_user))
        request = SimpleNamespace(app=object())

        with (
            patch("utils.get_app_state", return_value=app_state),
            patch(
                "utils.aiohttp_session.get_session",
                new=AsyncMock(return_value=self._session()),
            ),
            patch("utils.sse_response", side_effect=RuntimeError("setup failed")) as setup_sse,
        ):
            response = await utils.subscribe_notify(request)

        setup_sse.assert_called_once_with(request)
        self.assertEqual(response.status, 200)
        self.assertEqual(len(notify_user.notify_channels), 0)
        self.assertEqual(notify_channels.added.maxsize, utils.SSE_SNAPSHOT_QUEUE_MAXSIZE)
        with self.assertRaises(asyncio.QueueShutDown):
            notify_channels.added.get_nowait()

    async def test_legacy_header_streams_keep_unwrapped_payloads(self):
        from routes import get_routes

        routes = dict(get_routes)
        self.assertIs(routes["/notify"], utils.subscribe_notify)
        self.assertIs(routes["/challenge/subscribe"], header_challenges.subscribe_challenges)
        self.assertIs(routes["/api/header/subscribe"], header_challenges.subscribe_header)

        for module, handler, channel, payload in (
            (utils, utils.subscribe_notify, "notify_channels", [{"type": "studyInvite"}]),
            (
                header_challenges,
                header_challenges.subscribe_challenges,
                "challenge_channels",
                {"challenges": [{"id": "c1"}]},
            ),
        ):
            with self.subTest(channel=channel):
                channels = self._TrackingSet()
                user = self._UserStub(
                    **{channel: channels}, update_online=lambda: None, online=True
                )
                app_state = SimpleNamespace(users=self._UsersStub(user))
                response = self._CapturingResponse()

                @asynccontextmanager
                async def legacy_sse(
                    _request,
                    channel=channel,
                    channels=channels,
                    payload=payload,
                    response=response,
                ):
                    if channel == "notify_channels":
                        channels.added.put_nowait(json.dumps(payload))
                    yield response

                with (
                    patch.object(module, "get_app_state", return_value=app_state),
                    patch.object(
                        module.aiohttp_session,
                        "get_session",
                        new=AsyncMock(return_value=self._session()),
                    ),
                    patch.object(module, "sse_response", legacy_sse),
                    patch("header_challenges.cancel_direct_challenge_offline"),
                    patch("header_challenges.reactivate_direct_challenges", new=AsyncMock()),
                    patch("header_challenges.challenge_envelope", return_value=payload),
                ):
                    result = await handler(SimpleNamespace(app=object()))

                self.assertIs(result, response)
                self.assertEqual([json.loads(item) for item in response.payloads], [payload])
                self.assertEqual(len(channels), 0)
                with self.assertRaises(asyncio.QueueShutDown):
                    channels.added.get_nowait()

    async def test_subscribe_challenges_handles_sse_setup_error(self):
        challenge_channels = self._TrackingSet()
        challenge_user = self._UserStub(
            challenge_channels=challenge_channels,
            update_online=lambda: None,
            online=True,
        )
        app_state = SimpleNamespace(users=self._UsersStub(challenge_user))
        request = SimpleNamespace(app=object())

        with (
            patch("header_challenges.get_app_state", return_value=app_state),
            patch(
                "header_challenges.aiohttp_session.get_session",
                new=AsyncMock(return_value=self._session()),
            ),
            patch("header_challenges.cancel_direct_challenge_offline"),
            patch(
                "header_challenges.reactivate_direct_challenges",
                new=AsyncMock(),
            ),
            patch(
                "header_challenges.sse_response", side_effect=RuntimeError("setup failed")
            ) as setup_sse,
        ):
            response = await header_challenges.subscribe_challenges(request)

        setup_sse.assert_called_once_with(request)
        self.assertEqual(response.status, 200)
        self.assertEqual(len(challenge_channels), 0)
        self.assertEqual(
            challenge_channels.added.maxsize,
            header_challenges.SSE_SNAPSHOT_QUEUE_MAXSIZE,
        )
        with self.assertRaises(asyncio.QueueShutDown):
            challenge_channels.added.get_nowait()

    async def test_subscribe_invites_handles_sse_setup_error(self):
        game_id = "abcd1234"
        invite_channels = self._TrackingSet()
        app_state = SimpleNamespace(
            games={},
            invites={},
            invite_channels={game_id: invite_channels},
        )
        request = SimpleNamespace(app=object(), match_info={"gameId": game_id})

        with (
            patch("game_api.get_app_state", return_value=app_state),
            patch("game_api.sse_response", side_effect=RuntimeError("setup failed")),
        ):
            response = await game_api.subscribe_invites(request)

        self.assertEqual(response.status, 200)
        self.assertFalse(app_state.invite_channels.get(game_id))
        self.assertEqual(invite_channels.added.maxsize, game_api.SSE_SNAPSHOT_QUEUE_MAXSIZE)
        with self.assertRaises(asyncio.QueueShutDown):
            invite_channels.added.get_nowait()

    async def test_subscribe_invites_replays_accepted_game(self):
        game_id = "abcd1234"
        app_state = SimpleNamespace(
            games={game_id: object()},
            invites={},
            invite_channels={},
        )
        request = SimpleNamespace(app=object(), match_info={"gameId": game_id})
        response = self._CapturingResponse()

        with (
            patch("game_api.get_app_state", return_value=app_state),
            patch(
                "game_api.sse_response",
                lambda request: self._capturing_sse_response(response, request),
            ),
        ):
            result = await game_api.subscribe_invites(request)

        self.assertIs(result, response)
        self.assertEqual(
            [{"gameId": game_id, "accept": True}],
            [json.loads(payload) for payload in response.payloads],
        )

    async def test_subscribe_invites_replays_bot_decline(self):
        game_id = "abcd1234"
        decline_reason = "I'm not willing to play this variant right now."
        seek = SimpleNamespace(
            is_bot_challenge=True,
            bot_challenge_status=BOT_CHALLENGE_DECLINED,
            bot_challenge_decline_reason=decline_reason,
        )
        app_state = SimpleNamespace(
            games={},
            invites={game_id: seek},
            invite_channels={},
        )
        request = SimpleNamespace(app=object(), match_info={"gameId": game_id})
        response = self._CapturingResponse()

        with (
            patch("game_api.get_app_state", return_value=app_state),
            patch(
                "game_api.sse_response",
                lambda request: self._capturing_sse_response(response, request),
            ),
        ):
            result = await game_api.subscribe_invites(request)

        self.assertIs(result, response)
        self.assertEqual(
            [{"gameId": game_id, "accept": False, "declineReason": decline_reason}],
            [json.loads(payload) for payload in response.payloads],
        )

    async def test_subscribe_inbox_handles_sse_setup_error(self):
        inbox_channels = self._TrackingSet()
        inbox_user = self._UserStub(inbox_channels=inbox_channels)
        app_state = SimpleNamespace(users=self._UsersStub(inbox_user))
        request = SimpleNamespace(app=object())

        with (
            patch("inbox_api.get_app_state", return_value=app_state),
            patch(
                "inbox_api.aiohttp_session.get_session", new=AsyncMock(return_value=self._session())
            ),
            patch("inbox_api.sse_response", side_effect=RuntimeError("setup failed")) as setup_sse,
        ):
            response = await inbox_api.subscribe_inbox(request)

        setup_sse.assert_called_once_with(request)
        self.assertEqual(response.status, 200)
        self.assertEqual(len(inbox_channels), 0)
        self.assertEqual(inbox_channels.added.maxsize, inbox_api.SSE_EVENT_QUEUE_MAXSIZE)
        with self.assertRaises(asyncio.QueueShutDown):
            inbox_channels.added.get_nowait()

    async def test_subscribe_header_multiplexes_challenges_and_notifications(self):
        challenge_channels = self._TrackingSet()
        notify_channels = self._TrackingSet()
        header_user = self._UserStub(
            challenge_channels=challenge_channels,
            notify_channels=notify_channels,
            update_online=lambda: None,
            online=True,
        )
        app_state = SimpleNamespace(users=self._UsersStub(header_user))
        request = SimpleNamespace(app=object())

        class CapturingResponse:
            def __init__(self):
                self.connected = True
                self.payloads: list[str] = []

            def is_connected(self):
                return self.connected

            async def send(self, payload):
                self.payloads.append(payload)
                if len(self.payloads) >= 3:
                    self.connected = False

        response = CapturingResponse()

        @asynccontextmanager
        async def multiplexed_sse(_request):
            for queue in tuple(challenge_channels):
                queue.put_nowait('{"challenges":[{"id":"c1"}]}')
            for queue in tuple(notify_channels):
                queue.put_nowait('[{"type":"studyInvite"}]')
            yield response

        with (
            patch("header_challenges.get_app_state", return_value=app_state),
            patch(
                "header_challenges.aiohttp_session.get_session",
                new=AsyncMock(return_value=self._session()),
            ),
            patch("header_challenges.cancel_direct_challenge_offline"),
            patch(
                "header_challenges.reactivate_direct_challenges",
                new=AsyncMock(),
            ),
            patch(
                "header_challenges.challenge_envelope",
                return_value={"challenges": []},
            ),
            patch("header_challenges.sse_response", multiplexed_sse),
        ):
            result = await header_challenges.subscribe_header(request)

        self.assertIs(result, response)
        decoded = [json.loads(payload) for payload in response.payloads]
        self.assertEqual(decoded[0]["channel"], "challenges")
        self.assertEqual(json.loads(decoded[0]["payload"]), {"challenges": []})
        self.assertEqual(
            {item["channel"] for item in decoded[1:]},
            {"challenges", "notifications"},
        )
        by_channel = {item["channel"]: json.loads(item["payload"]) for item in decoded[1:]}
        self.assertEqual(by_channel["challenges"], {"challenges": [{"id": "c1"}]})
        self.assertEqual(by_channel["notifications"], [{"type": "studyInvite"}])
        self.assertEqual(len(challenge_channels), 0)
        self.assertEqual(len(notify_channels), 0)

    async def test_subscribe_header_handles_sse_setup_error(self):
        challenge_channels = self._TrackingSet()
        notify_channels = self._TrackingSet()
        header_user = self._UserStub(
            challenge_channels=challenge_channels,
            notify_channels=notify_channels,
            update_online=lambda: None,
            online=True,
        )
        app_state = SimpleNamespace(users=self._UsersStub(header_user))
        request = SimpleNamespace(app=object())

        with (
            patch("header_challenges.get_app_state", return_value=app_state),
            patch(
                "header_challenges.aiohttp_session.get_session",
                new=AsyncMock(return_value=self._session()),
            ),
            patch("header_challenges.cancel_direct_challenge_offline"),
            patch(
                "header_challenges.reactivate_direct_challenges",
                new=AsyncMock(),
            ),
            patch(
                "header_challenges.sse_response", side_effect=RuntimeError("setup failed")
            ) as setup_sse,
        ):
            response = await header_challenges.subscribe_header(request)

        setup_sse.assert_called_once_with(request)
        self.assertEqual(response.status, 200)
        self.assertEqual(len(challenge_channels), 0)
        self.assertEqual(len(notify_channels), 0)
        self.assertEqual(
            challenge_channels.added.maxsize, header_challenges.SSE_SNAPSHOT_QUEUE_MAXSIZE
        )
        self.assertEqual(
            notify_channels.added.maxsize, header_challenges.SSE_SNAPSHOT_QUEUE_MAXSIZE
        )
        with self.assertRaises(asyncio.QueueShutDown):
            challenge_channels.added.get_nowait()
        with self.assertRaises(asyncio.QueueShutDown):
            notify_channels.added.get_nowait()

    async def test_subscribe_games_handles_sse_setup_error(self):
        game_channels = self._TrackingSet()
        app_state = SimpleNamespace(game_channels=game_channels)
        request = SimpleNamespace(app=object())

        with (
            patch("game_api.get_app_state", return_value=app_state),
            patch("game_api.sse_response", side_effect=RuntimeError("setup failed")),
        ):
            response = await game_api.subscribe_games(request)

        self.assertEqual(response.status, 200)
        self.assertEqual(len(app_state.game_channels), 0)
        queue = game_channels.added
        self.assertEqual(queue.maxsize, game_api.ONGOING_GAME_QUEUE_MAXSIZE)
        with self.assertRaises(asyncio.QueueShutDown):
            queue.get_nowait()

    async def test_subscribe_games_times_out_blocked_send_and_drains_queue(self):
        game_channels = self._TrackingSet()
        app_state = SimpleNamespace(game_channels=game_channels)
        request = SimpleNamespace(app=object())

        class SlowResponse:
            def is_connected(self):
                return True

            async def send(self, _payload):
                await asyncio.Event().wait()

        slow_response = SlowResponse()

        @asynccontextmanager
        async def slow_sse_response(_request):
            game_channels.added.put_nowait("payload")
            yield slow_response

        with (
            patch("game_api.get_app_state", return_value=app_state),
            patch("game_api.sse_response", slow_sse_response),
            patch("sse_utils.SSE_SEND_TIMEOUT", 0.01),
        ):
            response = await game_api.subscribe_games(request)

        self.assertIs(response, slow_response)
        self.assertEqual(len(game_channels), 0)
        self.assertEqual(game_channels.added.qsize(), 0)
        with self.assertRaises(asyncio.QueueShutDown):
            game_channels.added.get_nowait()


class InviteReloadPersistenceTestCase(AioHTTPTestCase):
    async def get_application(self):
        db_client = AsyncMongoMockClient(tz_aware=True)
        db = db_client[MONGO_DB_NAME]
        await db.user.insert_many(
            [
                {"_id": "InviteCreator", "title": "", "enabled": True},
                {"_id": "InviteVisitor", "title": "", "enabled": True},
            ]
        )
        await db.seek.insert_one(
            {
                "_id": "seekInvite",
                "user": "InviteCreator",
                "variant": "chess",
                "chess960": False,
                "target": "Invite-friend",
                "fen": "",
                "color": "r",
                "rated": False,
                "rrmin": -10000,
                "rrmax": 10000,
                "base": 5,
                "inc": 5,
                "byoyomi": 0,
                "day": 0,
                "gameId": "AbCd1234",
            }
        )
        await db.seek.insert_one(
            {
                "_id": "seekInviteExpired",
                "user": "InviteCreator",
                "variant": "chess",
                "chess960": False,
                "target": "Invite-friend",
                "fen": "",
                "color": "r",
                "rated": False,
                "rrmin": -10000,
                "rrmax": 10000,
                "base": 5,
                "inc": 5,
                "byoyomi": 0,
                "day": 0,
                "gameId": "Expi1234",
                "expireAt": datetime.now(UTC) - timedelta(minutes=1),
            }
        )
        await db.seek.insert_one(
            {
                "_id": "seekBotDeclined",
                "user": "InviteCreator",
                "variant": "atomic",
                "chess960": False,
                "target": "BOT_challenge",
                "fen": "",
                "color": "r",
                "rated": False,
                "rrmin": -10000,
                "rrmax": 10000,
                "base": 3,
                "inc": 2,
                "byoyomi": 0,
                "day": 0,
                "gameId": "BotD1234",
                "botChallengeStatus": "declined",
                "botChallengeDeclineReason": "This bot does not support this variant.",
                "expireAt": datetime.now(UTC) + timedelta(minutes=30),
            }
        )
        return make_app(db_client=db_client, simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def _set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_reloaded_invite_page_is_available_after_restart(self):
        self._set_session_user("InviteVisitor")
        response = await self.client.get("/invite/AbCd1234")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('data-inviter="InviteCreator"', html)

    async def test_reloaded_invite_accept_starts_game_with_same_game_id(self):
        self._set_session_user("InviteVisitor")
        response = await self.client.post("/invite/accept/AbCd1234")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('data-view="round"', html)
        self.assertIn('data-gameid="AbCd1234"', html)

    async def test_reloaded_expired_invite_page_shows_expired_state(self):
        self._set_session_user("InviteVisitor")
        response = await self.client.get("/invite/Expi1234")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('data-inviter="expired"', html)
        app_state = get_app_state(self.app)
        self.assertNotIn("Expi1234", app_state.invites)

    async def test_reloaded_expired_invite_accept_shows_expired_state(self):
        self._set_session_user("InviteVisitor")
        response = await self.client.post("/invite/accept/Expi1234")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('data-inviter="expired"', html)

    async def test_reloaded_declined_bot_challenge_shows_decline_reason(self):
        self._set_session_user("InviteCreator")
        response = await self.client.get("/bot-challenge/BotD1234")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('data-view="bot_challenge"', html)
        self.assertIn('data-bot-challenge-status="declined"', html)
        self.assertIn(
            'data-bot-challenge-decline-reason="This bot does not support this variant."',
            html,
        )
