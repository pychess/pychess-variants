from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import AioHTTPTestCase
from const import CASUAL, STARTED
from fairy import FairyBoard
from game import Game
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import insert_game_to_db, load_game, play_move

from server import make_app


class LegalMoveStateTests(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def new_game(self):
        state = get_app_state(self.app)
        white = User(state, username="legal-moves-white")
        black = User(state, username="legal-moves-black")
        state.users[white.username] = white
        state.users[black.username] = black
        game = Game(state, id8(), "chess", "", white, black, rated=CASUAL)
        state.games[game.id] = game
        await insert_game_to_db(game, state)
        return game

    async def test_next_player_reuses_status_moves_and_takeback_rebuilds_them(self):
        game = await self.new_game()
        white, black = game.wplayer, game.bplayer
        black_ws = AsyncMock()
        black.add_ws_for_game(game.id, black_ws)

        with patch.object(game.board, "legal_moves", wraps=game.board.legal_moves) as generate:
            async with game.move_lock:
                await play_move(game.app_state, white, game, "e2e4", ply=1)
                self.assertEqual(game.ply, 1)
                self.assertEqual(generate.call_count, 2)
                black_ws.send_str.reset_mock()

                await play_move(game.app_state, white, game, "d2d4", ply=2)
                await play_move(game.app_state, black, game, "e7e4", ply=2)
                self.assertEqual(game.status, STARTED)
                self.assertEqual(game.ply, 1)
                self.assertEqual(generate.call_count, 2)
                black_ws.send_str.assert_awaited_once()

                await play_move(game.app_state, black, game, "e7e5", ply=2)
                self.assertEqual(game.ply, 2)
                self.assertEqual(generate.call_count, 3)

                await game.takeback(black)
                self.assertEqual(game.ply, 1)
                await play_move(game.app_state, black, game, "c7c5", ply=2)
                self.assertEqual(game.board.move_stack, ["e2e4", "c7c5"])
                self.assertEqual(generate.call_count, 5)

    async def test_reloaded_game_validates_the_restored_position(self):
        game = await self.new_game()
        state = game.app_state
        async with game.move_lock:
            await play_move(state, game.wplayer, game, "e2e4", ply=1)

        state.games.pop(game.id)
        await game.cancel_clocks_for_eviction()
        reloaded = await load_game(state, game.id)
        assert isinstance(reloaded, Game)
        self.assertIn("e7e5", reloaded.legal_moves)
        self.assertNotIn("e2e4", reloaded.legal_moves)

        with patch.object(
            reloaded.board, "legal_moves", wraps=reloaded.board.legal_moves
        ) as generate:
            async with reloaded.move_lock:
                await play_move(state, reloaded.bplayer, reloaded, "e7e5", ply=2)
            self.assertEqual(reloaded.ply, 2)
            generate.assert_called_once_with()


class BoardLegalMoveCacheTests(unittest.TestCase):
    def test_fen_replacement_at_same_ply_changes_moves(self):
        board = FairyBoard("chess")
        self.assertIn("e2e4", board.cached_legal_moves())

        changed = FairyBoard("chess")
        changed.push("e2e4")
        changed.push("e7e5")
        board.fen = changed.fen
        self.assertEqual(board.ply, 0)
        self.assertIn("g1f3", board.cached_legal_moves())
        self.assertNotIn("e2e4", board.cached_legal_moves())
        self.assertEqual(board.cached_legal_moves(), tuple(board.legal_moves()))

    def test_chess960_setting_change_updates_castling_moves(self):
        board = FairyBoard("chess", "4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        self.assertIn("e1g1", board.cached_legal_moves())

        board.chess960 = True
        self.assertIn("e1h1", board.cached_legal_moves())
        self.assertNotIn("e1g1", board.cached_legal_moves())

    def test_janggi_history_change_at_same_fen_and_ply_changes_moves(self):
        board = FairyBoard("janggi", "9/4k4/9/p8/9/4P4/9/9/4K4/R8 w - - 0 1")
        board.push("e5d5")
        self.assertNotIn("a7a6", board.cached_legal_moves())

        # Keep the same FEN and history length while changing the engine's replay input.
        board.move_stack[0] = "a1a2"
        self.assertIn("a7a6", board.cached_legal_moves())
        self.assertEqual(board.cached_legal_moves(), tuple(board.legal_moves()))

    def test_jieqi_cover_change_at_same_fen_can_cache_empty_move_list(self):
        fen = "2b~a~1a~b~n~r~/2n1k1R2/n1r1bN3/8p~/9/1aB1P4/8P~/1C~N1P2C~1/9/1N~B~1K1B~pR~ b - - 0 1"
        board = FairyBoard("jieqi", fen)
        self.assertEqual(board.cached_legal_moves(), ("f10g9",))

        board.set_jieqi_initial_pieces("nrcapppcbpabnpr", "PBPNAPANRBRPCPC")
        with patch.object(board, "legal_moves", wraps=board.legal_moves) as generate:
            self.assertEqual(board.cached_legal_moves(), ())
            self.assertEqual(board.cached_legal_moves(), ())
            generate.assert_called_once_with()
