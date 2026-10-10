from __future__ import annotations

import unittest

from fairy.fairy_board import FairyBoard
from fairy.racingkings import RACINGKINGS_FEN_TO_ID, RACINGKINGS_FENS, RACINGKINGS_STARTS


class RacingKings960StartsTestCase(unittest.TestCase):
    def test_filtered_catalogue_size_and_ids(self):
        self.assertEqual(1048, len(RACINGKINGS_STARTS))
        self.assertEqual(1048, len(RACINGKINGS_FENS))
        self.assertEqual(1048, len(RACINGKINGS_FEN_TO_ID))
        self.assertEqual(len(RACINGKINGS_FENS), len(set(RACINGKINGS_FENS)))

    def test_known_material_accidents_are_filtered(self):
        # Position 43: free queen; position 1099: free rook despite a low engine rank.
        self.assertNotIn("nknqQNKN/brrbBRRB", RACINGKINGS_FENS)
        self.assertNotIn("qknrRNKQ/brnbBNRB", RACINGKINGS_FENS)

    def test_posnum_preserves_original_source_id_after_filtering(self):
        # Positions 15, 16 and 17 are filtered, but source position 18 keeps ID 18.
        partial = "bbnqQNBB/nkrrRRKN"
        self.assertEqual(18, RACINGKINGS_FEN_TO_ID[partial])
        board = FairyBoard(
            "racingkings",
            initial_fen=f"8/8/8/8/8/8/{partial} w - - 0 1",
            chess960=True,
        )
        self.assertEqual(18, board.posnum)


if __name__ == "__main__":
    unittest.main()
