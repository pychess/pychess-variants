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


class FsfBuiltinRulesIniTestCase(TestCase):
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
