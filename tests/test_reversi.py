from __future__ import annotations

import unittest

from catalogued.builtin_data import (
    FSF_CATALOGUED_BUILTIN_VARIANTS,
    FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES,
)
from catalogued.documents import _build_fsf_builtin_doc, _client_doc
from fairy.fairy_board import sf
from study.engine import validated_study_position
from utils import pocket_variant_material_fits_engine


class ReversiTestCase(unittest.TestCase):
    def test_catalogued_native_positions_and_reachable_study_positions(self):
        for name in ("flipello", "flipello10", "flipersi"):
            with self.subTest(name=name):
                doc = _build_fsf_builtin_doc(name, FSF_CATALOGUED_BUILTIN_VARIANTS[name])
                self.assertNotIn(name, FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
                self.assertEqual(doc["pieceFamilyOverride"], "ataxx")
                self.assertEqual(doc["kingRoles"], [])
                self.assertEqual(doc["pocketRoles"], ["p"])
                self.assertFalse(doc["captureToHand"])
                self.assertEqual(doc["rulesPass"], name != "flipersi")
                self.assertFalse(_client_doc(doc)["replayOnly"])
                self.assertEqual(_client_doc(doc)["betzaPieces"], {"p": ""})
                start = sf.start_fen(name)
                self.assertTrue(pocket_variant_material_fits_engine(start, start, name))
                self.assertFalse(pocket_variant_material_fits_engine(start, start))
                for piece in ("P", "p"):
                    self.assertFalse(
                        pocket_variant_material_fits_engine(
                            start.replace("[", "[" + piece), start, name
                        )
                    )
                board = validated_study_position(name, start, chess960=False, show_promoted=False)
                board.push(board.legal_moves()[0])
                checked = validated_study_position(
                    name, board.fen, chess960=False, show_promoted=False
                )
                self.assertEqual(checked.legal_moves(), board.legal_moves())

    def test_native_pass_and_material_majority(self):
        for name in ("flipello", "flipello10", "flipersi"):
            with self.subTest(name=name):
                size = 10 if name == "flipello10" else 8
                rows = ["p" * size] * (size - 2) + [
                    "pp1" + "p" * (size - 3),
                    "Pp1" + "p" * (size - 3),
                ]
                fen = "/".join(rows) + "[Pp] b - - 0 1"
                moves = []
                if name != "flipersi":
                    self.assertEqual(sf.legal_moves(name, fen, moves), ["b1b1"])
                    moves.append("b1b1")
                    self.assertEqual(sf.legal_moves(name, fen, moves), ["P@c1"])
                    moves.extend(["P@c1", "d1d1", "a1a1"])
                self.assertEqual(sf.legal_moves(name, fen, moves), [])
                self.assertGreater(sf.game_result(name, fen, moves), 0)

    def test_full_board_scores_even_with_unused_reserves(self):
        for name in ("flipello", "flipello10", "flipersi"):
            with self.subTest(name=name):
                size = 10 if name == "flipello10" else 8
                fen = (
                    "/".join(["P" + "p" * (size - 1)] + ["p" * size] * (size - 1))
                    + "[Pp] w - - 0 1"
                )
                self.assertLess(sf.game_result(name, fen, []), 0)
                self.assertTrue(sf.is_immediate_game_end(name, fen, [])[0])

    def test_full_board_draw(self):
        for name in ("flipello", "flipello10", "flipersi"):
            with self.subTest(name=name):
                size = 10 if name == "flipello10" else 8
                fen = (
                    "/".join(["P" * size] * (size // 2) + ["p" * size] * (size // 2))
                    + "[Pp] w - - 0 1"
                )
                self.assertEqual(sf.game_result(name, fen, []), 0)
                self.assertEqual(sf.is_immediate_game_end(name, fen, []), (True, 0))
