from __future__ import annotations

import unittest

from catalogued.validation import catalogued_drops_require_visibility, catalogued_hidden_info_mode

FOG_INI = """[myfow:chess]
king = -
commoner = k
castlingKingPiece = k
extinctionValue = loss
extinctionPieceTypes = k
pieceDrops = true
capturesToHand = true
# pychessHiddenInfo = fog
"""


class CataloguedHiddenInfoTestCase(unittest.TestCase):
    def test_recognizes_fog_opt_in(self):
        self.assertEqual(catalogued_hidden_info_mode(FOG_INI), "fog")

    def test_ignores_other_or_missing_values(self):
        for ini in (
            "[myvar:chess]\n",
            "[myvar:chess]\n# pychessHiddenInfo = covered_pieces\n",
            "[myvar:chess]\n# pychessHiddenInfo = nonsense\n",
            "[myvar:chess]\npychessHiddenInfo = fog\n",  # not a comment, ignored
        ):
            with self.subTest(ini=ini):
                self.assertEqual(catalogued_hidden_info_mode(ini), "none")

    def test_is_case_insensitive_and_allows_trailing_comments(self):
        ini = "[myvar:chess]\n# PychessHiddenInfo = FOG  # fog of war please\n"
        self.assertEqual(catalogued_hidden_info_mode(ini), "fog")


class CataloguedDropsRequireVisibilityTestCase(unittest.TestCase):
    def test_requires_fog_and_drops(self):
        ini = FOG_INI + "# pychessDropsRequireVisibility = true\n"
        self.assertTrue(catalogued_drops_require_visibility(ini))

    def test_false_without_fog(self):
        ini = FOG_INI.replace("# pychessHiddenInfo = fog", "") + (
            "# pychessDropsRequireVisibility = true\n"
        )
        self.assertFalse(catalogued_drops_require_visibility(ini))

    def test_false_without_piece_drops(self):
        ini = FOG_INI.replace("pieceDrops = true", "pieceDrops = false") + (
            "# pychessDropsRequireVisibility = true\n"
        )
        self.assertFalse(catalogued_drops_require_visibility(ini))

    def test_false_without_opt_in(self):
        self.assertFalse(catalogued_drops_require_visibility(FOG_INI))


if __name__ == "__main__":
    unittest.main(verbosity=2)
