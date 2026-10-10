import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from bug.utils_bug import new_game_bughouse
from const import STARTED
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from seek import Seek
from user import User
from utils import (
    REALTIME_GAME_IN_PROGRESS_MESSAGE,
    join_seek,
    realtime_game_conflict,
)
from variants import VARIANTS

from server import make_app

test_logger.init_test_logger()
PERFS = new_default_perf_map(VARIANTS)


class RealtimeGameAdmissionTestCase(AioHTTPTestCase):
    async def startup(self, app):
        state = get_app_state(app)
        self.alice = User(state, username="alice-live", perfs=PERFS)
        self.bob = User(state, username="bob-live", perfs=PERFS)
        self.carol = User(state, username="carol-live", perfs=PERFS)
        self.bot = User(state, username="test-engine", bot=True, perfs=PERFS)
        for user in (self.alice, self.bob, self.carol, self.bot):
            state.users[user.username] = user

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        state = get_app_state(self.app)
        for game in list(state.games.values()):
            if game.status <= STARTED:
                if game.server_variant.two_boards:
                    await game.gameClocks.cancel_stopwatches()
                else:
                    await game.stopwatch.cancel()
        await self.client.close()

    def add_untouched_ai_game(self, game_id="ghost001") -> Game:
        state = get_app_state(self.app)
        game = Game(
            state,
            game_id,
            "chess",
            "",
            self.alice,
            self.bot,
            base=180,
            inc=0,
            rated=False,
        )
        state.games[game.id] = game
        self.assertLessEqual(game.status, STARTED)
        self.assertEqual(len(game.board.move_stack), 0)
        return game

    async def test_untouched_ai_game_blocks_second_realtime_game_even_without_hint(self):
        state = get_app_state(self.app)
        game = self.add_untouched_ai_game()

        # The admission rule must not depend on this lossy UI/navigation hint.
        self.alice.game_in_progress = None

        seek = Seek("second01", self.alice, "chess", player1=self.alice)
        response = await join_seek(state, self.bob, seek)

        self.assertEqual(
            response,
            {"type": "error", "message": REALTIME_GAME_IN_PROGRESS_MESSAGE},
        )
        self.assertIsNone(seek.player2)
        self.assertIn(game.id, state.games)

    async def test_rejected_join_does_not_leave_seek_occupied(self):
        state = get_app_state(self.app)
        self.add_untouched_ai_game()

        seek = Seek("retry001", self.bob, "chess", player1=self.bob)
        response = await join_seek(state, self.alice, seek)

        self.assertEqual(
            response,
            {"type": "error", "message": REALTIME_GAME_IN_PROGRESS_MESSAGE},
        )
        self.assertIsNone(seek.player2)

    async def test_active_realtime_game_does_not_block_correspondence(self):
        state = get_app_state(self.app)
        self.add_untouched_ai_game()

        seek = Seek("corr0001", self.alice, "chess", day=2, player1=self.alice)
        response = await join_seek(state, self.bob, seek)

        self.assertEqual(response["type"], "new_game")
        corr_game = state.games[response["gameId"]]
        self.assertTrue(corr_game.corr)

    async def test_two_board_one_person_team_is_allowed(self):
        state = get_app_state(self.app)
        seek = Seek(
            "bugsim01",
            self.alice,
            "bughouse",
            color="w",
            player1=self.alice,
            player2=self.bob,
            bugPlayer1=self.alice,
            bugPlayer2=self.carol,
        )
        state.seeks[seek.id] = seek

        response = await new_game_bughouse(state, seek.id)

        self.assertEqual(response["type"], "new_game")
        game = state.games[response["gameId"]]
        self.assertEqual(game.team1, [self.alice.username, self.alice.username])
        self.assertEqual(game.status, STARTED)

    async def test_simul_host_can_have_multiple_boards_only_in_same_simul(self):
        state = get_app_state(self.app)
        first = Game(
            state,
            "simul001",
            "chess",
            "",
            self.alice,
            self.bob,
            rated=False,
            simulId="SIMUL123",
        )
        state.games[first.id] = first

        same_simul = realtime_game_conflict(
            state,
            (self.alice, self.carol),
            allowed_simul_id="SIMUL123",
            simul_host_username=self.alice.username,
        )
        unrelated = realtime_game_conflict(state, (self.alice, self.carol))

        self.assertIsNone(same_simul)
        self.assertIsNotNone(unrelated)
        assert unrelated is not None
        self.assertIs(unrelated[1], first)
