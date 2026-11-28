from __future__ import annotations

import unittest

from catalogued.rules import catalogued_double_random_start
from fairy.fairy_board import STANDARD_FEN

RANDOM_INI = "[mydr960:crazyhouse]\nchess960 = true\n"


class CataloguedDoubleRandomTestCase(unittest.TestCase):
    def test_requires_opt_in_on_top_of_random_start(self):
        self.assertFalse(catalogued_double_random_start(RANDOM_INI, STANDARD_FEN, 8, 8))
        self.assertTrue(
            catalogued_double_random_start(
                RANDOM_INI + "# pychessDoubleRandom = true\n", STANDARD_FEN, 8, 8
            )
        )

    def test_false_when_random_start_itself_is_not_recognized(self):
        # Not a "...960" section name, so random_start is False regardless.
        ini = RANDOM_INI.replace("mydr960", "mydr") + "# pychessDoubleRandom = true\n"
        self.assertFalse(catalogued_double_random_start(ini, STANDARD_FEN, 8, 8))

    def test_works_with_fog_of_wars_royalless_king_setup(self):
        # king = -/commoner/castlingKingPiece is needed for castling to work
        # at all once the normal king is removed; it must not be mistaken for
        # a disqualifying custom-castling rule.
        ini = (
            "[myfow960:chess]\nchess960 = true\nking = -\ncommoner = k\n"
            "castlingKingPiece = k\n# pychessDoubleRandom = true\n"
        )
        self.assertTrue(catalogued_double_random_start(ini, STANDARD_FEN, 8, 8))


if __name__ == "__main__":
    unittest.main(verbosity=2)
