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

INITIAL = "4k3/8/8/P7/8/8/3R4/4K3 w - - 0 1"
MOVES = ["a5a6m", "e8f8", "d2d3", "f8g8", "d3g3"]


class KarOukTestCase(unittest.TestCase):
    def test_native_one_check_start_and_cambodian_metadata(self):
        self.assertEqual(sf.start_fen("karouk"), sf.start_fen("cambodian"))
        start = FairyBoard.start_fen("karouk")
        self.assertEqual(start.split()[4], "1+1")
        self.assertNotIn("karouk", FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
        doc = _build_fsf_builtin_doc("karouk", FSF_CATALOGUED_BUILTIN_VARIANTS["karouk"])
        self.assertEqual(doc["startFen"], start)
        self.assertEqual(doc["baseVariant"], "cambodian")
        self.assertEqual(doc["clientVariant"], "cambodian")
        self.assertEqual(doc["boardFamilyOverride"], "makruk8x8")
        self.assertEqual(doc["pieceFamilyOverride"], "makruk")
        self.assertEqual(doc["promotionOrder"], ["m"])
        self.assertTrue(doc["showCheckCounters"])
        self.assertTrue(doc["showPromoted"])
        self.assertFalse(_client_doc(doc)["replayOnly"])
        self.assertIn("checkCounting = true", catalogued_variant_rule_context(doc)["ini"])

    def test_cambodian_initial_met_and_king_moves_retain_rights(self):
        board = validated_study_position(
            "karouk", FairyBoard.start_fen("karouk"), chess960=False, show_promoted=True
        )
        moves = ["e3e4", "d6d5", "e1e3", "e8g7", "d1b2"]
        for ply, move in enumerate(moves):
            with self.subTest(move=move):
                self.assertIn(move, board.legal_moves())
                self.assertEqual(
                    set(board.legal_moves()),
                    set(sf.legal_moves("cambodian", sf.start_fen("cambodian"), moves[:ply])),
                )
                board.push(move)
                checked = validated_study_position(
                    "karouk", board.fen, chess960=False, show_promoted=True
                )
                self.assertEqual(board.legal_moves(), checked.legal_moves())
                self.assertFalse(board.is_immediate_game_end()[0])
        self.assertEqual(board.fen.split()[2], "d")

    def test_promotion_and_first_check_win_even_with_king_escapes(self):
        board = validated_study_position("karouk", INITIAL, chess960=False, show_promoted=True)
        for ply, move in enumerate(MOVES):
            self.assertIn(move, board.legal_moves())
            board.push(move)
            self.assertEqual(board.is_immediate_game_end()[0], ply == len(MOVES) - 1)
        self.assertEqual(board.fen.split()[4], "0+1")
        self.assertIn("M~", board.fen)
        self.assertEqual(board.legal_moves(), [])
        self.assertLess(board.game_result(), 0)
        self.assertTrue(sf.legal_moves("cambodian", INITIAL, MOVES))

    def test_black_check_and_automatic_counting_draw(self):
        fen = "4k3/3r4/8/8/8/8/8/4K3 b - - 0 1"
        self.assertIn("d7e7", sf.legal_moves("karouk", fen, []))
        self.assertEqual(sf.get_fen("karouk", fen, ["d7e7"]).split()[4], "1+0")
        self.assertTrue(sf.is_immediate_game_end("karouk", fen, ["d7e7"])[0])
        counting = "4k3/8/8/8/8/8/3R4/4K3 w - 30 1+1 30 16"
        self.assertFalse(sf.is_optional_game_end("karouk", counting, [])[0])
        self.assertEqual(sf.is_optional_game_end("karouk", counting, ["d2d3"]), (True, 0))
