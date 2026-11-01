import unittest

from catalogued.validation import (
    _catalogued_piece_roles_from_ini,
    _catalogued_pocket_roles_from_doc,
    catalogued_king_roles,
    catalogued_pocket_roles,
)

COURTHRONE_START_FEN = "qpbdkdbpq/9/v1v1v1v1v/9/9/9/V1V1V1V1V/9/QPBDKDBPQ[NNTTnntt] w - - 0 1"

COURTHRONE_INI = f"""
[courthrone]
variantTemplate = shogi
maxFile = 9
maxRank = 9
pocketSize = 7
startFen = {COURTHRONE_START_FEN}
customPiece1 = v:fFfsW
commoner = g
queen = q
customPiece2 = p:pQ
customPiece3 = d:mQcpQ
customPiece4 = b:cQmpQ
customPiece5 = e:QpQ
knight = n
customPiece6 = t:AD
customPiece7 = c:NAD
king = k
pieceDrops = true
capturesToHand = true
promotionRegionWhite = *9
promotionRegionBlack = *1
promotedPieceType = v:g q:e p:e d:e b:e n:c t:c
mandatoryPiecePromotion = true
stalemateValue = loss
nMoveRule = 0
nFoldRule = 3
nFoldValue = loss
perpetualCheckIllegal = true
castling = false
doubleStep = false
flagPiece = k
flagRegionWhite = *9
flagRegionBlack = *1
"""

DRAGONFLY_START_FEN = "rbbknnr/ppppppp/7/7/7/PPPPPPP/RBBKNNR[] w - - 0 1"
DRAGONFLY_INI = f"""
[dragonfly:chess]
pieceDrops = true
capturesToHand = true
startFen = {DRAGONFLY_START_FEN}
"""


class CataloguedVariantPocketRolesTestCase(unittest.TestCase):
    def test_capture_to_hand_expands_initial_pocket_roles_to_all_non_royal_pieces(self):
        pieces = _catalogued_piece_roles_from_ini(COURTHRONE_INI, COURTHRONE_START_FEN)
        king_roles = catalogued_king_roles(COURTHRONE_INI, pieces)

        self.assertEqual(
            catalogued_pocket_roles(COURTHRONE_INI, COURTHRONE_START_FEN, pieces, king_roles),
            ["n", "t", "q", "b", "p", "d", "v"],
        )

    def test_non_capture_to_hand_keeps_explicit_initial_pocket_roles(self):
        ini = COURTHRONE_INI.replace("capturesToHand = true", "capturesToHand = false")
        pieces = _catalogued_piece_roles_from_ini(ini, COURTHRONE_START_FEN)
        king_roles = catalogued_king_roles(ini, pieces)

        self.assertEqual(
            catalogued_pocket_roles(ini, COURTHRONE_START_FEN, pieces, king_roles),
            ["n", "t"],
        )

    def test_existing_stored_capture_to_hand_docs_are_expanded_for_clients(self):
        doc = {
            "ini": COURTHRONE_INI,
            "startFen": COURTHRONE_START_FEN,
            "pieces": ["k", "q", "b", "n", "p", "d", "v", "t"],
            "kingRoles": ["k"],
            "pocketRoles": ["n", "t"],
            "captureToHand": True,
        }

        self.assertEqual(
            _catalogued_pocket_roles_from_doc(
                doc, COURTHRONE_INI, COURTHRONE_START_FEN, doc["pieces"], doc["kingRoles"]
            ),
            ["n", "t", "q", "b", "p", "d", "v"],
        )

    def test_empty_initial_pocket_excludes_royal_roles_from_capture_to_hand(self):
        pieces = ["k", "r", "b", "n", "p"]

        self.assertEqual(
            catalogued_pocket_roles(DRAGONFLY_INI, DRAGONFLY_START_FEN, pieces, ["k"]),
            ["r", "b", "n", "p"],
        )

    def test_existing_stored_capture_to_hand_docs_filter_royal_roles(self):
        doc = {
            "pocketRoles": ["k", "r", "b", "n", "p"],
            "captureToHand": True,
        }

        self.assertEqual(
            _catalogued_pocket_roles_from_doc(
                doc,
                DRAGONFLY_INI,
                DRAGONFLY_START_FEN,
                ["k", "r", "b", "n", "p"],
                ["k"],
            ),
            ["r", "b", "n", "p"],
        )

    def test_explicit_initial_royal_pocket_role_is_preserved(self):
        start_fen = "8/8/8/8/8/8/8/8[KQkq] w - - 0 1"
        ini = f"[placement:chess]\npieceDrops = true\nstartFen = {start_fen}"

        self.assertEqual(
            catalogued_pocket_roles(
                ini,
                start_fen,
                ["k", "q"],
                ["k"],
                capture_to_hand=True,
            ),
            ["k", "q"],
        )


if __name__ == "__main__":
    unittest.main()
