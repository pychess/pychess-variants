from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import ClassVar
from unittest.mock import patch

import test_logger
from compress import R2C
from convert import grand2zero
from fairy import JIEQI_FEN
from test_embassy_castling_pgn import make_game
from utils import pgn
from variants import get_server_variant

test_logger.init_test_logger()


class JieqiPgnTestCase(unittest.TestCase):
    # Game KcU1f3vt: reveal suffixes are part of stored coordinates, including
    # moves to/from rank 10. A revealed rook later moves without a suffix.
    moves: ClassVar[list[str]] = [
        "b3b7c",
        "h8h4p",
        "h3h10c",
        "i10h10n",
        "g4g5r",
        "e7e6n",
        "g5e5",
        "g10e8a",
    ]

    def make_doc(self, moves: list[str]) -> dict:
        encode = get_server_variant("jieqi", False).move_encoding
        return {
            "_id": "jieqi-export-test",
            "v": "V",
            "m": [encode(grand2zero(move)) for move in moves],
            "d": datetime(2026, 10, 29, tzinfo=UTC),
            "us": ["White", "Black"],
            "r": R2C["1-0"],
            "b": 10,
            "i": 0,
            "bj": "cprprabnppcpnba",
            "wj": "NPRRBCCPBAPNPPA",
        }

    def test_database_export_preserves_all_coordinates_without_san_errors(self):
        for moves in (self.moves[:1], self.moves):
            with (
                self.subTest(plies=len(moves)),
                patch("utils.get_san_moves", side_effect=AssertionError("Jieqi needs reveals")),
                patch("utils.log.error") as error,
            ):
                exported = pgn(self.make_doc(moves))
                assert exported is not None
                expected = " ".join(
                    f"{index // 2 + 1}. {move}" if index % 2 == 0 else move
                    for index, move in enumerate(moves)
                )
                self.assertEqual(f"{expected} 1-0", exported.splitlines()[-1])
                self.assertIn(f'[FEN "{JIEQI_FEN}"]', exported)
                error.assert_not_called()

    def test_database_and_game_exports_have_the_same_jieqi_movetext(self):
        game = make_game("jieqi-export-test", "jieqi", "")
        game.board.move_stack = list(self.moves)
        game.result = "1-0"

        exported = pgn(self.make_doc(self.moves))
        assert exported is not None
        self.assertEqual(game.pgn.splitlines()[-1], exported.splitlines()[-1])
