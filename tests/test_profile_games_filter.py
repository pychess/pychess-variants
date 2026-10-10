import json
import time
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from aiohttp.test_utils import AioHTTPTestCase
from const import STARTED
from game_api import (
    _build_user_games_filter_cond,
    _resolve_user_games_filter_and_variant,
)
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User
from variants import get_server_variant

from server import make_app


class _FakeRequest:
    """Minimal stand-in for an aiohttp Request used by the resolve function."""

    def __init__(self, path: str, query: dict | None = None):
        self.path = path
        self.rel_url = SimpleNamespace(query=query or {})


class ProfileGamesFilterCombineTestCase(unittest.TestCase):
    """Issue #648: the profile page variant filter and the Rated/Casual/...
    tabs must combine (AND) instead of resetting each other.

    These tests exercise the two pure helpers that build the MongoDB query
    directly, so they cover the fix without needing a live database.
    """

    PROFILE = "someuser"
    SESSION = "otheruser"

    def _resolve(self, path: str, query: dict | None = None):
        return _resolve_user_games_filter_and_variant(_FakeRequest(path, query))

    def _build(self, path: str, query: dict | None = None, level: str | None = None):
        selected_filter, selected_variant, _parts = self._resolve(path, query)
        return _build_user_games_filter_cond(
            profile_id=self.PROFILE,
            session_user=self.SESSION,
            selected_filter=selected_filter,
            selected_variant=selected_variant,
            level=level,
        )

    def _variant_clause(self, name: str, is960: bool = False) -> dict:
        code = get_server_variant(name, is960).code
        z = 1 if is960 else 0
        return {
            "$or": [
                {"v": code, "z": z, "us.1": self.PROFILE},
                {"v": code, "z": z, "us.0": self.PROFILE},
            ]
        }

    def _rated_clause(self) -> dict:
        return {
            "$or": [
                {"y": 1, "us.1": self.PROFILE},
                {"y": 1, "us.0": self.PROFILE},
            ]
        }

    # --- resolve layer: tab and variant are detected independently ---

    def test_resolve_rated_tab_with_variant_query(self):
        selected_filter, selected_variant, _parts = self._resolve(
            "/@/someuser/rated", {"variant": "chess"}
        )
        self.assertEqual(selected_filter, "rated")
        self.assertEqual(selected_variant, "chess")

    def test_resolve_variant_only_from_path(self):
        selected_filter, selected_variant, _parts = self._resolve("/@/someuser/perf/chess")
        self.assertEqual(selected_filter, "perf")
        self.assertEqual(selected_variant, "chess")

    def test_resolve_no_filter_means_all(self):
        selected_filter, selected_variant, _parts = self._resolve("/@/someuser")
        self.assertEqual(selected_filter, "all")
        self.assertIsNone(selected_variant)

    # --- build layer: combining the two filters ---

    def test_rated_tab_and_variant_combine_with_and(self):
        cond = self._build("/@/someuser/rated", {"variant": "chess"})
        self.assertEqual(
            cond,
            {
                "$and": [
                    self._rated_clause(),
                    self._variant_clause("chess"),
                    {"y": {"$ne": 2}},
                ]
            },
        )

    def test_variant_only_excludes_imported_games(self):
        cond = self._build("/@/someuser/perf/chess")
        self.assertEqual(
            cond,
            {"$and": [self._variant_clause("chess"), {"y": {"$ne": 2}}]},
        )

    def test_rated_tab_only_excludes_imported_games(self):
        cond = self._build("/@/someuser/rated")
        self.assertEqual(
            cond,
            {"$and": [self._rated_clause(), {"y": {"$ne": 2}}]},
        )

    def test_no_filter_returns_all_user_games(self):
        cond = self._build("/@/someuser")
        self.assertEqual(cond, {"us": self.PROFILE})

    def test_unknown_variant_on_perf_path_returns_none(self):
        cond = self._build("/@/someuser/perf/notavariant")
        self.assertIsNone(cond)

    def test_unknown_variant_with_rated_tab_returns_none(self):
        cond = self._build("/@/someuser/rated", {"variant": "notavariant"})
        self.assertIsNone(cond)

    def test_chess960_variant_is_flagged_with_z(self):
        cond = self._build("/@/someuser/perf/chess960")
        self.assertEqual(
            cond,
            {"$and": [self._variant_clause("chess", is960=True), {"y": {"$ne": 2}}]},
        )

    def test_import_tab_does_not_exclude_imported_games(self):
        # ?filter=import (or /import path) returns imported games of the user and
        # may still be narrowed by a variant.
        selected_filter, selected_variant, _parts = self._resolve(
            "/@/someuser/import", {"variant": "chess"}
        )
        cond = _build_user_games_filter_cond(
            profile_id=self.PROFILE,
            session_user=self.SESSION,
            selected_filter=selected_filter,
            selected_variant=selected_variant,
            level=None,
        )
        self.assertEqual(
            cond,
            {"$and": [{"by": self.PROFILE, "y": 2}, self._variant_clause("chess")]},
        )


if __name__ == "__main__":
    unittest.main()


class ProfileGamesFilterCombineHttpTestCase(AioHTTPTestCase):
    """End-to-end coverage of #648 through the real app: the profile games API
    ANDs the tab and the variant, and the profile page preserves the active tab
    when a variant link is rendered.
    """

    PROFILE = "combouser"
    OPPONENT = "opponent"
    VIEWER = "viewer"

    async def startup(self, app):
        app_state = get_app_state(self.app)
        # The session user must be a live, non-anon User so the games API does
        # not treat the request as anonymous. The viewed PROFILE is intentionally
        # NOT registered as a live User: get_profile() checks the live user first
        # and would otherwise return a User with empty perfs (the sidebar would
        # render no variant links). Seeding PROFILE only in the DB lets
        # get_profile() read the perfs document instead.
        viewer = User(app_state, username=self.VIEWER)
        app_state.users[self.VIEWER] = viewer

        await app_state.db.user.insert_many(
            [
                {"_id": self.PROFILE, "title": ""},
                {"_id": self.OPPONENT, "title": ""},
            ]
        )
        # Give combouser perfs so the variant sidebar renders variant links.
        await app_state.db.user.update_one(
            {"_id": self.PROFILE},
            {
                "$set": {
                    "perfs": {
                        "chess": {"nb": 5, "gl": {"r": 1500.0, "d": 0}},
                        "shogi": {"nb": 3, "gl": {"r": 1500.0, "d": 0}},
                    }
                }
            },
        )

        chess_code = get_server_variant("chess", False).code
        shogi_code = get_server_variant("shogi", False).code
        base = {
            "us": [self.PROFILE, self.OPPONENT],
            "z": 0,
            "r": "a",
            "m": [],
            "s": STARTED + 1,
            "d": datetime(2025, 1, 1, tzinfo=UTC),
        }
        await app_state.db.game.insert_many(
            [
                # rated chess
                {**base, "_id": "rated_chess", "v": chess_code, "y": 1},
                # casual chess
                {**base, "_id": "casual_chess", "v": chess_code, "y": 0},
                # rated shogi
                {**base, "_id": "rated_shogi", "v": shogi_code, "y": 1},
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

    async def _games(self, query: str) -> list:
        self.set_session_user(self.VIEWER)
        response = await self.client.get(f"/api/games/user/{self.PROFILE}?{query}")
        self.assertEqual(response.status, 200)
        return await response.json()

    async def test_rated_and_chess_returns_only_rated_chess(self):
        payload = await self._games("filter=rated&variant=chess")
        self.assertEqual(["rated_chess"], [item["_id"] for item in payload])

    async def test_variant_chess_returns_both_rated_and_casual(self):
        payload = await self._games("variant=chess")
        self.assertEqual(
            {"rated_chess", "casual_chess"},
            {item["_id"] for item in payload},
        )

    async def test_rated_tab_returns_both_variants(self):
        payload = await self._games("filter=rated")
        self.assertEqual(
            {"rated_chess", "rated_shogi"},
            {item["_id"] for item in payload},
        )

    async def test_rated_and_shogi_returns_only_rated_shogi(self):
        payload = await self._games("filter=rated&variant=shogi")
        self.assertEqual(["rated_shogi"], [item["_id"] for item in payload])

    async def test_unknown_variant_with_rated_tab_returns_empty(self):
        payload = await self._games("filter=rated&variant=notavariant")
        self.assertEqual([], payload)

    async def test_profile_page_preserves_tab_when_variant_active(self):
        self.set_session_user(self.VIEWER)
        response = await self.client.get(f"/@/{self.PROFILE}/rated?variant=chess")
        self.assertEqual(response.status, 200)
        body = await response.text()

        # The client model must carry both the active tab and the variant so the
        # two filters combine instead of resetting each other.
        self.assertIn('data-rated="1"', body)
        self.assertIn('data-variant="chess"', body)
        # Variant links on the Rated tab keep the tab in the URL.
        self.assertIn(f"/@/{self.PROFILE}/rated?variant=chess", body)
