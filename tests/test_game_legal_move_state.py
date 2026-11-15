"""Keep Random-Mover's cached moves and game status consistent."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from fairy.fairy_board import FairyBoard
from game import Game


class LegalMoveStateTests(unittest.TestCase):
    def test_random_mover_reuses_one_legal_moves_call(self):
        game = Game.__new__(Game)
        game.random_mover = True
        game.board = Mock()
        game.board.has_legal_move.side_effect = AssertionError("redundant rules call")

        for moves in (["e2e4", "d2d4"], [], ["a1a2"]):
            with self.subTest(moves=moves):
                game.board.legal_moves.return_value = moves
                before = game.board.legal_moves.call_count
                game._refresh_legal_move_state()
                self.assertEqual(game.board.legal_moves.call_count, before + 1)
                self.assertEqual(game.legal_moves, moves)
                self.assertEqual(game.has_legal_move, bool(moves))
        game.board.has_legal_move.assert_not_called()

    def test_regular_game_still_uses_existing_has_legal_move_path(self):
        game = Game.__new__(Game)
        game.random_mover = False
        game.board = Mock()
        game.board.has_legal_move.return_value = True
        game._refresh_legal_move_state()
        self.assertTrue(game.has_legal_move)
        game.board.has_legal_move.assert_called_once_with()
        game.board.legal_moves.assert_not_called()

    def test_native_legal_moves_match_existing_status_in_history_variants(self):
        # Janggi requires move history; Jieqi filters hidden-piece moves.
        for variant in ("chess", "janggi", "jieqi"):
            with self.subTest(variant=variant):
                game = Game.__new__(Game)
                game.random_mover = True
                game.board = FairyBoard(variant)
                expected = game.board.has_legal_move()
                game._refresh_legal_move_state()
                self.assertEqual(game.has_legal_move, expected)
                self.assertEqual(game.legal_moves, game.board.legal_moves())
