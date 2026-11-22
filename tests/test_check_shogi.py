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
from fairy.fairy_board import FairyBoard, sf
from study.engine import validated_study_position

INITIAL = "4k4/9/9/9/9/9/2p6/2R6/4K4[] w - - 0 1"
MOVES = ["c2c3", "e9f9", "P@a4", "f9g9", "c3c7+", "g9h9", "c7h7"]


class CheckShogiTestCase(unittest.TestCase):
    def test_missing_counter_means_one_check_and_start_is_explicit_for_ui(self):
        native = sf.start_fen("checkshogi")
        self.assertEqual(native, sf.start_fen("shogi"))
        self.assertEqual(sf.get_fen("checkshogi", native, []).split()[4], "1+1")
        start = FairyBoard.start_fen("checkshogi")
        self.assertEqual(start, sf.get_fen("checkshogi", native, []))
        self.assertEqual(FairyBoard("checkshogi").fen, start)
        self.assertNotIn("checkshogi", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
        doc = _build_fsf_builtin_doc("checkshogi", FSF_CATALOGUED_BUILTIN_VARIANTS["checkshogi"])
        self.assertEqual(doc["startFen"], start)
        self.assertEqual((doc["width"], doc["height"]), (9, 9))
        self.assertEqual(doc["pieceFamilyOverride"], "shogi")
        self.assertTrue(doc["showCheckCounters"])
        self.assertTrue(doc["captureToHand"])
        self.assertEqual(doc["promotionType"], "shogi")
        self.assertFalse(_client_doc(doc)["replayOnly"])
        self.assertIn("checkCounting = true", catalogued_variant_rule_context(doc)["ini"])

    def test_capture_drop_promotion_and_first_check_wins_without_mate(self):
        board = validated_study_position("checkshogi", INITIAL, chess960=False, show_promoted=False)
        for ply, move in enumerate(MOVES):
            with self.subTest(move=move):
                self.assertIn(move, board.legal_moves())
                board.push(move)
                self.assertEqual(board.is_immediate_game_end()[0], ply == len(MOVES) - 1)
        self.assertEqual(board.fen.split()[4], "0+1")
        self.assertEqual(board.legal_moves(), [])
        self.assertLess(board.game_result(), 0)
        self.assertGreater(len(sf.legal_moves("shogi", INITIAL, MOVES)), 0)
        checked = validated_study_position(
            "checkshogi", board.fen, chess960=False, show_promoted=False
        )
        self.assertEqual(checked.legal_moves(), [])
        self.assertTrue(checked.is_immediate_game_end()[0])

    def test_checking_pawn_drop_wins_and_black_can_win_too(self):
        fixtures = (
            ("4k4/9/9/9/9/9/9/9/4K4[P] w - - 0 1", "P@e8", "0+1"),
            ("4k4/9/9/9/9/9/9/9/4K4[p] b - - 0 1", "P@e2", "1+0"),
        )
        for fen, move, counter in fixtures:
            with self.subTest(counter=counter):
                self.assertIn(move, sf.legal_moves("checkshogi", fen, []))
                final = sf.get_fen("checkshogi", fen, [move])
                self.assertEqual(final.split()[4], counter)
                self.assertEqual(
                    sf.is_immediate_game_end("checkshogi", fen, [move]), (True, -32000)
                )
                self.assertGreater(len(sf.legal_moves("shogi", fen, [move])), 0)
