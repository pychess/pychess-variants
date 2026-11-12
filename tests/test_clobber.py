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


class ClobberTestCase(unittest.TestCase):
    def test_native_catalogue_metadata_and_study_capture(self):
        for name, width, height in (("clobber", 5, 6), ("clobber10", 10, 10)):
            with self.subTest(name=name):
                self.assertNotIn(name, FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
                doc = _build_fsf_builtin_doc(name, FSF_CATALOGUED_BUILTIN_VARIANTS[name])
                self.assertEqual((doc["width"], doc["height"]), (width, height))
                self.assertEqual(doc["pieceFamilyOverride"], "ataxx")
                self.assertEqual(doc["kingRoles"], [])
                self.assertEqual(doc["pocketRoles"], [])
                self.assertFalse(doc["rulesPass"])
                self.assertFalse(_client_doc(doc)["replayOnly"])
                self.assertEqual(_client_doc(doc)["betzaPieces"], {"p": "cW"})
                self.assertIn(
                    "maxRank = " + str(height), catalogued_variant_rule_context(doc)["ini"]
                )
                board = validated_study_position(
                    name, sf.start_fen(name), chess960=False, show_promoted=False
                )
                self.assertEqual(board.insufficient_material(), (False, False))
                board.push(board.legal_moves()[0])
                checked = validated_study_position(
                    name, board.fen, chess960=False, show_promoted=False
                )
                self.assertEqual(board.legal_moves(), checked.legal_moves())

    def test_blocked_side_loses_even_with_more_discs(self):
        for name, width, height in (("clobber", 5, 6), ("clobber10", 10, 10)):
            with self.subTest(name=name):
                rows = (
                    ["p" + str(width - 1)]
                    + [str(width)] * (height - 3)
                    + ["2p" + str(width - 3), "Pp" + str(width - 2)]
                )
                fen = "/".join(rows) + " w - - 0 1"
                self.assertEqual(sf.legal_moves(name, fen, []), ["a1b1"])
                self.assertEqual(sf.legal_moves(name, fen, ["a1b1"]), [])
                self.assertLess(sf.game_result(name, fen, ["a1b1"]), 0)
                self.assertEqual(sf.has_insufficient_material(name, fen, ["a1b1"]), (False, False))
