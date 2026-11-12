from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from catalogued.builtin_data import (
    FSF_CATALOGUED_BUILTIN_DESCRIPTION,
    FSF_CATALOGUED_BUILTIN_VARIANTS,
)
from catalogued.documents import (
    _build_fsf_builtin_doc,
    _client_doc,
    _fsf_builtin_description_for_doc,
    catalogued_variant_rule_context,
)
from fairy.fairy_board import sf


class FsfBuiltinRulesIniTestCase(TestCase):
    def test_micro_documents_mandatory_capture_flips_and_both_face_drops(self) -> None:
        doc = _build_fsf_builtin_doc("micro", FSF_CATALOGUED_BUILTIN_VARIANTS["micro"])
        context = catalogued_variant_rule_context(doc)
        self.assertIn("piecePromotionOnCapture = true", context["ini"])
        self.assertIn("pieceDemotion = true", context["ini"])
        self.assertIn("dropPromoted = true", context["ini"])
        self.assertIn("promotedPieceType = p:n l:s b:g r:g", context["ini"])
        self.assertEqual(_client_doc(doc)["ini"], "")
        start = sf.start_fen("micro")
        self.assertIn("d2d3", sf.legal_moves("micro", start, []))
        self.assertNotIn("d2d3+", sf.legal_moves("micro", start, []))

    def test_snailtrail_exposes_non_capturing_king_moves_and_loses_when_blocked(self) -> None:
        doc = _build_fsf_builtin_doc("snailtrail", FSF_CATALOGUED_BUILTIN_VARIANTS["snailtrail"])
        client_doc = _client_doc(doc)
        self.assertEqual(client_doc["ini"], "")
        self.assertEqual(client_doc["betzaPieces"], {"p": "mK"})
        self.assertTrue(client_doc["rulesArrowing"])
        context = catalogued_variant_rule_context(doc)
        self.assertIn("wallingRule = past", context["ini"])
        fen = sf.start_fen("snailtrail")
        self.assertEqual(
            set(sf.legal_moves("snailtrail", fen, [])),
            {"a1b1,b1a1", "a1a2,a2a1", "a1b2,b2a1"},
        )
        blocked = "6p/7/7/7/7/**5/P*5 w - - 0 1"
        self.assertEqual(sf.legal_moves("snailtrail", blocked, []), [])
        self.assertLess(sf.game_result("snailtrail", blocked, []), 0)
        adjacent = "7/7/7/3p3/3P3/7/7 w - - 0 1"
        self.assertNotIn("d3d4,d4d3", sf.legal_moves("snailtrail", adjacent, []))

    def test_chessgi_documents_loop_captures_and_first_rank_pawn_drops(self) -> None:
        doc = _build_fsf_builtin_doc("chessgi", FSF_CATALOGUED_BUILTIN_VARIANTS["chessgi"])
        client_doc = _client_doc(doc)
        self.assertEqual(client_doc["ini"], "")
        self.assertEqual(client_doc["fsfBuiltinVariant"], "chessgi")
        self.assertNotIn("rulesIni", client_doc)
        context = catalogued_variant_rule_context(doc)
        self.assertIn("[chessgi:loop]", context["ini"])
        self.assertIn("dropLoop = true", context["ini"])
        self.assertIn("firstRankPawnDrops = true", context["ini"])

    def test_jesonmor_documents_its_centre_goal_without_redefining_the_builtin(self) -> None:
        doc = _build_fsf_builtin_doc("jesonmor", FSF_CATALOGUED_BUILTIN_VARIANTS["jesonmor"])
        client_doc = _client_doc(doc)
        self.assertEqual(client_doc["ini"], "")
        self.assertNotIn("rulesIni", client_doc)
        self.assertEqual(client_doc["fsfBuiltinVariant"], "jesonmor")
        context = catalogued_variant_rule_context(doc)
        self.assertIn("flagPiece = n", context["ini"])
        self.assertIn("flagRegionWhite = e5", context["ini"])
        self.assertIn("flagRegionBlack = e5", context["ini"])
        self.assertIn("flagMove = true", context["ini"])
        self.assertEqual(context["customPieceDiagrams"], [])

    def test_euroshogi_rules_expose_sideways_knight_and_mandatory_promotion(self) -> None:
        doc = _build_fsf_builtin_doc("euroshogi", FSF_CATALOGUED_BUILTIN_VARIANTS["euroshogi"])
        client_doc = _client_doc(doc)
        self.assertEqual(client_doc["ini"], "")
        self.assertNotIn("rulesIni", client_doc)
        self.assertEqual(client_doc["fsfBuiltinVariant"], "euroshogi")
        self.assertEqual(client_doc["betzaPieces"], {"n": "fNsW"})
        context = catalogued_variant_rule_context(doc)
        self.assertIn("mandatoryPiecePromotion = true", context["ini"])
        self.assertIn("nFoldRule = 4", context["ini"])
        self.assertEqual([diagram["piece"] for diagram in context["customPieceDiagrams"]], ["n"])

    def test_okisakishogi_rules_document_the_vertical_lance_and_chess_knight(self) -> None:
        doc = _build_fsf_builtin_doc(
            "okisakishogi", FSF_CATALOGUED_BUILTIN_VARIANTS["okisakishogi"]
        )
        client_doc = _client_doc(doc)
        self.assertEqual(client_doc["ini"], "")
        self.assertNotIn("rulesIni", client_doc)
        self.assertEqual(client_doc["betzaPieces"], {"l": "vR", "n": "N"})
        context = catalogued_variant_rule_context(doc)
        self.assertIn("customPiece1 = l:vR", context["ini"])
        self.assertEqual([diagram["piece"] for diagram in context["customPieceDiagrams"]], ["l"])

    def test_yarishogi_rules_ini_is_documentation_only(self) -> None:
        metadata = FSF_CATALOGUED_BUILTIN_VARIANTS["yarishogi"]
        start_fen = "rnnkbbr/7/ppppppp/7/7/7/PPPPPPP/7/RBBKNNR[-] w 0 1"

        with patch("catalogued.validation.sf.start_fen", return_value=start_fen):
            doc = _build_fsf_builtin_doc("yarishogi", metadata)

        self.assertEqual(doc["ini"], "")
        self.assertEqual(doc["baseVariant"], "")
        self.assertEqual(doc["clientVariant"], "shogi")
        self.assertIn("[yarishogi]", doc["rulesIni"])
        self.assertIn("customPiece1 = n:fRffN", doc["rulesIni"])
        self.assertEqual(set(doc["pieces"]), {"p", "n", "b", "r", "k"})
        self.assertEqual(doc["promotionRoles"], ["p", "n", "b", "r"])
        self.assertTrue(doc["captureToHand"])
        self.assertNotIn("description", doc)

        client_doc = _client_doc(doc)
        self.assertEqual(client_doc["ini"], "")
        self.assertEqual(client_doc["baseVariant"], "")
        self.assertEqual(client_doc["clientVariant"], "shogi")
        self.assertNotIn("rulesIni", client_doc)
        self.assertEqual(client_doc["fsfBuiltinVariant"], "yarishogi")
        self.assertEqual(client_doc["tooltip"], FSF_CATALOGUED_BUILTIN_DESCRIPTION)
        self.assertEqual(
            client_doc["betzaPieces"],
            {
                "l": "R",
                "n": "fRffN",
                "b": "fFfR",
                "r": "frlR",
                "g": "WfFbR",
                "s": "fKbR",
            },
        )

        rule_context = catalogued_variant_rule_context(doc)
        self.assertTrue(rule_context["system"])
        self.assertEqual(rule_context["description"], FSF_CATALOGUED_BUILTIN_DESCRIPTION)
        self.assertEqual(rule_context["ini"], doc["rulesIni"])
        self.assertEqual(
            [diagram["piece"] for diagram in rule_context["customPieceDiagrams"]],
            ["n", "b", "r", "g", "s"],
        )
        self.assertGreater(len(rule_context["ruleSummary"]["sections"]), 3)

    def test_only_custom_builtin_descriptions_are_persisted(self) -> None:
        metadata = FSF_CATALOGUED_BUILTIN_VARIANTS["yarishogi"]

        self.assertEqual(
            _fsf_builtin_description_for_doc(
                metadata,
                {"description": FSF_CATALOGUED_BUILTIN_DESCRIPTION},
                [],
            ),
            "",
        )
        self.assertEqual(
            _fsf_builtin_description_for_doc(
                metadata,
                {"description": "Custom administrator description"},
                [],
            ),
            "Custom administrator description",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
