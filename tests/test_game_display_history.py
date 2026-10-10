from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, PropertyMock, patch

from const import RESIGN, STARTED
from fairy.fairy_board import FairyBoard
from test_embassy_castling_pgn import CAPA_CASTLING_FEN, make_game
from views import add_game_context
from wsr import handle_analysis, handle_board


def archived_game(variant="chess", fen="", moves=("e2e4", "e7e5")):
    game = make_game("archive1", variant, fen)
    for move in moves:
        game.board.push(move)
    game.lastmove = moves[-1] if moves else None
    game.status = RESIGN
    game.result = "1-0"
    game.clocks_w = [600000, 599000]
    game.clocks_b = [600000, 598000]
    return game


class GameDisplayHistoryTestCase(unittest.TestCase):
    def test_finished_display_skips_all_step_engine_calls_and_keeps_pgn(self):
        game = archived_game()
        before = game.board.fen, list(game.board.move_stack), game.board.ply
        with (
            patch.object(game, "create_steps", side_effect=AssertionError("server replay")),
            patch.object(FairyBoard, "get_san", side_effect=AssertionError("server SAN")),
            patch.object(FairyBoard, "push", side_effect=AssertionError("server push")),
            patch.object(FairyBoard, "is_checked", side_effect=AssertionError("server check")),
        ):
            response = game.get_board(full=True, client_history=True)
        self.assertEqual(response["history"]["moves"], ["e2e4", "e7e5"])
        self.assertEqual(response["steps"], game.steps)
        self.assertEqual(len(game.steps), 1)
        self.assertIn("1. e4 e5", response["pgn"])
        self.assertEqual(response["fen"], game.board.fen)
        self.assertEqual(before, (game.board.fen, game.board.move_stack, game.board.ply))

    def test_backend_consumers_still_get_authoritative_steps(self):
        game = archived_game()
        response = game.get_board(full=True)
        self.assertNotIn("history", response)
        self.assertEqual(len(response["steps"]), 3)
        self.assertEqual(response["steps"][-1]["fen"], game.board.fen)

    def test_active_browser_snapshots_still_reconstruct_on_server(self):
        game = archived_game()
        game.status = STARTED
        game.board.ply = 1  # Avoid elapsed-clock adjustment in this isolated fixture.
        response = game.get_board(full=True, client_history=True)
        self.assertNotIn("history", response)
        self.assertEqual(len(response["steps"]), 3)

    def test_cached_steps_supply_latest_analysis_without_sending_positions(self):
        game = archived_game()
        game.ensure_steps()
        game.analysis = [{"s": {"cp": 1}}]
        game.steps[1]["analysis"] = {"s": {"cp": 30}}
        response = game.get_board(full=True, client_history=True)
        self.assertEqual(len(response["steps"]), 1)
        self.assertIsNot(response["steps"][0], game.steps[0])
        self.assertEqual(response["history"]["analysis"][1], {"s": {"cp": 30}})

    def test_stored_analysis_and_pgn_advice_survive_without_steps(self):
        game = archived_game()
        game.analysis = [
            {"s": {"cp": 0}},
            {"s": {"cp": 10}},
            {
                "s": {"cp": 200},
                "advice": {"nag": 4, "comment": "Blunder.", "variation": []},
            },
        ]
        response = game.get_board(full=True, client_history=True)
        self.assertEqual(response["history"]["analysis"], game.analysis)
        self.assertIn("e5 $4 {Blunder.}", response["pgn"])
        self.assertEqual(len(game.steps), 1)

    def test_legacy_castling_selects_original_rules(self):
        for move, expected in (("e8i8", "capablanca"), ("e8b8", "embassy")):
            with self.subTest(move=move):
                game = make_game("archive1", "capablanca", CAPA_CASTLING_FEN)
                game.board.move_stack = [move]
                self.assertEqual(game.display_history()["variant"], expected)

    def test_clock_history_is_only_sent_for_realtime_games(self):
        game = archived_game()
        self.assertEqual(game.display_history()["clocksWhite"], game.clocks_w)
        self.assertEqual(game.display_history()["clocksBlack"], game.clocks_b)
        game.corr = True
        self.assertNotIn("clocksWhite", game.display_history())

    def test_counting_intervals_cover_loaded_and_cached_games(self):
        game = make_game("archive1", "makruk", "")
        game.mct = [(3, 6)]
        self.assertEqual(game.display_history()["countIntervals"], [(3, 6)])
        game.mct = None
        game.manual_count_toggled = [(3, 6)]
        game.board.count_started = 8
        game.board.ply = 10
        self.assertEqual(game.display_history()["countIntervals"], [(3, 6), (8, 11)])

    def test_old_usi_analysis_only_keeps_root_as_before(self):
        game = archived_game()
        game.usi_format = True
        game.analysis = [{"s": {"cp": 0}}, {"s": {"cp": 100}}]
        self.assertTrue(game.display_history()["usi"])
        self.assertEqual(game.display_history()["analysis"], game.analysis[:1])

    def test_jieqi_mapping_only_sent_in_finished_browser_history(self):
        game = make_game("archive1", "jieqi", "")
        game.status = RESIGN
        response = game.get_board(full=True, client_history=True)
        self.assertEqual(
            response["history"]["jieqiCovered"], game.board.jieqi_initial_covered_pieces
        )
        game.status = STARTED
        self.assertNotIn("history", game.get_board(full=True, client_history=True))

    def test_long_display_history_does_not_trigger_reconstruction(self):
        game = archived_game()
        game.board.move_stack = ["g1f3", "g8f6", "f3g1", "f6g8"] * 200
        with (
            patch.object(game, "create_steps", side_effect=AssertionError("server replay")),
            patch.object(type(game), "pgn", new_callable=PropertyMock, return_value="PGN"),
        ):
            response = game.get_board(full=True, client_history=True)
        self.assertEqual(len(response["history"]["moves"]), 800)
        self.assertEqual(len(game.steps), 1)


class GameDisplayHistoryTransportTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_server_analysis_materializes_positions_on_demand(self):
        game = archived_game()
        app_state = SimpleNamespace(
            games={game.id: game}, fishnet_works={}, fishnet_queue=asyncio.PriorityQueue()
        )
        with (
            patch("wsr.drop_stale_analysis_work", return_value=0),
            patch("wsr.has_available_fishnet_worker", return_value=True),
            patch("wsr.catalogued_variant_allows_fishnet", return_value=True),
            patch("wsr.ws_send_json", new=AsyncMock()),
        ):
            await handle_analysis(
                app_state, AsyncMock(), {"gameId": game.id, "username": "viewer"}, game
            )
        self.assertEqual(len(game.steps), 3)
        self.assertEqual(len(app_state.fishnet_works), 1)

    async def test_html_and_round_socket_both_send_compact_history(self):
        for variant, fen, moves in (
            ("chess", "", ("e2e4", "e7e5")),
            ("janggi", "", ("a4a5", "a7a6")),
        ):
            with self.subTest(variant=variant):
                game = archived_game(variant, fen, moves)
                context = {}
                user = SimpleNamespace(username="spectator")
                ws = AsyncMock()
                with patch.object(
                    game, "create_steps", side_effect=AssertionError("server replay")
                ):
                    add_game_context(game, None, user, context)
                    await handle_board(ws, user, game)
                html = json.loads(context["board"])
                socket = json.loads(ws.send_str.await_args.args[0])
                self.assertEqual(html, socket)
                self.assertEqual(html["history"]["moves"], list(moves))


if __name__ == "__main__":
    unittest.main()
