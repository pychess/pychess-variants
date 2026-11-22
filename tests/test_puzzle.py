import re
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import aiohttp_jinja2
import jinja2
import puzzle
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from const import HTTP_ANON_USER
from glicko2.glicko2 import gl2
from mongomock_motor import AsyncMongoMockClient
from typedefs import pychess_global_app_state_key
from views.puzzle import puzzle as puzzle_view


class PuzzleRequestHandlingTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_read_puzzle_post_connection_reset_returns_none(self):
        request = cast(web.Request, AsyncMock())
        request.post = AsyncMock(side_effect=ConnectionResetError)

        data = await puzzle._read_puzzle_post(request)

        self.assertIsNone(data)

    async def test_puzzle_complete_connection_reset_returns_empty_json(self):
        request = cast(web.Request, AsyncMock())
        request.app = {}
        request.match_info = {"puzzleId": "puzzle1"}
        request.post = AsyncMock(side_effect=ConnectionResetError)

        with patch("puzzle.get_app_state", return_value=SimpleNamespace()):
            response = await puzzle.puzzle_complete(request)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.text, "{}")

    async def test_puzzle_vote_connection_reset_returns_empty_json(self):
        request = cast(web.Request, AsyncMock())
        request.app = {}
        request.match_info = {"puzzleId": "puzzle1"}
        request.post = AsyncMock(side_effect=ConnectionResetError)

        with patch("puzzle.get_app_state", return_value=SimpleNamespace()):
            response = await puzzle.puzzle_vote(request)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.text, "{}")


class PuzzleRatingTestCase(AioHTTPTestCase):
    async def get_application(self):
        app = web.Application()
        self.db = AsyncMongoMockClient(tz_aware=True).pychess
        app[pychess_global_app_state_key] = SimpleNamespace(db=self.db)
        env = aiohttp_jinja2.setup(
            app,
            enable_async=True,
            extensions=["jinja2.ext.i18n"],
            loader=jinja2.FileSystemLoader("templates"),
            autoescape=jinja2.select_autoescape(["html"]),
        )
        env.install_null_translations(newstyle=True)
        env.globals.update(
            static=lambda path: f"/static/{path}", local_static=lambda path: f"/static/{path}"
        )
        app.router.add_get("/puzzle/{puzzleId}", puzzle_view)
        user = SimpleNamespace(
            username=HTTP_ANON_USER,
            puzzles={},
            get_puzzle_rating=lambda *_: gl2.create_rating(),
        )

        async def get_user_context(_request):
            return user, {"view": "puzzle", "anon": True}

        self.context_patch = patch("views.puzzle.get_user_context", new=get_user_context)
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)
        return app

    async def test_random_puzzle_uses_the_same_stored_rating_as_its_direct_page(self):
        await self.db.puzzle.insert_one(
            {
                "_id": "EoGTD",
                "v": "dobutsu",
                "f": "1le/1C1/g1G/E1L[C] b - - 0 3",
                "m": "c4b3",
                "t": "winning",
                "e": "#71",
                "perf": {
                    "gl": {"r": 1325.18, "d": 73.83, "v": 0.06},
                    "la": datetime.now(UTC),
                    "nb": 445,
                },
            }
        )

        for path in ("/puzzle/dobutsu", "/puzzle/EoGTD"):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                body = await response.text()
                ratings = dict(re.findall(r'data-([wb]rating)="([^"]*)"', body))
                self.assertEqual(ratings, {"wrating": "1325", "brating": "1500"})

    async def test_random_puzzle_without_a_stored_rating_uses_the_initial_estimate(self):
        await self.db.puzzle.insert_one(
            {
                "_id": "new01",
                "v": "dobutsu",
                "f": "g1e/1cl/LC1/EG1[] b - - 3 2",
                "m": "c3c2,b2b3,c4b3",
                "t": "mate",
                "e": "#2",
            }
        )

        response = await self.client.get("/puzzle/dobutsu")

        self.assertEqual(response.status, 200)
        body = await response.text()
        ratings = dict(re.findall(r'data-([wb]rating)="([^"]*)"', body))
        self.assertEqual(ratings, {"wrating": "1500", "brating": "1500"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
