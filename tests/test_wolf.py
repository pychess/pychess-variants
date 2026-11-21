from __future__ import annotations

import unittest

from catalogued.builtin_data import (
    FSF_CATALOGUED_BUILTIN_VARIANTS,
    FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES,
)
from catalogued.documents import _build_fsf_builtin_doc, _client_doc
from fairy.fairy_board import FairyBoard, sf
from study.engine import validated_study_position


class WolfTestCase(unittest.TestCase):
    def test_native_metadata_and_piece_definitions(self):
        self.assertNotIn("wolf", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
        doc = _build_fsf_builtin_doc("wolf", FSF_CATALOGUED_BUILTIN_VARIANTS["wolf"])
        self.assertEqual((doc["width"], doc["height"]), (8, 10))
        self.assertEqual(doc["pieceFamilyOverride"], "wolf")
        self.assertIn("+p", doc["pieces"])
        self.assertEqual(doc["promotionRoles"], ["p", "s"])
        self.assertEqual(doc["promotionOrder"], ["q", "w", "f", "r", "b", "+"])
        self.assertEqual(doc["promotionType"], "regular")
        client = _client_doc(doc)
        self.assertFalse(client["replayOnly"])
        self.assertEqual(
            {p: client["betzaPieces"][p] for p in ("w", "f", "s", "n", "+p")},
            {"w": "RN", "f": "BN", "s": "fKifmnD", "n": "NN", "+p": "NNQ"},
        )

    def test_promotions_for_both_piece_types_and_colors_round_trip(self):
        for color in ("w", "b"):
            for letter in ("p", "s"):
                piece = letter.upper() if color == "w" else letter
                fen = (
                    f"7k/{piece}7/8/8/8/8/8/8/8/7K w - - 0 1"
                    if color == "w"
                    else f"7k/8/8/8/8/8/8/8/{piece}7/7K b - - 0 1"
                )
                orig, dest = ("a9", "a10") if color == "w" else ("a2", "a1")
                moves = sf.legal_moves("wolf", fen, [])
                suffixes = {m[len(orig + dest) :] for m in moves if m.startswith(orig + dest)}
                self.assertEqual(suffixes, set("qwfrb") | ({"+"} if letter == "p" else set()))
                for suffix in suffixes:
                    with self.subTest(color=color, piece=letter, suffix=suffix):
                        board = validated_study_position(
                            "wolf", fen, chess960=False, show_promoted=False
                        )
                        board.push(orig + dest + suffix)
                        checked = validated_study_position(
                            "wolf", board.fen, chess960=False, show_promoted=False
                        )
                        self.assertEqual(board.legal_moves(), checked.legal_moves())
                        if suffix == "+":
                            self.assertIn("+" + piece, board.fen)
                        board.pop()
                        self.assertEqual(board.fen, fen)

    def test_staggered_pawn_double_step_and_sergeant_quiet_diagonal(self):
        moves = set(sf.legal_moves("wolf", sf.start_fen("wolf"), []))
        for move in ("a2a4", "b3b5", "c3c5", "d2d4", "e2e4", "f3f5", "g3g5", "h2h4"):
            self.assertIn(move, moves)
        for piece in ("p", "s"):
            fen = f"7k/8/8/8/8/2{piece}5/8/1P6/8/7K w - - 0 1"
            board = FairyBoard("wolf", initial_fen=fen)
            board.push("b3b5")
            self.assertIn("c5b4", board.legal_moves())
            board.push("c5b4")
            self.assertEqual("1P6" in board.fen, piece == "s")
