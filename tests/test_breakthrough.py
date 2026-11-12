from __future__ import annotations

import unittest

from catalogued.builtin_data import (
    FSF_CATALOGUED_BUILTIN_VARIANTS,
    FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES,
)
from catalogued.documents import (
    _build_fsf_builtin_doc,
    _client_doc,
    catalogued_variant_rule_context,
)
from fairy.fairy_board import sf
from study.engine import validated_study_position

INITIAL = "7p/7p/8/8/8/2Pp4/8/8 w - - 0 1"
MOVES = ["c3d4", "h7h6", "d4e5", "h6h5", "e5f6", "h5g4", "f6g7", "g4f3", "g7h8"]


class BreakthroughTestCase(unittest.TestCase):
    def test_catalogue_board_pieces_and_premove_rules(self):
        self.assertNotIn("breakthrough", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
        doc = _build_fsf_builtin_doc(
            "breakthrough", FSF_CATALOGUED_BUILTIN_VARIANTS["breakthrough"]
        )
        self.assertEqual((doc["width"], doc["height"]), (8, 8))
        self.assertEqual(doc["boardFamilyOverride"], "standard8x8")
        self.assertEqual(doc["pieceFamilyOverride"], "standard")
        self.assertEqual(doc["kingRoles"], [])
        self.assertEqual(doc["pocketRoles"], [])
        self.assertFalse(_client_doc(doc)["replayOnly"])
        self.assertEqual(_client_doc(doc)["betzaPieces"], {"p": "fmWfF"})
        self.assertIn("flagRegionWhite = *8", catalogued_variant_rule_context(doc)["ini"])

    def test_quiet_diagonals_capture_and_goal_without_promotion(self):
        board = validated_study_position(
            "breakthrough", INITIAL, chess960=False, show_promoted=False
        )
        for ply, move in enumerate(MOVES):
            with self.subTest(move=move):
                self.assertIn(move, board.legal_moves())
                board.push(move)
                self.assertEqual(board.is_immediate_game_end()[0], ply == len(MOVES) - 1)
        self.assertEqual(board.fen.split()[0], "7P/8/8/8/8/3p1p2/8/8")
        self.assertEqual(board.legal_moves(), [])
        self.assertLess(board.game_result(), 0)
        self.assertFalse(board.is_checked())

    def test_moves_are_forward_only_no_double_step_or_straight_capture(self):
        fen = "7p/8/8/3p4/3P4/8/8/8 w - - 0 1"
        self.assertEqual(set(sf.legal_moves("breakthrough", fen, [])), {"d4c5", "d4e5"})
        fen = "8/8/8/8/3p4/3P4/8/P7 b - - 0 1"
        self.assertEqual(set(sf.legal_moves("breakthrough", fen, [])), {"d4c3", "d4e3"})
        self.assertNotIn("a2a4", sf.legal_moves("breakthrough", sf.start_fen("breakthrough"), []))

    def test_black_goal_and_capturing_last_enemy_piece(self):
        for fen, move, immediate in (
            ("8/P7/8/8/8/8/7p/8 b - - 0 1", "h2h1", True),
            ("8/8/8/8/8/8/2p5/1P6 w - - 0 1", "b1c2", False),
        ):
            with self.subTest(move=move):
                self.assertIn(move, sf.legal_moves("breakthrough", fen, []))
                self.assertEqual(sf.legal_moves("breakthrough", fen, [move]), [])
                self.assertEqual(
                    sf.is_immediate_game_end("breakthrough", fen, [move])[0], immediate
                )
                self.assertLess(sf.game_result("breakthrough", fen, [move]), 0)
