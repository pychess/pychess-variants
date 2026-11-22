import unittest
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import AioHTTPTestCase
from const import STARTED
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from user import User
from variants import VARIANTS
from wsr import handle_setup, handle_takeback

from server import make_app

PERFS = new_default_perf_map(VARIANTS)
RED_SETUP_FEN = "rbna1abnr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RNBA1ABNR w - - 0 1"
BLUE_SETUP_FEN = "rbna1abnr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RBNA1ANBR w - - 0 1"


class JanggiSetupValidationTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        self.wplayer = User(app_state, username="wplayer-setup", perfs=PERFS)
        self.bplayer = User(app_state, username="bplayer-setup", perfs=PERFS)

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    def new_game(self) -> Game:
        return Game(
            get_app_state(self.app),
            id8(),
            "janggi",
            "",
            self.wplayer,
            self.bplayer,
            rated=False,
        )

    @property
    def users(self):
        return {
            self.wplayer.username: self.wplayer,
            self.bplayer.username: self.bplayer,
        }

    async def test_setup_color_mismatch_is_ignored(self):
        game = self.new_game()
        initial_fen = game.board.initial_fen

        with patch("wsr.ws_send_json", new=AsyncMock()):
            await handle_setup(
                ws=AsyncMock(),
                users=self.users,
                user=self.wplayer,
                data={
                    "type": "setup",
                    "gameId": game.id,
                    "color": "black",
                    "fen": RED_SETUP_FEN,
                },
                game=game,
            )

        self.assertTrue(game.bsetup)
        self.assertTrue(game.wsetup)
        self.assertEqual(game.board.initial_fen, initial_fen)
        self.assertEqual(game.steps[0]["fen"], initial_fen)

    async def test_stale_setup_after_first_move_is_ignored(self):
        game = self.new_game()

        with patch("wsr.ws_send_json", new=AsyncMock()):
            await handle_setup(
                ws=AsyncMock(),
                users=self.users,
                user=self.bplayer,
                data={
                    "type": "setup",
                    "gameId": game.id,
                    "color": "black",
                    "fen": RED_SETUP_FEN,
                },
                game=game,
            )
            await handle_setup(
                ws=AsyncMock(),
                users=self.users,
                user=self.wplayer,
                data={
                    "type": "setup",
                    "gameId": game.id,
                    "color": "white",
                    "fen": BLUE_SETUP_FEN,
                },
                game=game,
            )

            clocks = (game.clocks_w[0], game.clocks_b[0])
            await game.play_move("c1d3", clocks=clocks, ply=1)

            fen_before = game.board.fen
            initial_before = game.board.initial_fen
            step0_before = game.steps[0]["fen"]

            await handle_setup(
                ws=AsyncMock(),
                users=self.users,
                user=self.wplayer,
                data={
                    "type": "setup",
                    "gameId": game.id,
                    "color": "white",
                    "fen": RED_SETUP_FEN,
                },
                game=game,
            )

        self.assertEqual(game.ply, 1)
        self.assertEqual(game.board.fen, fen_before)
        self.assertEqual(game.board.initial_fen, initial_before)
        self.assertEqual(game.steps[0]["fen"], step0_before)
        self.assertFalse(game.bsetup)
        self.assertFalse(game.wsetup)

    async def test_black_setup_with_bot_white_sends_board_and_starts_game(self):
        app_state = get_app_state(self.app)
        white_bot = User(app_state, bot=True, username="wbot-setup", perfs=PERFS)
        black_player = User(app_state, username="bplayer-vs-bot", perfs=PERFS)
        users = {
            white_bot.username: white_bot,
            black_player.username: black_player,
        }
        game = Game(
            app_state,
            id8(),
            "janggi",
            "",
            white_bot,
            black_player,
            rated=False,
        )

        ws_send_json_mock = AsyncMock()
        with patch("wsr.ws_send_json", new=ws_send_json_mock):
            await handle_setup(
                ws=AsyncMock(),
                users=users,
                user=black_player,
                data={
                    "type": "setup",
                    "gameId": game.id,
                    "color": "black",
                    "fen": RED_SETUP_FEN,
                },
                game=game,
            )

        self.assertFalse(game.bsetup)
        self.assertFalse(game.wsetup)
        self.assertEqual(game.status, STARTED)
        self.assertGreaterEqual(len(ws_send_json_mock.await_args_list), 1)
        sent_payload = ws_send_json_mock.await_args_list[-1].args[1]
        self.assertEqual(sent_payload["type"], "board")

    async def test_takeback_to_ply_zero_keeps_completed_setup_playable(self):
        app_state = get_app_state(self.app)
        game = self.new_game()
        initial_count = app_state.g_cnt[0]
        before_setup = game.legal_moves

        with patch("wsr.ws_send_json", new=AsyncMock()):
            await handle_setup(
                ws=AsyncMock(),
                users=self.users,
                user=self.bplayer,
                data={
                    "type": "setup",
                    "gameId": game.id,
                    "color": "black",
                    "fen": RED_SETUP_FEN,
                },
                game=game,
            )
            await handle_setup(
                ws=AsyncMock(),
                users=self.users,
                user=self.wplayer,
                data={
                    "type": "setup",
                    "gameId": game.id,
                    "color": "white",
                    "fen": BLUE_SETUP_FEN,
                },
                game=game,
            )

        self.assertEqual(game.status, STARTED)
        self.assertFalse(game.bsetup)
        self.assertFalse(game.wsetup)
        self.assertFalse(game.counted_as_active)
        self.assertNotEqual(game.legal_moves, before_setup)
        self.assertEqual(game.legal_moves, tuple(game.board.legal_moves()))

        await game.play_move(game.board.legal_moves()[0])
        await game.play_move(game.board.legal_moves()[0])
        self.assertTrue(game.counted_as_active)
        self.assertEqual(app_state.g_cnt[0], initial_count + 1)

        await handle_takeback(AsyncMock(), self.wplayer, game)
        await handle_takeback(AsyncMock(), self.bplayer, game)

        self.assertEqual(game.ply, 0)
        self.assertEqual(game.status, STARTED)
        self.assertFalse(game.bsetup)
        self.assertFalse(game.wsetup)
        self.assertFalse(game.counted_as_active)
        self.assertEqual(app_state.g_cnt[0], initial_count)
        self.assertTrue(game.has_legal_move)

        await game.play_move(game.board.legal_moves()[0])
        self.assertEqual(game.ply, 1)
        self.assertEqual(game.status, STARTED)
        self.assertTrue(game.counted_as_active)
        self.assertEqual(app_state.g_cnt[0], initial_count + 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
