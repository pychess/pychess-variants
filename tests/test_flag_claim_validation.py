import asyncio
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import AioHTTPTestCase
from clock import first_move_timeout_reason
from const import FLAG, STARTED
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import insert_game_to_db
from variants import VARIANTS
from wsr import handle_abort_resign_abandon_flag, handle_byoyomi

from server import make_app

PERFS = new_default_perf_map(VARIANTS)


class FlagClaimValidationTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        self.wplayer = User(app_state, username="wplayer-flag", perfs=PERFS)
        self.bplayer = User(app_state, username="bplayer-flag", perfs=PERFS)

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
            "chess",
            "",
            self.wplayer,
            self.bplayer,
            rated=False,
        )

    async def play_white_first_move(self, game: Game) -> None:
        clocks = (game.clocks_w[0], game.clocks_b[0])
        await game.play_move("e2e4", clocks=clocks, ply=1)

    async def play_two_plies(self, game: Game) -> None:
        await self.play_white_first_move(game)
        clocks = (game.clocks_w[-1], game.clocks_b[-1])
        await game.play_move("e7e5", clocks=clocks, ply=2)

    @asynccontextmanager
    async def paused_countdown(self, game: Game, *, remaining: int, delay: int):
        clock = game.stopwatch
        await clock.cancel()
        clock.restart(remaining)
        waiting = asyncio.Event()
        release = asyncio.Event()
        checked = asyncio.Event()
        blocked = asyncio.Event()
        real_sleep = asyncio.sleep

        async def controlled_sleep(seconds):
            if asyncio.current_task() is task:
                if not waiting.is_set() and seconds == delay:
                    waiting.set()
                    await release.wait()
                else:
                    checked.set()
                    await blocked.wait()
            else:
                await real_sleep(seconds)

        async def resume():
            release.set()

            async def wait_until_checked():
                while not task.done() and not checked.is_set():
                    await real_sleep(0)

            await asyncio.wait_for(wait_until_checked(), timeout=1)

        with patch("clock.asyncio.sleep", new=controlled_sleep):
            task = asyncio.create_task(clock.countdown())
            clock.clock_task = task
            try:
                await asyncio.wait_for(waiting.wait(), timeout=1)
                yield resume
            finally:
                await clock.cancel()

    async def test_old_server_timeout_does_not_flag_a_new_byoyomi_turn(self):
        app_state = get_app_state(self.app)
        for player in (self.wplayer, self.bplayer):
            app_state.users[player.username] = player
        game = Game(
            app_state,
            id8(),
            "shogi",
            "",
            self.wplayer,
            self.bplayer,
            base=15,
            inc=60,
            byoyomi_period=1,
        )
        await insert_game_to_db(game, app_state)
        for _ in range(2):
            await game.play_move(game.board.legal_moves()[0], clocks=[900000, 5000])

        async with self.paused_countdown(game, remaining=0, delay=80) as resume:
            await handle_byoyomi(
                self.wplayer,
                {
                    "type": "byoyomi",
                    "color": "white",
                    "period": 0,
                    "positionId": game.position_id(),
                },
                game,
            )
            await game.play_move(game.board.legal_moves()[0], clocks=[60000, 5000])
            # A move at the main-time boundary can report zero before the next browser tick.
            await game.play_move(game.board.legal_moves()[0], clocks=[60000, 0])
            await game.play_move(game.board.legal_moves()[0], clocks=[60000, 0])
            await handle_byoyomi(
                self.bplayer,
                {
                    "type": "byoyomi",
                    "color": "black",
                    "period": 0,
                    "positionId": game.position_id(),
                },
                game,
            )
            self.assertGreater(game.get_board(full=True)["clocks"][1], 55000)

            await resume()

            self.assertEqual(game.status, STARTED)
            self.assertEqual(game.result, "*")

    async def test_restarting_same_position_invalidates_pending_timeout(self):
        game = self.new_game()
        await self.play_two_plies(game)

        async with self.paused_countdown(game, remaining=0, delay=20) as resume:
            game.stopwatch.restart(0)
            await resume()

            self.assertEqual(game.status, STARTED)
            self.assertEqual(game.result, "*")

    async def test_restart_while_timeout_waits_for_move_lock_does_not_flag(self):
        game = self.new_game()
        await self.play_two_plies(game)
        waiting_for_lock = asyncio.Event()
        acquire = game.move_lock.acquire

        async def signal_acquire():
            waiting_for_lock.set()
            return await acquire()

        await game.move_lock.acquire()
        try:
            with patch.object(game.move_lock, "acquire", new=signal_acquire):
                async with self.paused_countdown(game, remaining=0, delay=20) as resume:
                    resumed = asyncio.create_task(resume())
                    await asyncio.wait_for(waiting_for_lock.wait(), timeout=1)
                    game.stopwatch.restart(0)
                    game.move_lock.release()
                    await resumed

                    self.assertEqual(game.status, STARTED)
                    self.assertEqual(game.result, "*")
        finally:
            if game.move_lock.locked():
                game.move_lock.release()

    async def test_tick_from_previous_turn_does_not_deduct_from_restarted_clock(self):
        game = self.new_game()
        await self.play_two_plies(game)

        async with self.paused_countdown(game, remaining=1000, delay=1) as resume:
            game.stopwatch.restart(5000)
            await resume()

            self.assertEqual(game.stopwatch.secs, 5000)
            self.assertEqual(game.status, STARTED)

    async def test_server_timeout_still_flags_current_expired_turn(self):
        game = self.new_game()
        await self.play_two_plies(game)

        async with self.paused_countdown(game, remaining=0, delay=20) as resume:
            await resume()

            self.assertEqual(game.status, FLAG)
            self.assertEqual(game.result, "0-1")

    async def test_flag_ignored_if_not_side_to_move(self):
        game = self.new_game()
        await self.play_two_plies(game)

        ws = AsyncMock()
        await handle_abort_resign_abandon_flag(
            ws,
            users={},
            user=self.bplayer,
            data={"type": "flag", "gameId": game.id},
            game=game,
        )

        self.assertEqual(game.status, STARTED)
        self.assertEqual(game.result, "*")
        ws.send_str.assert_not_awaited()

    async def test_flag_ignored_before_server_timeout(self):
        game = self.new_game()
        await self.play_two_plies(game)

        ws = AsyncMock()
        await handle_abort_resign_abandon_flag(
            ws,
            users={},
            user=self.wplayer,
            data={"type": "flag", "gameId": game.id},
            game=game,
        )

        self.assertEqual(game.status, STARTED)
        self.assertEqual(game.result, "*")
        ws.send_str.assert_not_awaited()

    async def test_flag_accepted_when_server_clock_is_expired(self):
        game = self.new_game()
        await self.play_two_plies(game)

        # Force white's server-side remaining time to be negative.
        game.last_server_clock -= (game.clocks_w[-1] / 1000) + 1

        ws = AsyncMock()
        await handle_abort_resign_abandon_flag(
            ws,
            users={},
            user=self.wplayer,
            data={"type": "flag", "gameId": game.id},
            game=game,
        )

        self.assertEqual(game.status, FLAG)
        self.assertEqual(game.result, "0-1")
        ws.send_str.assert_awaited()

    async def test_first_move_timeout_aborts_rr_arrangement_games(self):
        game = Game(
            get_app_state(self.app),
            id8(),
            "chess",
            "",
            self.wplayer,
            self.bplayer,
            rated=False,
            tournamentId="tour12345",
            tournamentArrangementId="tour12345:wplayer-flag:bplayer-flag",
        )

        self.assertEqual(first_move_timeout_reason(game, ply=0), "abort")
        self.assertEqual(first_move_timeout_reason(game, ply=1), "abort")

    async def test_first_move_timeout_flags_non_arrangement_tournament_games(self):
        game = Game(
            get_app_state(self.app),
            id8(),
            "chess",
            "",
            self.wplayer,
            self.bplayer,
            rated=False,
            tournamentId="tour12345",
        )

        self.assertEqual(first_move_timeout_reason(game, ply=0), "flag")
        self.assertEqual(first_move_timeout_reason(game, ply=1), "flag")


if __name__ == "__main__":
    unittest.main(verbosity=2)
