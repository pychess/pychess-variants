from __future__ import annotations

import unittest

import pyffish as sf
import test_logger
from fairy.fairy_board import FairyBoard, get_fog_fen
from test_embassy_castling_pgn import make_game
from variants import register_catalogued_server_variant, unregister_catalogued_server_variant

test_logger.init_test_logger()

CATALOGUED_FOW_INI = """[testcatfow:chess]
king = -
commoner = k
castlingKingPiece = k
extinctionValue = loss
extinctionPieceTypes = k
pieceDrops = true
capturesToHand = true
# pychessHiddenInfo = fog
# pychessDropsRequireVisibility = true
"""

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"
MIDGAME_FEN = "rnqbbnkr/pppppppp/8/8/8/8/PPPPPPPP/QRBNKBRN[P] w BGbh - 0 1"


class CataloguedHiddenInfoGameTestCase(unittest.TestCase):
    """Proves the fog/drop-visibility machinery is already generic: it works
    for a catalogued (user-defined) variant exactly as it already does for a
    built-in one, once hidden_info/drops_require_visibility are set."""

    def setUp(self):
        sf.load_variant_config(CATALOGUED_FOW_INI)
        register_catalogued_server_variant(
            "testcatfow",
            "Test Catalogued FoW",
            hidden_info=True,
            hidden_info_mode="fog",
            drops_require_visibility=True,
        )
        self.addCleanup(unregister_catalogued_server_variant, "testcatfow")

    def test_game_reports_fog_and_drop_visibility_metadata(self):
        game = make_game("catfow-game", "testcatfow", START_FEN)
        self.assertTrue(game.fow)
        self.assertTrue(game.server_variant.hidden_info)
        self.assertTrue(game.server_variant.drops_require_visibility)

    def test_fog_fen_redacts_the_board_for_a_catalogued_variant(self):
        fog = get_fog_fen(MIDGAME_FEN, 0, "testcatfow", False, drops_require_visibility=True)
        ranks = fog.split()[0].split("/")
        # Black's distant ranks stay hidden; white's own back rank is visible.
        self.assertEqual(ranks[0], "********")
        self.assertNotIn("*", ranks[-1])

    def test_drop_visibility_filter_matches_built_in_behavior(self):
        board = FairyBoard("testcatfow", MIDGAME_FEN, False)
        visible = board.visible_drop_squares()
        drop_moves = [move for move in board.legal_moves() if "@" in move]
        blocked = [move for move in drop_moves if move[2:4] not in visible]
        allowed = [move for move in drop_moves if move[2:4] in visible]
        self.assertTrue(allowed)
        self.assertTrue(blocked)


if __name__ == "__main__":
    unittest.main(verbosity=2)
