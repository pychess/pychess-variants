import unittest

import test_logger
from aiohttp import web
from catalogued.validation import (
    _ensure_catalogued_rules_supported,
    _strip_pychess_pieces_metadata,
    catalogued_king_roles,
    catalogued_legal_moves_need_history,
    catalogued_n_fold_is_draw,
    catalogued_promotion_order,
    catalogued_promotion_roles,
    catalogued_promotion_type,
    catalogued_pychess_piece_roles,
    catalogued_rules_gate,
    catalogued_rules_pass,
    catalogued_show_check_counters,
    catalogued_show_promoted,
)

test_logger.init_test_logger()


class CataloguedVariantRuleSafetyTestCase(unittest.TestCase):
    def test_accepts_pychess_piece_metadata_comments(self) -> None:
        ini = """[testmeta:chess]
# pychessPieces = k,q,r,+r p,+p ; inherited promotion pieces
; pychessPieces = b,+b # another metadata line
"""

        self.assertEqual(
            catalogued_pychess_piece_roles(ini),
            (["k", "q", "r", "p", "b"], ["r", "p", "b"]),
        )
        self.assertEqual(_strip_pychess_pieces_metadata(ini), "[testmeta:chess]")

    def test_rejects_invalid_pychess_piece_metadata_tokens(self) -> None:
        ini = """[testmeta:chess]
# pychessPieces = k,++p
"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            catalogued_pychess_piece_roles(ini)

        self.assertIn("pychessPieces", exc.exception.text)

    def test_rejects_two_board_variants(self) -> None:
        ini = """[testbug:chess]
twoBoards = true
"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _ensure_catalogued_rules_supported(ini)

        self.assertIn("twoBoards", exc.exception.text)

    def test_rejects_duck_walling_variants(self) -> None:
        ini = """[testduck:chess]
wallingRule = duck
"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _ensure_catalogued_rules_supported(ini)

        self.assertIn("wallingRule", exc.exception.text)

    def test_rejects_cambodian_and_chasing_rules(self) -> None:
        ini = """[testregional:chess]
cambodianMoves = true
chasingRule = axf
"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _ensure_catalogued_rules_supported(ini)

        self.assertIn("cambodianMoves", exc.exception.text)
        self.assertIn("chasingRule", exc.exception.text)

    def test_rejects_generic_non_seirawan_gating(self) -> None:
        ini = """[testgate:chess]
gating = true
"""

        with self.assertRaises(web.HTTPBadRequest) as exc:
            _ensure_catalogued_rules_supported(ini)

        self.assertIn("gating", exc.exception.text)

    def test_accepts_automatic_adjudication_rules(self) -> None:
        ini = """[testflag:chess]
flagPiece = k
flagRegionWhite = *8
flagRegionBlack = *1
connectN = 4
connectHorizontal = true
stalemateValue = loss
extinctionPieceTypes = k
extinctionPieceCount = 0
castlingWins = true
"""

        _ensure_catalogued_rules_supported(ini)

    def test_accepts_supported_client_rule_metadata(self) -> None:
        ini = """[testrules:chess]
seirawanGating = true
passOnStalemate = true
perpetualCheckIllegal = true
moveRepetitionIllegal = true
nFoldRule = 4
nFoldValue = draw
checkCounting = true
"""

        _ensure_catalogued_rules_supported(ini)
        self.assertTrue(catalogued_rules_gate(ini))
        self.assertTrue(catalogued_rules_pass(ini))
        self.assertTrue(catalogued_legal_moves_need_history(ini))
        self.assertTrue(catalogued_n_fold_is_draw(ini))
        self.assertTrue(catalogued_show_check_counters(ini))

    def test_accepts_regular_promotion_metadata(self) -> None:
        ini = """[testpromo:chess]
promotionPieceTypes = qh
"""

        _ensure_catalogued_rules_supported(ini)
        self.assertEqual(catalogued_promotion_type(ini), "regular")
        self.assertEqual(catalogued_promotion_roles(ini, ["k", "q", "h", "p"]), ["p"])
        self.assertEqual(catalogued_promotion_order(ini, "regular"), ["q", "h"])

    def test_accepts_shogi_style_promotion_metadata(self) -> None:
        ini = """[testshogi:chess]
promotedPieceType = p:q n:c
promotionPieceTypes = -
"""

        _ensure_catalogued_rules_supported(ini)
        self.assertEqual(catalogued_promotion_type(ini), "shogi")
        self.assertEqual(catalogued_promotion_roles(ini, ["k", "q", "c", "p", "n"]), ["p", "n"])
        self.assertEqual(catalogued_promotion_order(ini, "shogi"), ["+", ""])

    def test_promoted_pseudo_royal_king_is_marked_as_king_role(self) -> None:
        ini = """[promotion:chess]
extinctionValue = loss
extinctionPieceTypes = jk
extinctionPseudoRoyal = true
extinctionPieceCount = 64
mandatoryPiecePromotion = true
promotedPieceType = n:y b:y p:z r:o q:a k:j
promotionPieceTypes = -
"""

        self.assertEqual(catalogued_king_roles(ini, ["k", "q", "r", "b", "n", "p"]), ["k", "+k"])

    def test_pseudo_royal_extinction_piece_is_marked_as_king_role(self) -> None:
        ini = """[royalqueen:chess]
extinctionValue = loss
extinctionPieceTypes = q
extinctionPseudoRoyal = true
"""

        self.assertEqual(catalogued_king_roles(ini, ["k", "q", "r", "b", "n", "p"]), ["k", "q"])

    def test_accepts_demoting_and_promoted_drop_metadata(self) -> None:
        ini = """[testflip:chess]
promotedPieceType = p:r
pieceDemotion = true
piecePromotionOnCapture = true
dropPromoted = true
"""

        _ensure_catalogued_rules_supported(ini)
        self.assertTrue(catalogued_show_promoted(ini, "8/8/8/8/8/8/8/8[] w - - 0 1"))
