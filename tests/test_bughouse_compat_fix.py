import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock

import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from bug.game_bug import GameBug
from const import RESIGN, STARTED
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User
from variants import VARIANTS
from views import add_game_context
from wsr import init_ws

from server import make_app

test_logger.init_test_logger()


class BughouseContextTestCase(unittest.TestCase):
    def test_add_game_context_uses_bughouse_compat_fields(self) -> None:
        player_a = SimpleNamespace(username="whiteA", title="", patron=False)
        player_b = SimpleNamespace(username="blackA", title="", patron=False)
        player_c = SimpleNamespace(username="whiteB", title="", patron=False)
        player_d = SimpleNamespace(username="blackB", title="", patron=False)

        class FakeBughouseGame:
            id = "bug1"
            variant = "bughouse"
            wplayer = player_a
            bplayer = player_b
            wplayerB = player_c
            bplayerB = player_d
            wrating = "1500"
            brating = "1500"
            wrating_b = "1500"
            brating_b = "1500"
            wrdiff = 0
            brdiff = 0
            chess960 = True
            rated = 0
            corr = False
            level = 0
            fen = "fen-a | fen-b"
            posnum = -1
            base = 3
            inc = 2
            byoyomi_period = 0
            result = "*"
            status = STARTED + 1
            date = datetime(2026, 3, 19, tzinfo=UTC)
            browser_title = "Bughouse"
            ply = 4
            initial_fen = "start-a | start-b"
            server_variant = SimpleNamespace(two_boards=True)

            @property
            def board(self) -> object:
                raise AssertionError("bughouse context should not access game.board")

            def get_board(
                self, full: bool = False, persp_color: int | None = None, *, client_history=False
            ) -> dict[str, object]:
                return {"type": "board", "full": full, "persp": persp_color}

        context: dict[str, object] = {}
        add_game_context(FakeBughouseGame(), None, SimpleNamespace(username="spectator"), context)

        self.assertEqual(context["posnum"], -1)
        self.assertEqual(context["fen"], "fen-a | fen-b")
        self.assertEqual(context["initialFen"], "start-a | start-b")
        self.assertEqual(context["wplayerB"], "whiteB")
        self.assertEqual(context["bplayerB"], "blackB")


class GamesApiBughousePreviewTestCase(AioHTTPTestCase):
    async def startup(self, app) -> None:
        app_state = get_app_state(self.app)

        class FakeBughouseGame:
            id = "bug1"
            variant = "bughouse"
            chess960 = False
            base = 3
            inc = 0
            byoyomi_period = 0
            level = 0
            corr = False
            status = STARTED
            lastmove = None
            turn_player = "whiteA"
            preview_fen = "fen-a"
            wplayer = SimpleNamespace(username="whiteA", title="")
            bplayer = SimpleNamespace(username="blackA", title="")
            spectators: ClassVar[set[object]] = set()
            non_bot_players: ClassVar[list[object]] = []

            @property
            def board(self) -> object:
                raise AssertionError("bughouse preview should not access game.board")

        app_state.games["bug1"] = FakeBughouseGame()

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self) -> None:
        await self.client.close()

    async def test_api_games_uses_preview_fen(self) -> None:
        response = await self.client.get("/api/games")
        self.assertEqual(response.status, 200)
        payload = await response.json()

        self.assertEqual(payload[0]["gameId"], "bug1")
        self.assertEqual(payload[0]["fen"], "fen-a")


class BughouseRoundSocketTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self) -> None:
        await self.client.close()

    async def test_active_and_finished_bughouse_connections_send_both_boards(self):
        state = get_app_state(self.app)
        players = [
            User(state, username=name, perfs=new_default_perf_map(VARIANTS))
            for name in ("whiteA", "blackA", "whiteB", "blackB", "spectator")
        ]
        for player in players:
            state.users[player.username] = player
        game = GameBug(state, "bugWS001", "bughouse", "", *players[:4], rated=False)
        state.games[game.id] = game
        await game.play_move("e2e4", clocks=[60000, 60000], clocks_b=[60000, 60000], board="a")
        await game.play_move("d2d4", clocks=[60000, 60000], clocks_b=[60000, 60000], board="b")

        for status in (STARTED, RESIGN):
            game.status = status
            game.result = "*" if status == STARTED else "1-0"
            for viewer in players:
                with self.subTest(status=status, viewer=viewer.username):
                    ws = AsyncMock()
                    await init_ws(state, ws, viewer, game)
                    messages = [json.loads(call.args[0]) for call in ws.send_str.await_args_list]
                    board = next(message for message in messages if message["type"] == "board")
                    self.assertEqual(board["fen"], game.fen)
                    self.assertEqual(len(board["steps"]), 3)
                    self.assertEqual(board["steps"][-1]["fenB"], game.boards["b"].fen)
                    self.assertIn("clocksB", board)
                    self.assertNotIn("history", board)
                    viewer.remove_ws_for_game(game.id, ws)


if __name__ == "__main__":
    unittest.main(verbosity=2)
