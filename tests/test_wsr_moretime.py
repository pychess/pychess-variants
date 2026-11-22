import asyncio
import json
from unittest.mock import AsyncMock

import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from fairy import BLACK, WHITE
from game import Game
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from user import User
from wsr import MORE_TIME, handle_moretime

from server import make_app

test_logger.init_test_logger()


class MoreTimeTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    def create_game(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="moretime-white")
        black = User(app_state, username="moretime-black", anon=True)
        app_state.users[white.username] = white
        app_state.users[black.username] = black
        game = Game(app_state, id8(), "chess", "", white, black, base=5, inc=0)
        return app_state.users, game

    async def test_gift_to_waiting_opponent_survives_move_and_refresh(self):
        users, game = self.create_game()
        await game.play_move("e2e4")
        await game.play_move("e7e5")
        for giver, recipient_color, move in (
            (game.wplayer, BLACK, "g1f3"),
            (game.bplayer, WHITE, "g8f6"),
        ):
            with self.subTest(recipient_color=recipient_color):
                before = game.clocks[recipient_color]
                request = {"type": "moretime", "gameId": game.id}
                await handle_moretime(users, giver, request, game)
                await handle_moretime(users, giver, request, game)
                expected = before + 2 * MORE_TIME
                self.assertEqual(game.get_board(full=True)["clocks"][recipient_color], expected)

                # The move sender includes both clocks, but only their own clock
                # is saved by play_move. The gift must already be on the server.
                clocks = list(game.clocks)
                clocks[recipient_color] = expected
                await game.play_move(move, clocks=clocks)
                self.assertEqual(game.get_board()["clocks"][recipient_color], expected)
                self.assertEqual(game.stopwatch.secs, expected)

    async def test_gift_to_running_opponent_is_saved_and_broadcast_once(self):
        users, game = self.create_game()
        await game.play_move("e2e4")
        await game.play_move("e7e5")
        recipient_ws = AsyncMock()
        spectator_ws = AsyncMock()
        game.wplayer.add_ws_for_game(game.id, recipient_ws)
        spectator = User(get_app_state(self.app), username="moretime-spectator")
        spectator.add_ws_for_game(game.id, spectator_ws)
        game.spectators.add(spectator)
        game.last_server_clock -= 5
        game.stopwatch.secs -= 5000
        before = game.get_board(full=True)["clocks"][WHITE]
        timer_before = game.stopwatch.secs

        await handle_moretime(users, game.bplayer, {"type": "moretime", "gameId": game.id}, game)

        self.assertAlmostEqual(
            game.get_board(full=True)["clocks"][WHITE], before + MORE_TIME, delta=100
        )
        self.assertEqual(game.stopwatch.secs, timer_before + MORE_TIME)
        for ws in (recipient_ws, spectator_ws):
            ws.send_str.assert_awaited_once()
            self.assertEqual(
                json.loads(ws.send_str.await_args.args[0]),
                {"type": "moretime", "username": game.wplayer.username},
            )

    async def test_gift_before_first_move_keeps_clock_stopped(self):
        users, game = self.create_game()
        await handle_moretime(users, game.bplayer, {"type": "moretime", "gameId": game.id}, game)
        self.assertFalse(game.stopwatch.running)
        self.assertEqual(game.clocks[WHITE], 300000 + MORE_TIME)

    async def test_gift_waits_for_move_lock(self):
        users, game = self.create_game()
        await game.move_lock.acquire()
        task = asyncio.create_task(
            handle_moretime(users, game.wplayer, {"type": "moretime", "gameId": game.id}, game)
        )
        try:
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertEqual(game.clocks[BLACK], 300000)
        finally:
            game.move_lock.release()
            await task
        self.assertEqual(game.clocks[BLACK], 300000 + MORE_TIME)
