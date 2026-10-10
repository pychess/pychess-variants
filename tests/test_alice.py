import unittest

import test_logger
from fairy import FEN_OK, NOTATION_SAN, STANDARD_FEN, FairyBoard, get_san_moves, validate_fen

test_logger.init_test_logger()

# https://en.wikipedia.org/wiki/Alice_chess#Early_mates
MATE1 = ("e2e4", "d7d5", "f1e2", "d5e4", "e2b5")
MATE2 = ("e2e4", "d7d6", "f1c4", "d8d2", "c4b5")
MATE3 = ("e2e4", "e7e5", "d1h5", "g8f6", "h5e5")
MATE4 = ("e2e4", "h7h5", "f1e2", "h8h4", "e2h5", "h4e4", "e1f1", "d7d5", "d1e2", "c8h3")
MATE5 = ("d2d4", "e7e6", "d1d6", "f8e7", "d6e5", "e8f8", "c1h6")

# https://en.wikipedia.org/wiki/Alice_chess#Example_game
# Paul Yearout vs. George Jelliss, 1996 AISE Grand Prix
# TODO: SAN ambiguation of 6...Rg8 is missing in alice.py (it should be 6...Rbg8)
GAME_PART1 = (
    "d2d3",
    "g8f6",
    "b1c3",
    "c7c5",
    "d1d2",
    "b8c6",
    "d3d4",
    "a8b8",
    "e2e3",
    "g7g5",
    "f2f4",
    "b8g8",
    "c3d5",
    "h7h6",
    "g1f3",
    "g5f4",
    "c1f4",
    "g8g4",
    "f4e5",
    "h8h5",
    "e1c1",
)
GAME_PART2 = (
    "f6e4",
    "e5c7",
    "g4a4",
    "f1a6",
    "f8g7",
    "a6b5",
    "a4c4",
    "c1b1",
    "h5f5",
    "c7a5",
    "f5d5",
    "d2d5",
    "d8a5",
    "a2a3",
    "a5d2",
    "d5d7",
    "e8f8",
    "d7g7",
    "d2c3",
    "d1d8",
)

# https://github.com/pychess/pychess-variants/issues/1570
GHOST_ROOKS_PART1 = (
    "e2e4",
    "e7e5",
    "b1c3",
    "g8f6",
    "c3d5",
    "f6e4",
    "d5c7",
    "f8d6",
    "f1d3",
    "d6c7",
)
GHOST_ROOKS_PART2 = (
    "f2f3",
    "e4d6",
    "g1e2",
    "d8e7",
    "e2d4",
)

# https://github.com/pychess/pychess-variants/issues/1604
QUEEN_DISAPPEARED = (
    "d2d4",
    "d7d5",
    "d1d8",
    "c8d7",
    "b1c3",
    "g8f6",
    "c3d5",
    "b8a6",
    "c1g5",
    "a8c8",
)


class AliceTestCase(unittest.TestCase):
    def test_checkmate(self):
        for movelist in (MATE1, MATE2, MATE3, MATE4, MATE5):
            board = FairyBoard("alice")
            for move in movelist:
                board.push(move)
            self.assertTrue(board.is_checked())
            self.assertFalse(board.has_legal_move())

            for _ in range(len(movelist)):
                board.pop()

            self.assertEqual(board.fen, STANDARD_FEN)

    def test_alice_uses_pyffish_alice_engine(self):
        board = FairyBoard("alice")

        self.assertEqual(board.sf.__name__, "pyffish_alice")
        self.assertEqual(validate_fen(board.fen, "alice", False), FEN_OK)

        legal_moves = board.legal_moves()
        self.assertIn("e2e4", legal_moves)
        self.assertIn("g1f3", legal_moves)

        self.assertEqual(
            get_san_moves("alice", board.fen, ["e2e4", "e7e5"], False, NOTATION_SAN),
            ["e4", "e5"],
        )

    def test_game_with_castling(self):
        board = FairyBoard("alice")
        for move in GAME_PART1:
            board.push(move)

        # After 11. 0-0-0
        FEN = "2bqkb2/pp1ppp2/2|n2|n1|p/2|pNB2|r/3P2|r1/4|P|N2/PPP|Q2PP/2|K|R1B1R b - - 4 11"
        self.assertEqual(board.fen, FEN)

        # The black queen is now effectively 'pinned': 11...Q–c7/b6?? 12.Qd8#.)
        board.push("d8b6")
        board.push("d2d8")
        self.assertTrue(board.is_checked())
        self.assertFalse(board.has_legal_move())
        board.pop()
        board.pop()

        for move in GAME_PART2:
            board.push(move)

        # Black resigns. If 21...Bd7/Be6/Nf6 [then] 22.Qg8/Re8/Qh8#
        board.push("c8d7")
        board.push("g7g8")
        self.assertTrue(board.is_checked())
        self.assertFalse(board.has_legal_move())
        board.pop()
        board.pop()

        board.push("c8e6")
        board.push("d8e8")
        self.assertTrue(board.is_checked())
        self.assertFalse(board.has_legal_move())
        board.pop()
        board.pop()

        board.push("e4f6")
        board.push("g7h8")
        self.assertTrue(board.is_checked())
        self.assertFalse(board.has_legal_move())
        board.pop()
        board.pop()

        for _ in range(len(GAME_PART1) + len(GAME_PART2)):
            board.pop()
        self.assertEqual(board.fen, STANDARD_FEN)

    def test_game_without_castling1(self):
        board = FairyBoard("alice")
        for move in GHOST_ROOKS_PART1:
            board.get_san(move)
            board.legal_moves()
            board.push(move)

        # After 5...Bxc7
        FEN = "rnbqk2r/ppbp1ppp/8/4|p3/4n3/3|B4/PPPP1PPP/R1BQK1NR w KQkq - 0 6"
        self.assertEqual(board.fen, FEN)

        for move in GHOST_ROOKS_PART2:
            board.get_san(move)
            board.legal_moves()
            board.push(move)

        # After 8. Nd4
        FEN = "rnb1k2r/ppbp|qppp/3|n4/4|p3/3N4/3|B1|P2/PPPP2PP/R1BQK2R b KQkq - 4 8"
        self.assertEqual(board.fen, FEN)

    def test_game_without_castling2(self):
        board = FairyBoard("alice")
        for move in QUEEN_DISAPPEARED:
            board.get_san(move)
            board.legal_moves()
            board.push(move)

        # After 5...Rc8
        FEN = "2|r|Qkb1r/ppp|bpppp/|n4|n2/3N2|B1/3|P4/8/PPP1PPPP/R3KBNR w KQk - 3 6"
        self.assertEqual(board.fen, FEN)

    def test_castling(self):
        FEN = "r|q2k2r/1pp|bpp|b1/|P1|n|pP1|p1/2PP4/6n1/2|N1|B|N1p/1|p|Q2PPP/R3K|B1R b KQkq - 0 13"
        board = FairyBoard("alice", initial_fen=FEN)

        move = "e8c8"
        board.get_san(move)
        board.legal_moves()
        board.push(move)

        FEN_OOO = (
            "1|q|k|r3r/1pp|bpp|b1/|P1|n|pP1|p1/2PP4/6n1/2|N1|B|N1p/1|p|Q2PPP/R3K|B1R w KQ - 1 14"
        )
        self.assertEqual(board.fen, FEN_OOO)

        board.pop()
        self.assertEqual(board.fen, FEN)

        move = "e8g8"
        board.get_san(move)
        board.legal_moves()
        board.push(move)

        FEN_OO = (
            "r|q3|r|k1/1pp|bpp|b1/|P1|n|pP1|p1/2PP4/6n1/2|N1|B|N1p/1|p|Q2PPP/R3K|B1R w KQ - 1 14"
        )
        self.assertEqual(board.fen, FEN_OO)

        board.pop()
        self.assertEqual(board.fen, FEN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
