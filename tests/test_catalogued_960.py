from __future__ import annotations

import unittest

from catalogued.rules import catalogued_random_start, catalogued_rule_summary
from fairy.fairy_board import STANDARD_FEN


class Catalogued960PolicyTestCase(unittest.TestCase):
    def test_randomization_requires_all_opt_in_conditions(self):
        ini = "[sideways960:pawnsideways]\nchess960 = true"
        self.assertTrue(catalogued_random_start(ini, STANDARD_FEN, 8, 8))
        for rules, fen, width, height in (
            (ini.replace("sideways960", "sideways"), STANDARD_FEN, 8, 8),
            (ini.replace("true", "false"), STANDARD_FEN, 8, 8),
            ("[sideways960:pawnsideways]", STANDARD_FEN, 8, 8),
            (ini, STANDARD_FEN, 10, 8),
            (ini, STANDARD_FEN, 8, 10),
            (ini, STANDARD_FEN.replace("RNBQKBNR", "RNKRQBBN"), 8, 8),
            (ini, STANDARD_FEN.replace("rnbqkbnr", "rnkrqbbn"), 8, 8),
            (ini, STANDARD_FEN.replace("KQkq", "-"), 8, 8),
            (ini + "\ncastling = false", STANDARD_FEN, 8, 8),
            (ini + "\ncastlingKingPiece = q", STANDARD_FEN, 8, 8),
            (ini + "\ngating = true", STANDARD_FEN, 8, 8),
            (ini + "\ncustomPiece1 = r:QN", STANDARD_FEN, 8, 8),
        ):
            with self.subTest(rules=rules, fen=fen, width=width, height=height):
                self.assertFalse(catalogued_random_start(rules, fen, width, height))

    def test_rule_summary_distinguishes_castling_from_randomization(self):
        for name, randomizes in (("sideways960", True), ("sideways", False)):
            summary = catalogued_rule_summary(
                {
                    "ini": f"[{name}:pawnsideways]\nchess960 = true",
                    "startFen": STANDARD_FEN,
                    "width": 8,
                    "height": 8,
                }
            )
            lines = [line["text"] for section in summary["sections"] for line in section["lines"]]
            self.assertIn("The variant supports Chess960-style castling.", lines)
            self.assertEqual(
                "Games use a randomized Chess960 starting position." in lines, randomizes
            )
