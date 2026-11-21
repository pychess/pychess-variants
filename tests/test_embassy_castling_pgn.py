from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import test_logger
from compress import R2C
from const import MATE, STARTED
from fairy.fairy_board import FairyBoard
from game import Game
from glicko2.glicko2 import new_default_perf_map
from user import User
from utils import pgn as export_pgn
from variants import VARIANTS, get_server_variant

test_logger.init_test_logger()


CAPA_CASTLING_FEN = "r3k4r/10/10/10/10/10/10/R3K4R b KQkq - 0 1"
PERFS = new_default_perf_map(VARIANTS)


def make_export_doc(move: str) -> dict:
    encode = get_server_variant("capablanca", False).move_encoding
    return {
        "_id": "embassy-test",
        "v": "c",
        "m": [encode(move)],
        "if": CAPA_CASTLING_FEN,
        "d": datetime(2026, 2, 18, tzinfo=UTC),
        "us": ["White", "Black"],
        "r": R2C["*"],
        "b": 10,
        "i": 0,
        "p0": {"e": "1500?"},
        "p1": {"e": "1500?"},
    }


def make_game(game_id: str, variant: str, initial_fen: str, *, corr: bool = False) -> Game:
    app_state = SimpleNamespace(anon_as_test_users=False)
    wplayer = User(app_state, username="White", perfs=PERFS)
    bplayer = User(app_state, username="Black", perfs=PERFS)
    with (
        patch("game.Clock", return_value=SimpleNamespace()),
        patch("game.CorrClock", return_value=SimpleNamespace()),
    ):
        game = Game(
            app_state,
            game_id,
            variant,
            initial_fen,
            wplayer,
            bplayer,
            base=10,
            inc=0,
            rated=False,
            chess960=False,
            corr=corr,
        )
    game.date = datetime(2026, 2, 18, tzinfo=UTC)
    return game


def make_game_for_pgn(move: str) -> Game:
    game = make_game("embassy-game", "capablanca", CAPA_CASTLING_FEN)
    game.board = SimpleNamespace(initial_fen=CAPA_CASTLING_FEN, move_stack=[move])
    return game


class EmbassyCastlingPgnTestCase(unittest.TestCase):
    def test_create_steps_replays_legacy_capablanca_castling_coordinate(self) -> None:
        game = make_game("embassy-replay", "capablanca", CAPA_CASTLING_FEN, corr=True)
        game.steps = []
        game.clocks_w = [0]
        game.clocks_b = [0]
        game.loaded_at = None
        game.status = MATE

        game.board = FairyBoard("capablanca", CAPA_CASTLING_FEN, chess960=False)
        self.assertEqual("embassy", game.board.variant)
        game.board.move_stack = ["e8i8", "a1a2", "h8e8"]
        game.board.fen = CAPA_CASTLING_FEN
        game.board.color = 1  # black to move

        game.create_steps()

        self.assertEqual(3, len(game.steps))
        self.assertEqual("e8i8", game.steps[0]["move"])
        self.assertEqual("h8e8", game.steps[2]["move"])

    def test_create_steps_downgrades_historical_replay_failures(self) -> None:
        game = make_game("legacy-replay", "chess", "", corr=True)
        game.steps = []
        game.clocks_w = [0]
        game.clocks_b = [0]
        game.date = datetime(2025, 1, 1, tzinfo=UTC)
        game.loaded_at = datetime(2026, 4, 1, tzinfo=UTC)
        game.status = MATE

        game.board = FairyBoard("chess")
        game.board.move_stack = ["e2e4", "e2e4"]

        with (
            patch("game.log.warning") as mock_warning,
            patch("game.log.exception") as mock_exception,
        ):
            game.create_steps()

        self.assertEqual(1, len(game.steps))
        self.assertEqual("e2e4", game.steps[0]["move"])
        mock_warning.assert_called_once()
        mock_exception.assert_not_called()

    def test_create_steps_never_mutates_live_board_on_invalid_history(self) -> None:
        game = make_game("current-corrupt-replay", "chess", "", corr=True)
        game.steps = []
        game.clocks_w = [0]
        game.clocks_b = [0]
        game.loaded_at = datetime(2026, 7, 30, tzinfo=UTC)
        game.status = STARTED

        valid_board = FairyBoard("chess")
        valid_board.push("e2e4")
        game.board = FairyBoard("chess")
        game.board.move_stack = ["e2e4", "e2e4"]
        game.board.fen = valid_board.fen
        game.board.ply = 2
        game.board.color = valid_board.color
        before = (
            game.board.fen,
            game.board.color,
            game.board.ply,
            list(game.board.move_stack),
        )

        with patch("game.log.exception"):
            game.create_steps()

        self.assertEqual(
            before,
            (
                game.board.fen,
                game.board.color,
                game.board.ply,
                game.board.move_stack,
            ),
        )

    def test_export_pgn_fallback_accepts_modern_embassy_castling(self) -> None:
        # In current games the move can be embassy-style (e8b8) even if stored variant is capablanca.
        with patch("utils.log.error") as error:
            pgn_text = export_pgn(make_export_doc("e8b8"))
        error.assert_not_called()
        self.assertIsNotNone(pgn_text)
        assert pgn_text is not None
        self.assertIn("O-O-O", pgn_text)
        self.assertNotIn("e8b8", pgn_text)

    def test_export_pgn_keeps_legacy_capablanca_castling(self) -> None:
        # Older games can still contain historical capablanca castling coordinate e8c8.
        pgn_text = export_pgn(make_export_doc("e8c8"))
        self.assertIsNotNone(pgn_text)
        assert pgn_text is not None
        self.assertIn("O-O-O", pgn_text)
        self.assertNotIn("e8c8", pgn_text)

    def test_game_pgn_fallback_accepts_modern_embassy_castling(self) -> None:
        pgn_text = make_game_for_pgn("e8b8").pgn
        self.assertIn("O-O-O", pgn_text)
        self.assertNotIn("e8b8", pgn_text)

    def test_game_pgn_falls_back_to_raw_move_when_castling_is_invalid(self) -> None:
        # Invalid in both capablanca and embassy; PGN should still be generated from raw move list.
        pgn_text = make_game_for_pgn("e8a8").pgn
        self.assertIn("e8a8", pgn_text)
        self.assertNotIn("O-O-O", pgn_text)

    def test_game_pgn_uses_board_initial_fen_when_initial_fen_is_empty(self) -> None:
        game = make_game_for_pgn("e8b8")
        game.variant = "janggi"
        game.initial_fen = ""
        board_fen = "rnba1anbr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RNBA1ANBR w - - 0 1"
        game.board = SimpleNamespace(initial_fen=board_fen, move_stack=["h1f3"])
        with patch("game.get_san_moves", return_value=["Hf3"]) as mocked_get_san:
            _ = game.pgn

        call_args = mocked_get_san.call_args.args
        self.assertEqual(call_args[0], "janggi")
        self.assertEqual(call_args[1], board_fen)
        self.assertEqual(call_args[2], ["h1f3"])

    def test_game_pgn_falls_back_to_trimmed_move_list_when_full_list_fails(self) -> None:
        game = make_game_for_pgn("e8b8")
        game.variant = "janggi"
        game.initial_fen = ""
        board_fen = "rnba1anbr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RNBA1ANBR w - - 0 1"
        moves = ["h1f3", "i7i7"]
        game.board = SimpleNamespace(initial_fen=board_fen, move_stack=moves)

        def fake_get_san_moves(_variant, _fen, mlist, _chess960, _notation):
            if mlist == moves:
                raise ValueError("invalid trailing move")
            return ["Hf3"]

        with patch("game.get_san_moves", side_effect=fake_get_san_moves):
            pgn_text = game.pgn

        self.assertIn("1. Hf3 *", pgn_text)
        self.assertNotIn("h1f3", pgn_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
