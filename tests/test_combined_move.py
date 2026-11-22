from __future__ import annotations

import unittest
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import AsyncMock, PropertyMock, patch

import pyffish as sf
import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from const import INVALIDMOVE, STARTED
from fairy.fairy_board import BLACK, WHITE, FairyBoard, MoveResult
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import play_move
from variants import (
    VARIANTS,
    ServerVariants,
    register_catalogued_server_variant,
    unregister_catalogued_server_variant,
)

from server import make_app

test_logger.init_test_logger()

NATIVE_APPLY_MOVE = getattr(sf, "apply_move", None)


@unittest.skipUnless(NATIVE_APPLY_MOVE is not None, "requires pyffish.apply_move")
class CombinedBoardMoveTestCase(unittest.TestCase):
    def compare_move(self, board: FairyBoard, move: str) -> MoveResult:
        before = board.fen, board.color, board.ply, list(board.move_stack)
        result = board.prepare_move(move)
        self.assertEqual(before, (board.fen, board.color, board.ply, board.move_stack))
        san = board.get_san(move)
        board.push(move)
        moves = board.legal_moves()
        immediate = board.is_immediate_game_end()
        optional = board.is_optional_game_end()
        expected = MoveResult(
            san,
            board.fen,
            board.is_checked(),
            bool(moves),
            moves,
            board.insufficient_material(),
            (immediate[0], immediate[1] if immediate[0] else 0),
            (optional[0], optional[1] if optional[0] else 0),
            board.game_result() if not moves else None,
        )
        self.assertEqual(result, expected)
        return result

    def test_site_variants_match_existing_queries(self):
        for variant in ServerVariants:
            if variant.two_boards or variant.chess960 or variant.uci_variant in ("alice", "jieqi"):
                continue
            board = FairyBoard(
                variant.server_name,
                show_promoted=variant.show_promoted,
                legal_moves_need_history=variant.legal_moves_need_history,
            )
            for ply in range(3):
                moves = board.legal_moves()
                if not moves:
                    break
                with self.subTest(variant=variant.server_name, ply=ply):
                    self.compare_move(board, moves[0])

    def test_special_moves_and_game_endings_match_existing_queries(self):
        cases = (
            ("chess", "", ["e2e4", "a7a6", "e4e5", "d7d5"], "e5d6", False),
            ("chess", "7k/P7/8/8/8/8/8/7K w - - 0 1", [], "a7a8q", False),
            ("chess", "", ["f2f3", "e7e5", "g2g4"], "d8h4", False),
            ("chess", "7k/5K2/4Q3/8/8/8/8/8 w - - 0 1", [], "e6g6", False),
            ("chess", "7k/8/8/n7/8/2B5/8/K7 w - - 0 1", [], "c3a5", False),
            ("chess", "4k3/8/8/8/8/8/8/R1K4R w HA - 0 1", [], "c1h1", True),
            ("chess", "", ["g1f3", "g8f6", "f3g1", "f6g8"] * 100, "g1f3", False),
            ("chess", "7k/8/8/8/8/8/8/KR6 w - - 99 50", [], "b1b2", False),
            ("crazyhouse", "7k/8/8/8/8/8/8/K7[N] w - - 0 1", [], "N@f7", False),
            ("crazyhouse", "7k/8/8/8/8/2q~5/1B6/K7[] w - - 0 1", [], "b2c3", False),
            (
                "capablanca",
                "rk7r/1pp2P1ppp/p7c1/3NPCP1b1/3P3p2/8P1/PPP4B1P/R3K2R2 w Q - 0 29",
                [],
                "e1b1",
                False,
            ),
            ("atomic", "B6Q/Rk6/8/8/8/8/8/4K3 w - - 0 1", [], "h8b8", False),
            ("dobutsu", "1L1/1g1/1G1/1l1[] w - - 0 1", [], "b2a2", False),
        )
        for variant, fen, history, move, chess960 in cases:
            with self.subTest(variant=variant, move=move):
                board = FairyBoard(variant, fen, chess960=chess960, show_promoted=True)
                board.move_stack = list(history)
                board.ply = len(history)
                board.fen = board.sf.get_fen(
                    board.variant, board.initial_fen, history, chess960, False, True
                )
                board.color = BLACK if board.fen.split()[1] == "b" else WHITE
                self.compare_move(board, move)

    def test_counting_toggles_preserve_incremental_counters(self):
        cases = (
            ("makruk", "3k4/2m5/5M~2/4M3/3KS3/8/8/8 w - 128 7 33"),
            ("cambodian", "8/2K3k1/5m2/4S1S1/8/8/8/8 w - 126 101 80"),
        )
        for variant, fen in cases:
            board = FairyBoard(variant, fen)
            for count_started in (-1, -1, 3, 3, -1, -1, 7, 7, 0, 0):
                with self.subTest(variant=variant, count_started=count_started, ply=board.ply):
                    board.count_started = count_started
                    self.compare_move(board, board.legal_moves()[0])

    def test_custom_history_dependent_legality_is_preserved(self):
        name = "combined_janggi_test"
        sf.load_variant_config(f"[{name}:janggi]\n")
        register_catalogued_server_variant(name, name, legal_moves_need_history=True)
        self.addCleanup(unregister_catalogued_server_variant, name)
        board = FairyBoard(name, legal_moves_need_history=True)
        for move in ("e2e3", "e9e8", "e3d3"):
            self.compare_move(board, move)
        self.compare_move(board, board.legal_moves()[0])
        before = board.fen, list(board.move_stack), board.ply
        with self.assertRaises(ValueError):
            board.prepare_move("a1a10")
        self.assertEqual(before, (board.fen, board.move_stack, board.ply))

    def test_takeback_does_not_reuse_move_facts(self):
        board = FairyBoard("chess")
        for move in ("e2e4", "e7e5", "g1f3"):
            board.push(move, move_result=board.prepare_move(move))
        board.pop()
        self.compare_move(board, "f1c4")


@unittest.skipUnless(NATIVE_APPLY_MOVE is not None, "requires pyffish.apply_move")
class CombinedGameMoveTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    def make_game(self, variant="chess", fen="", *, random_mover=False):
        state = get_app_state(self.app)
        perfs = new_default_perf_map(VARIANTS)
        white = User(state, username="combined-white", perfs=perfs)
        black = User(state, username="combined-black", perfs=perfs)
        if random_mover:
            black.title = "TEST"
        game = Game(state, "combined1", variant, fen, white, black, rated=False)
        game.save_move = AsyncMock()
        game.save_game = AsyncMock()
        self.addAsyncCleanup(game.cancel_clocks_for_eviction)
        return game

    def state(self, game):
        return deepcopy(
            (
                game.board.fen,
                game.board.color,
                game.ply,
                game.board.move_stack,
                game.lastmove,
                game.steps,
                game.status,
                game.result,
                game.check,
                game.has_legal_move,
                game.clocks_w,
                game.clocks_b,
            )
        )

    async def test_human_move_uses_one_combined_query_and_caches_legal_replies(self):
        game = self.make_game()
        await game.play_move("e2e4", [600000, 600000])
        await game.play_move("e7e5", [600000, 600000])
        expected_fen = sf.get_fen("chess", game.board.initial_fen, ["e2e4", "e7e5", "g1f3"])
        expected_moves = tuple(sf.legal_moves("chess", expected_fen, []))
        assert NATIVE_APPLY_MOVE is not None

        def apply_move(*args):
            self.assertEqual(args[2], ["e2e4", "e7e5"])
            return NATIVE_APPLY_MOVE(*args)

        with ExitStack() as stack:
            combined = stack.enter_context(patch.object(sf, "apply_move", side_effect=apply_move))
            for method in (
                "get_san",
                "get_fen",
                "legal_moves",
                "gives_check",
                "has_insufficient_material",
                "is_immediate_game_end",
                "is_optional_game_end",
                "game_result",
            ):
                stack.enter_context(patch.object(sf, method, side_effect=AssertionError(method)))
            await play_move(
                get_app_state(self.app), game.wplayer, game, "g1f3", [599000, 600000], ply=3
            )
            self.assertEqual(game.legal_moves, expected_moves)
        combined.assert_called_once_with(
            game.board.variant,
            game.board.initial_fen,
            game.board.move_stack,
            "g1f3",
            False,
            game.board.notation,
            False,
            game.board.show_promoted,
            0,
            True,
        )
        self.assertEqual(game.ply, 3)
        self.assertEqual(game.steps[-1]["san"], "Nf3")
        self.assertEqual(game.status, STARTED)

    async def test_random_mover_reuses_the_requested_legal_move_list(self):
        game = self.make_game(random_mover=True)
        expected_fen = sf.get_fen("chess", game.board.initial_fen, ["e2e4"])
        expected_moves = sf.legal_moves("chess", expected_fen, [])
        with (
            patch.object(sf, "apply_move", wraps=NATIVE_APPLY_MOVE) as combined,
            patch.object(sf, "legal_moves", side_effect=AssertionError("duplicate legal query")),
        ):
            await game.play_move("e2e4", [600000, 600000])
            self.assertEqual(game.legal_moves, tuple(expected_moves))
        self.assertEqual(combined.call_count, 1)
        self.assertTrue(combined.call_args.args[-1])

    async def test_illegal_human_move_leaves_clocks_offers_and_board_untouched(self):
        game = self.make_game()
        await game.play_move("e2e4", [600000, 600000])
        await game.play_move("e7e5", [600000, 600000])
        game.draw_offers.add(game.bplayer.username)
        game.takeback_offer = game.bplayer.username, game.ply
        before = self.state(game), list(game.clocks_w), list(game.clocks_b), game.last_server_clock
        game.wplayer.send_game_message = AsyncMock()
        await play_move(get_app_state(self.app), game.wplayer, game, "e4e7", [1, 1], ply=3)
        self.assertEqual(
            before, (self.state(game), game.clocks_w, game.clocks_b, game.last_server_clock)
        )
        self.assertEqual(game.draw_offers, {game.bplayer.username})
        self.assertIsNotNone(game.takeback_offer)
        self.assertTrue(game.stopwatch.running)
        self.assertEqual(game.wplayer.send_game_message.await_args.args[1]["type"], "board")

    async def test_native_input_aliases_remain_rejected_for_human_moves(self):
        for fen, move in (("", "e2e4="), ("7k/P7/8/8/8/8/8/7K w - - 0 1", "a7a8Q")):
            with self.subTest(move=move):
                game = self.make_game(fen=fen)
                await play_move(
                    get_app_state(self.app), game.wplayer, game, move, [600000, 600000], ply=1
                )
                self.assertEqual(game.ply, 0)
                self.assertNotEqual(game.status, INVALIDMOVE)

    async def test_game_results_and_steps_match_the_existing_move_path(self):
        janggi_moves = [
            "e2e3",
            "e9f9",
            "h3d3",
            "e7f7",
            "i1i3",
            "h10i8",
            "i3h3",
            "c10e7",
            "h3h8",
            "i10i9",
            "h8b8",
            "i9g9",
            "d3f3",
            "f9e9",
            "f3f10",
            "e7c10",
            "f10c10",
            "b10c8",
            "c10g10",
            "g9f9",
            "b8c8",
            "a10b10",
            "b3f3",
            "f9h9",
            "a1a2",
            "h9f9",
            "a2d2",
            "b10b9",
            "d2d10",
            "e9d10",
            "c8c10",
            "d10d9",
            "f3f9",
            "i8g9",
            "f9b9",
            "a7a6",
            "g10g7",
            "f7f6",
            "e4e5",
            "c7d7",
            "g1e4",
            "i7i6",
            "e4b6",
            "d9d8",
            "c10c8",
            "d8d9",
            "b9g9",
            "d7d6",
            "b6e8",
            "i6h6",
            "e5e6",
            "f6e6",
            "c1e4",
            "a6b6",
            "e4b6",
            "d6d5",
            "c4c5",
            "d9d10",
            "e3d3",
            "h6i6",
            "c5c6",
            "d5c5",
            "d3d3",
        ]
        cases = (
            ("chess", "", ("f2f3", "e7e5", "g2g4", "d8h4")),
            ("chess", "7k/5K2/4Q3/8/8/8/8/8 w - - 0 1", ("e6g6",)),
            ("atomic", "B6Q/Rk6/8/8/8/8/8/4K3 w - - 0 1", ("h8b8",)),
            ("dobutsu", "1L1/1g1/1G1/1l1[] w - - 0 1", ("b2a2",)),
            ("shogi", "", ("c3c4", "c7c6")),
            ("ataxx", sf.start_fen("ataxx"), ("g1e1", "a1c1")),
            ("janggi", sf.start_fen("janggi"), janggi_moves),
        )
        for variant, fen, moves in cases:
            with self.subTest(variant=variant, fen=fen):
                current = self.make_game(variant, fen)
                legacy = self.make_game(variant, fen)
                for move in moves:
                    await current.play_move(move, [600000, 600000])
                    with patch.object(
                        FairyBoard,
                        "supports_combined_move",
                        new_callable=PropertyMock,
                        return_value=False,
                    ):
                        await legacy.play_move(move, [600000, 600000])
                    self.assertEqual(self.state(current), self.state(legacy))

    async def test_manual_count_start_stop_and_restart_match_the_existing_move_path(self):
        fen = "3k4/2m5/5M~2/4M3/3KS3/8/8/8 w - 128 7 33"
        current = self.make_game("makruk", fen)
        legacy = self.make_game("makruk", fen)
        for ply in range(8):
            if ply in (0, 4):
                current.start_manual_count()
                legacy.start_manual_count()
            elif ply == 2:
                current.stop_manual_count()
                legacy.stop_manual_count()
            move = legacy.board.legal_moves()[0]
            await current.play_move(move, [600000, 600000])
            with patch.object(
                FairyBoard, "supports_combined_move", new_callable=PropertyMock, return_value=False
            ):
                await legacy.play_move(move, [600000, 600000])
            self.assertEqual(self.state(current), self.state(legacy))
            self.assertEqual(current.manual_count_toggled, legacy.manual_count_toggled)
            self.assertEqual(current.draw_offers, legacy.draw_offers)

    async def test_custom_repetition_uses_history_and_existing_draw_policy(self):
        name = "combined_repetition_test"
        sf.load_variant_config(f"[{name}:chess]\nnFoldRule = 3\n")
        register_catalogued_server_variant(name, name, n_fold_is_draw=True)
        self.addCleanup(unregister_catalogued_server_variant, name)
        current = self.make_game(name)
        legacy = self.make_game(name)
        for move in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
            await current.play_move(move, [600000, 600000])
            with patch.object(
                FairyBoard, "supports_combined_move", new_callable=PropertyMock, return_value=False
            ):
                await legacy.play_move(move, [600000, 600000])
            self.assertEqual(self.state(current), self.state(legacy))
        self.assertEqual(current.result, "1/2-1/2")
        self.assertGreater(current.status, STARTED)

    async def test_alice_and_jieqi_keep_their_special_move_paths(self):
        for variant, move in (("alice", "e2e4"), ("jieqi", "a4a5")):
            with self.subTest(variant=variant):
                game = self.make_game(variant)
                with patch.object(sf, "apply_move", side_effect=AssertionError("special variant")):
                    await game.play_move(move, [600000, 600000])
                self.assertEqual(game.ply, 1)
                self.assertNotEqual(game.status, INVALIDMOVE)
