import asyncio
import json
from unittest.mock import AsyncMock

import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from const import CREATED, RATED, STARTED
from fairy import BLACK
from fairy.jieqi import BLACK_PIECES, RED_PIECES
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import insert_game_to_db, load_game_from_doc
from variants import VARIANTS
from wsr import (
    handle_board,
    handle_byoyomi,
    handle_reject_takeback,
    handle_takeback,
    takeback_allowed,
)

from server import make_app

test_logger.init_test_logger()

TEST_PLAYER_PERFS = new_default_perf_map(VARIANTS)


class TakebackBroadcastTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    async def test_bot_takeback_broadcasts_to_all_player_sockets(self):
        app_state = get_app_state(self.app)
        player = User(app_state, username="takeback-user", perfs=TEST_PLAYER_PERFS)
        bot = app_state.users["Random-Mover"]
        game = Game(
            app_state,
            id8(),
            "cambodian",
            "",
            player,
            bot,
            rated=False,
            create=True,
        )

        await game.play_move("e3e4")
        await game.play_move("c8c7")
        await game.play_move("f3f4")
        await game.play_move("e8d7")

        ws1 = AsyncMock()
        ws2 = AsyncMock()
        player.add_ws_for_game(game.id, ws1)
        player.add_ws_for_game(game.id, ws2)

        await handle_takeback(ws1, player, game)

        ws1.send_str.assert_awaited()
        ws2.send_str.assert_awaited()

        payload1 = json.loads(ws1.send_str.await_args.args[0])
        payload2 = json.loads(ws2.send_str.await_args.args[0])

        self.assertTrue(payload1["takeback"])
        self.assertTrue(payload2["takeback"])
        self.assertEqual(payload1["ply"], 2)
        self.assertEqual(payload2["ply"], 2)

    async def test_takeback_waits_for_move_lock(self):
        app_state = get_app_state(self.app)
        player = User(app_state, username="takeback-lock-user", perfs=TEST_PLAYER_PERFS)
        bot = app_state.users["Random-Mover"]
        game = Game(
            app_state,
            id8(),
            "cambodian",
            "",
            player,
            bot,
            rated=False,
            create=True,
        )

        await game.play_move("e3e4")
        await game.play_move("c8c7")
        await game.play_move("f3f4")
        await game.play_move("e8d7")

        ws = AsyncMock()
        player.add_ws_for_game(game.id, ws)

        await game.move_lock.acquire()
        task = asyncio.create_task(handle_takeback(ws, player, game))
        try:
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertEqual(
                game.board.fen, "rn1m1snr/2sk4/pppppppp/8/4PP2/PPPP2PP/8/RNSKMSNR w DEd - 1 3"
            )
        finally:
            game.move_lock.release()

        await task
        payload = json.loads(ws.send_str.await_args.args[0])
        self.assertTrue(payload["takeback"])
        self.assertEqual(payload["ply"], 2)

    async def test_casual_human_takeback_requires_opponent_acceptance(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="takeback-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="takeback-black", perfs=TEST_PLAYER_PERFS)
        game = Game(app_state, id8(), "cambodian", "", white, black, rated=False, create=True)

        await game.play_move("e3e4")
        await game.play_move("c8c7")
        await game.play_move("f3f4")
        await game.play_move("e8d7")

        white_ws = AsyncMock()
        black_ws = AsyncMock()
        white.add_ws_for_game(game.id, white_ws)
        black.add_ws_for_game(game.id, black_ws)

        await handle_takeback(white_ws, white, game)

        self.assertEqual(game.board.ply, 4)
        self.assertEqual(game.takeback_offer, (white.username, 4))
        offer = json.loads(black_ws.send_str.await_args.args[0])
        self.assertEqual(offer["type"], "takeback_offer")
        self.assertEqual(offer["username"], white.username)

        await handle_takeback(black_ws, black, game)

        self.assertIsNone(game.takeback_offer)
        self.assertEqual(game.board.ply, 2)
        board = json.loads(white_ws.send_str.await_args.args[0])
        self.assertTrue(board["takeback"])
        self.assertEqual(board["ply"], 2)

    async def test_casual_human_can_reject_takeback(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="reject-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="reject-black", perfs=TEST_PLAYER_PERFS)
        game = Game(app_state, id8(), "cambodian", "", white, black, rated=False, create=True)
        await game.play_move("e3e4")
        await game.play_move("c8c7")

        black_ws = AsyncMock()
        black.add_ws_for_game(game.id, black_ws)
        await handle_takeback(AsyncMock(), white, game)
        await handle_reject_takeback(black, game)

        self.assertIsNone(game.takeback_offer)
        self.assertEqual(game.board.ply, 2)
        response = json.loads(black_ws.send_str.await_args.args[0])
        self.assertEqual(response["type"], "takeback_rejected")

    async def test_takeback_after_requesters_move_rewinds_one_ply(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="single-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="single-black", perfs=TEST_PLAYER_PERFS)
        game = Game(app_state, id8(), "cambodian", "", white, black, rated=False, create=True)
        await game.play_move("e3e4")
        await game.play_move("c8c7")
        await game.play_move("f3f4")
        await game.play_move("e8d7")

        await handle_takeback(AsyncMock(), black, game)
        await handle_takeback(AsyncMock(), white, game)

        self.assertEqual(game.board.ply, 3)
        self.assertEqual(len(game.clocks_w), 3)
        self.assertEqual(len(game.clocks_b), 2)

    async def test_casual_duck_game_allows_takeback(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="duck-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="duck-black", perfs=TEST_PLAYER_PERFS)
        game = Game(app_state, id8(), "duck", "", white, black, rated=False, create=True)
        await game.play_move(game.board.legal_moves()[0])
        await game.play_move(game.board.legal_moves()[0])

        await handle_takeback(AsyncMock(), black, game)
        await handle_takeback(AsyncMock(), white, game)

        self.assertEqual(game.board.ply, 1)

    async def test_reloaded_jieqi_takeback_replays_revealed_moves(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="jieqi-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="jieqi-black", perfs=TEST_PLAYER_PERFS)
        app_state.users[white.username] = white
        app_state.users[black.username] = black
        game = Game(app_state, id8(), "jieqi", "", white, black, rated=False, create=True)
        game.board.set_jieqi_initial_pieces(BLACK_PIECES, RED_PIECES)
        await insert_game_to_db(game, app_state)

        await game.play_move("c4c5")
        expected_fen = game.board.fen
        expected_mapping = dict(game.board.jieqi_covered_pieces)
        await game.play_move("c7c6")

        assert app_state.db is not None
        persisted = await app_state.db.game.find_one({"_id": game.id})
        assert persisted is not None
        await game.stopwatch.cancel()
        reloaded = await load_game_from_doc(app_state, persisted)
        self.assertIsInstance(reloaded, Game)
        assert isinstance(reloaded, Game)
        reloaded.get_board(full=True)

        await reloaded.takeback(reloaded.bplayer)

        self.assertEqual(reloaded.board.ply, 1)
        self.assertEqual(reloaded.board.fen, expected_fen)
        self.assertEqual(reloaded.board.jieqi_covered_pieces, expected_mapping)
        self.assertEqual(reloaded.board.move_stack, [game.board.move_stack[0]])
        await reloaded.stopwatch.cancel()

    async def test_rated_game_rejects_takeback_server_side(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="rated-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="rated-black", perfs=TEST_PLAYER_PERFS)
        game = Game(app_state, id8(), "cambodian", "", white, black, rated=RATED, create=True)
        await game.play_move("e3e4")
        await game.play_move("c8c7")

        ws = AsyncMock()
        await handle_takeback(ws, white, game)

        self.assertEqual(game.board.ply, 2)
        self.assertIsNone(game.takeback_offer)
        response = json.loads(ws.send_str.await_args.args[0])
        self.assertEqual(response["type"], "error")
        self.assertIn("not allowed", response["message"])

    async def test_takeback_to_ply_zero_resets_active_game_lifecycle(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="lifecycle-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="lifecycle-black", perfs=TEST_PLAYER_PERFS)
        game = Game(app_state, id8(), "cambodian", "", white, black, rated=False, create=True)
        await insert_game_to_db(game, app_state)
        assert app_state.db is not None
        initial_count = app_state.g_cnt[0]

        await game.play_move("e3e4")
        await game.play_move("c8c7")
        self.assertEqual(game.status, STARTED)
        self.assertEqual(app_state.g_cnt[0], initial_count + 1)

        await handle_takeback(AsyncMock(), white, game)
        await handle_takeback(AsyncMock(), black, game)

        self.assertEqual(game.board.ply, 0)
        self.assertEqual(game.status, CREATED)
        self.assertEqual(app_state.g_cnt[0], initial_count)
        document = await app_state.db.game.find_one({"_id": game.id})
        self.assertEqual(document["s"], CREATED)

        await game.play_move("e3e4")
        self.assertEqual(game.status, STARTED)
        self.assertEqual(app_state.g_cnt[0], initial_count + 1)

    async def test_takeback_restores_byoyomi_state_at_start_of_turn(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="byoyomi-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="byoyomi-black", perfs=TEST_PLAYER_PERFS)
        app_state.users[white.username] = white
        app_state.users[black.username] = black
        game = Game(
            app_state,
            id8(),
            "shogi",
            "",
            white,
            black,
            base=1,
            inc=5,
            byoyomi_period=3,
            rated=False,
            create=True,
        )
        await insert_game_to_db(game, app_state)
        assert app_state.db is not None
        await game.play_move(game.board.legal_moves()[0])

        original_periods = game.byoyomi_periods.copy()
        await handle_byoyomi(
            black,
            {
                "type": "byoyomi",
                "color": "black",
                "period": 2,
            },
            game,
        )
        self.assertEqual(game.byoyomi_periods, original_periods)
        self.assertEqual(game.byo_correction, 0)

        await handle_byoyomi(
            black,
            {
                "type": "byoyomi",
                "color": "black",
                "period": 2,
                "positionId": game.position_id(),
            },
            game,
        )
        game.overtime = True
        await game.play_move(game.board.legal_moves()[0])
        self.assertEqual(game.byoyomi_periods[BLACK], 2)
        self.assertTrue(game.overtime)

        persisted = await app_state.db.game.find_one({"_id": game.id})
        assert persisted is not None
        await game.stopwatch.cancel()
        reloaded = await load_game_from_doc(app_state, persisted)
        self.assertIsInstance(reloaded, Game)
        assert isinstance(reloaded, Game)
        self.assertEqual(len(reloaded.byoyomi_state_stack), reloaded.board.ply + 1)
        self.assertEqual(reloaded.byoyomi_periods, [3, 2])
        self.assertTrue(reloaded.overtime)
        self.assertTrue(takeback_allowed(reloaded, reloaded.bplayer))
        abandoned_position_id = reloaded.position_id()

        await handle_takeback(AsyncMock(), reloaded.bplayer, reloaded)
        self.assertEqual(reloaded.takeback_offer, (reloaded.bplayer.username, 2))
        await handle_takeback(AsyncMock(), reloaded.wplayer, reloaded)

        self.assertEqual(reloaded.board.ply, 1)
        self.assertEqual(reloaded.byoyomi_periods, [3, 3])
        self.assertFalse(reloaded.overtime)
        self.assertEqual(reloaded.byo_correction, 0)
        self.assertNotEqual(abandoned_position_id, reloaded.position_id())
        await handle_byoyomi(
            reloaded.wplayer,
            {
                "type": "byoyomi",
                "color": "white",
                "period": 2,
                "positionId": abandoned_position_id,
            },
            reloaded,
        )
        self.assertEqual(reloaded.byoyomi_periods, [3, 3])
        self.assertEqual(reloaded.byo_correction, 0)
        document = await app_state.db.game.find_one({"_id": reloaded.id})
        self.assertEqual(document["byop"], [3, 3])
        self.assertFalse(document["byoo"])
        self.assertEqual(len(document["byost"]), 1)

    async def test_zero_main_time_byoyomi_stays_in_overtime_after_reload_and_takeback(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="zero-byo-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="zero-byo-black", perfs=TEST_PLAYER_PERFS)
        app_state.users[white.username] = white
        app_state.users[black.username] = black
        game = Game(
            app_state,
            id8(),
            "torishogi",
            "",
            white,
            black,
            base=0,
            inc=5,
            byoyomi_period=3,
        )
        await insert_game_to_db(game, app_state)
        self.assertTrue(game.overtime)
        self.assertEqual(game.byoyomi_periods, [2, 2])
        self.assertEqual(game.clocks, (5000, 5000))
        for _ in range(2):
            await game.play_move(game.board.legal_moves()[0])
        await handle_byoyomi(
            white,
            {
                "type": "byoyomi",
                "color": "white",
                "period": 1,
                "positionId": game.position_id(),
            },
            game,
        )
        await game.play_move(game.board.legal_moves()[0])

        persisted = await app_state.db.game.find_one({"_id": game.id})
        await game.stopwatch.cancel()
        reloaded = await load_game_from_doc(app_state, persisted)
        assert isinstance(reloaded, Game)
        self.assertTrue(reloaded.overtime)
        self.assertEqual(reloaded.byoyomi_periods, [1, 2])
        await handle_takeback(AsyncMock(), reloaded.wplayer, reloaded)
        await handle_takeback(AsyncMock(), reloaded.bplayer, reloaded)

        self.assertEqual(reloaded.board.ply, 2)
        self.assertTrue(reloaded.overtime)
        self.assertEqual(reloaded.byoyomi_periods, [2, 2])

    async def test_pending_takeback_offer_is_resent_on_reconnect(self):
        app_state = get_app_state(self.app)
        white = User(app_state, username="reconnect-white", perfs=TEST_PLAYER_PERFS)
        black = User(app_state, username="reconnect-black", perfs=TEST_PLAYER_PERFS)
        game = Game(app_state, id8(), "cambodian", "", white, black, rated=False, create=True)
        await game.play_move("e3e4")
        await game.play_move("c8c7")
        await handle_takeback(AsyncMock(), white, game)

        black_ws = AsyncMock()
        await handle_board(black_ws, black, game)

        reconnect_message = json.loads(black_ws.send_str.await_args.args[0])
        self.assertEqual(reconnect_message["type"], "takeback_offer")
        self.assertEqual(reconnect_message["username"], white.username)
        self.assertEqual(game.board.ply, 2)
