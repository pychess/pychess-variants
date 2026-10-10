"""Compare compact archive display and explicit replay with pre-change server output."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import fishnet
import test_logger
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from bson import Int64
from bug.utils_bug import load_game_bug_from_doc
from const import STARTED
from fairy import FairyBoard
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User
from variants import VARIANTS
from views import add_game_context
from wsr import init_ws

from server import make_app

test_logger.init_test_logger()
FIXTURES = json.loads(Path(__file__).with_name("twoBoardHistoryFixtures.json").read_text())


class TwoBoardDisplayHistoryTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def setUpAsync(self):
        await super().setUpAsync()
        self.state = get_app_state(self.app)
        for name in ("aw", "ab", "bw", "bb", "viewer"):
            self.state.users[name] = User(
                self.state, username=name, perfs=new_default_perf_map(VARIANTS)
            )

    async def tearDownAsync(self):
        await self.client.close()

    async def load_fixture(self, fixture, **updates):
        doc = {**fixture["doc"], **updates}
        doc["d"] = datetime.fromisoformat(doc["d"])
        with patch("bug.game_bug.time_ns", return_value=0):
            return await load_game_bug_from_doc(self.state, doc, cache_finished=False)

    async def test_finished_load_and_display_do_not_replay_native_moves(self):
        for fixture in FIXTURES:
            with (
                self.subTest(name=fixture["name"]),
                patch.object(FairyBoard, "push", side_effect=AssertionError("archive replay")),
                patch.object(FairyBoard, "get_san", side_effect=AssertionError("archive SAN")),
                patch.object(
                    FairyBoard,
                    "piece_to_partner",
                    side_effect=AssertionError("archive capture"),
                ),
            ):
                game = await self.load_fixture(fixture)
                board = game.get_board(full=True, client_history=True)
                self.assertEqual(len(game.steps), 1)
                self.assertEqual(board["steps"], fixture["expected"][:1])
                self.assertEqual(board["fen"], fixture["message"]["fen"])
                self.assertEqual(board["ply"], len(fixture["expected"]) - 1)
                history = board["twoBoardHistory"]
                self.assertEqual(
                    history["moves"],
                    [
                        step["move" if step["boardName"] == "a" else "moveB"]
                        for step in fixture["expected"][1:]
                    ],
                )
                self.assertEqual(
                    history["boards"], [step["boardName"] for step in fixture["expected"][1:]]
                )
                self.assertEqual(
                    history["metadata"],
                    [
                        {
                            key: step[key]
                            for key in ("clocks", "clocksB", "ts", "analysis", "chat")
                            if key in step
                        }
                        for step in fixture["expected"][1:]
                    ],
                )
                self.assertEqual(board["lastMove"], fixture["message"]["lastMove"])
                self.assertEqual(board["uci_usi"], fixture["message"]["uci_usi"])
                self.assertEqual(board["check"], fixture["message"]["check"])
                self.assertEqual(board["checkB"], fixture["message"]["checkB"])
                self.assertFalse(
                    any(clock.running for clock in game.gameClocks.stopwatches.values())
                )

    async def test_explicit_backend_replay_matches_previous_reader_exactly(self):
        for fixture in FIXTURES:
            with self.subTest(name=fixture["name"]):
                game = await self.load_fixture(fixture)
                first = game.get_board(full=True)
                self.assertEqual(first["steps"], fixture["expected"])
                self.assertEqual(first["fen"], fixture["message"]["fen"])
                game.ensure_steps()
                self.assertEqual(game.steps, fixture["expected"])
                self.assertNotIn("twoBoardHistory", game.get_board(full=True, client_history=True))

    async def test_active_restore_still_replays_on_server(self):
        fixture = FIXTURES[0]
        game = await self.load_fixture(fixture, s=STARTED, r="d", ts=[])
        try:
            self.assertEqual(len(game.steps), len(fixture["expected"]))
            self.assertEqual(game.fen, fixture["message"]["fen"])
            self.assertIsNone(game.display_history())
            self.assertFalse(game.saved)
            self.assertEqual(game.lastmovePerBoardAndUser["a"]["ab"], "P@e6")
        finally:
            await game.cancel_clocks_for_eviction()

    async def test_archive_without_final_fen_retains_readable_history(self):
        fixture = {**FIXTURES[0], "doc": dict(FIXTURES[0]["doc"])}
        fixture["doc"].pop("f")
        game = await self.load_fixture(fixture)
        self.assertEqual(game.steps, fixture["expected"])
        self.assertNotIn("twoBoardHistory", game.get_board(full=True, client_history=True))

    async def test_compact_timestamps_are_plain_ints(self):
        timestamps = [Int64(1700000000000000000 + index) for index in range(9)]
        game = await self.load_fixture(FIXTURES[0], ts=timestamps)
        board = game.get_board(full=True, client_history=True)
        for index, metadata in enumerate(board["twoBoardHistory"]["metadata"]):
            self.assertIs(type(metadata["ts"]), int)
            self.assertEqual(metadata["ts"], timestamps[index + 1])

    async def test_fishnet_result_hydrates_history_before_merging_analysis(self):
        game = await self.load_fixture(FIXTURES[0])
        self.state.games[game.id] = game
        self.state.fishnet_works["work1"] = {"game_id": game.id, "username": "aw"}
        self.state.fishnet_monitor["worker1"] = []
        self.state.users["aw"].send_game_message = AsyncMock()
        rows = [{"score": {"cp": index}, "depth": 20, "pv": ""} for index in range(9)]
        data = {"fishnet": {"apikey": "testkey"}, "analysis": rows}
        request = cast(web.Request, SimpleNamespace(match_info={"workId": "work1"}, app=self.app))
        with (
            patch.dict(fishnet.FISHNET_KEYS, {"testkey": "worker1"}, clear=True),
            patch("fishnet._read_fishnet_json", new=AsyncMock(return_value=(data, None))),
        ):
            response = await fishnet.fishnet_analysis(request)
        self.assertEqual(response.status, 204)
        self.assertEqual(len(game.steps), 9)
        self.assertEqual(game.steps[-1]["analysis"]["s"], {"cp": 8})
        self.assertEqual(game.steps[-1]["fenB"], FIXTURES[0]["expected"][-1]["fenB"])
        self.assertIsNone(game.display_history())
        self.assertNotIn("work1", self.state.fishnet_works)

    async def test_html_and_all_socket_seats_use_compact_history(self):
        game = await self.load_fixture(FIXTURES[0])
        self.state.games[game.id] = game
        with patch.object(FairyBoard, "push", side_effect=AssertionError("display replay")):
            for name in ("aw", "ab", "bw", "bb", "viewer"):
                user = self.state.users[name]
                context = {}
                add_game_context(game, None, user, context)
                self.assertIn("twoBoardHistory", json.loads(context["board"]))
                ws = AsyncMock()
                await init_ws(self.state, ws, user, game)
                messages = [json.loads(call.args[0]) for call in ws.send_str.await_args_list]
                board = next(message for message in messages if message["type"] == "board")
                self.assertIn("twoBoardHistory", board)
                user.remove_ws_for_game(game.id, ws)
