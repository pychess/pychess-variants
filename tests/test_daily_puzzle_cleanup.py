import json
import time
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import puzzle as puzzle_module
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from const import GAME_CATEGORY_ALL
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _puzzle_doc(puzzle_id: str, *, variant: str = "chess") -> dict:
    return {
        "_id": puzzle_id,
        "v": variant,
        "f": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "m": "e4",
        "t": "",
        "e": "#2",
    }


class _PuzzleAppTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def login(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})


class DailyPuzzleDanglingReferenceTestCase(_PuzzleAppTestCase):
    """A deleted puzzle must not stay wired into the daily puzzle rotation.

    Deleting the puzzle that is currently the daily puzzle used to leave its id
    in ``daily_puzzle_ids`` and in the ``dailypuzzle`` collection.
    ``get_daily_puzzle()`` then returned ``None``, which the lobby serialized
    into ``data-puzzle="null"`` and the client crashed on, while ``/puzzle/daily``
    returned a 404.
    """

    async def test_daily_puzzle_page_serves_a_replacement(self):
        app_state = get_app_state(self.app)
        await app_state.db.puzzle.insert_one(_puzzle_doc("b0001"))
        key = f"{_today()}:all"
        app_state.daily_puzzle_ids[key] = "a0001"  # never inserted -> dangling

        page = await self.client.get("/puzzle/daily")

        self.assertEqual(page.status, 200)
        self.assertEqual(app_state.daily_puzzle_ids[key], "b0001")

    async def test_dangling_reference_is_removed_from_cache_and_database(self):
        app_state = get_app_state(self.app)
        await app_state.db.puzzle.insert_one(_puzzle_doc("b0001"))
        key = f"{_today()}:all"
        app_state.daily_puzzle_ids[key] = "a0001"
        await app_state.db.dailypuzzle.insert_one({"_id": key, "puzzleId": "a0001"})

        await self.client.get("/puzzle/daily")

        self.assertEqual(app_state.daily_puzzle_ids[key], "b0001")
        stored = await app_state.db.dailypuzzle.find_one({"_id": key})
        self.assertEqual(stored["puzzleId"], "b0001")

    async def test_lobby_renders_when_daily_puzzle_reference_is_dangling(self):
        app_state = get_app_state(self.app)
        await app_state.db.puzzle.insert_one(_puzzle_doc("b0001"))
        app_state.daily_puzzle_ids[f"{_today()}:all"] = "a0001"

        page = await self.client.get("/")

        self.assertEqual(page.status, 200)
        self.assertNotIn('data-puzzle="null"', await page.text())

    async def test_existing_daily_puzzle_is_served_unchanged(self):
        app_state = get_app_state(self.app)
        await app_state.db.puzzle.insert_one(_puzzle_doc("b0001"))
        key = f"{_today()}:all"
        app_state.daily_puzzle_ids[key] = "b0001"
        await app_state.db.dailypuzzle.insert_one({"_id": key, "puzzleId": "b0001"})

        page = await self.client.get("/puzzle/daily")

        self.assertEqual(page.status, 200)
        self.assertEqual(app_state.daily_puzzle_ids[key], "b0001")

    async def test_empty_puzzle_database_still_serves_the_page(self):
        page = await self.client.get("/puzzle/daily")

        self.assertEqual(page.status, 200)


class PuzzleCompleteAfterDeletionTestCase(_PuzzleAppTestCase):
    """Completing a puzzle deleted while the page was open must be a no-op."""

    async def test_puzzle_complete_with_deleted_puzzle_returns_empty_json(self):
        app_state = get_app_state(self.app)
        app_state.users["solver"] = User(app_state, username="solver", enabled=True)
        self.login("solver")

        response = await self.client.post(
            "/puzzle/complete/a0001",
            data={"rated": "true", "v": "chess", "color": "w", "win": "true"},
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {})


class ConcurrentDailyPuzzleCleanupTestCase(unittest.IsolatedAsyncioTestCase):
    """Two requests can clean up the same dangling entry at the same time.

    Reading ``daily_puzzle_ids[key]`` again after an ``await`` is unsafe: the
    event loop can hand control to the other request, which drops the entry
    while this one is suspended, so the second read raises ``KeyError``.
    """

    async def test_dangling_entry_removed_by_a_concurrent_request_is_not_re_read(self):
        db = AsyncMongoMockClient(tz_aware=True).pychess
        await db.puzzle.insert_one(_puzzle_doc("b0001"))
        app_state = SimpleNamespace(
            db=db,
            daily_puzzle_ids={f"{_today()}:all": "a0001"},
            users={"PyChess": User.__new__(User)},
        )
        key = f"{_today()}:all"

        request = cast(web.Request, AsyncMock())
        request.app = {}

        async def get_puzzle(_request, puzzle_id):
            self.assertEqual(puzzle_id, "a0001")
            # Simulate the other request winning the race: it removes the shared
            # entry while this request is suspended at the await below.
            app_state.daily_puzzle_ids.pop(key, None)

        with (
            patch("puzzle.get_app_state", return_value=app_state),
            patch("puzzle.get_puzzle", new=get_puzzle),
            patch("puzzle.drop_stale_daily_puzzle_keys", new=AsyncMock()) as drop_stale,
            patch(
                "puzzle.effective_game_category",
                return_value=GAME_CATEGORY_ALL,
            ),
            patch("puzzle.aiohttp_session.get_session", new=AsyncMock(return_value={})),
        ):
            puzzle = await puzzle_module.get_daily_puzzle(request)

        self.assertEqual(puzzle["_id"], "b0001")
        drop_stale.assert_awaited_once_with(app_state, "a0001")


if __name__ == "__main__":
    unittest.main(verbosity=2)
