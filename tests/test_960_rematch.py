import asyncio
import unittest
from unittest.mock import patch

import game
import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from bug.game_bug import GameBug
from bug.wsr_bug import handle_rematch_bughouse
from catalogued.variants import register_catalogued_variant_doc
from const import RATED
from fairy import FairyBoard
from fairy.fairy_board import STANDARD_FEN
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import insert_game_to_db, load_game_from_doc
from utils import pgn as export_pgn
from variants import VARIANTS, unregister_catalogued_server_variant
from wsr import handle_rematch

from server import make_app

game.KEEP_TIME = 0
game.MAX_PLY = 120

test_logger.init_test_logger()

PERFS = {
    "newplayer": new_default_perf_map(VARIANTS),
}

ONE_TEST_ONLY = False


class FakeWs:
    async def send_str(self, msg):
        pass


class RamatchChess960GameTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        self.fake_ws = FakeWs()

        self.Aplayer = User(get_app_state(self.app), username="Aplayer", perfs=PERFS["newplayer"])
        self.Bplayer = User(get_app_state(self.app), username="Bplayer", perfs=PERFS["newplayer"])
        self.Cplayer = User(get_app_state(self.app), username="Cplayer", perfs=PERFS["newplayer"])
        self.Dplayer = User(get_app_state(self.app), username="Dplayer", perfs=PERFS["newplayer"])

        app_state.users["Aplayer"] = self.Aplayer
        app_state.users["Bplayer"] = self.Bplayer
        app_state.users["Cplayer"] = self.Cplayer
        app_state.users["Dplayer"] = self.Dplayer

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def play_game_and_rematch_game(self, game):
        app_state = get_app_state(self.app)
        await game.game_ended(game.wplayer, "flag")

        data = {"gameId": game.id, "handicap": False}
        resp = None
        if game.variant == "bughouse":

            async def send_rematch(user, delay=0.0):
                if delay:
                    await asyncio.sleep(delay)
                return await handle_rematch_bughouse(app_state, game, user)

            users = list(game.all_players)
            tasks = [asyncio.create_task(send_rematch(user)) for user in users]
            responses = await asyncio.gather(*tasks)
            resp = next(
                response
                for response in responses
                if response is not None and response.get("type") == "new_game"
            )
        else:
            for user in game.all_players:
                resp = await handle_rematch(app_state, self.fake_ws, user, data, game)

        return resp

    def register_fixed_community_variant(self, name="pawnsideways960"):
        app_state = get_app_state(self.app)
        fen = "4k3/8/8/8/8/8/8/RK1R4 w DA - 0 1"
        register_catalogued_variant_doc(
            app_state,
            {
                "name": name,
                "ini": f"[{name}:pawnsideways]\nchess960 = true\nstartFen = {fen}\n",
                "startFen": fen,
                "visibility": "public",
            },
        )
        self.addCleanup(unregister_catalogued_server_variant, name)
        return fen

    async def test_community_fixed_start_persists_and_replays_after_reload(self):
        app_state = get_app_state(self.app)
        for name in ("pawnsideways960", "fixed_castling"):
            with self.subTest(variant=name):
                fen = self.register_fixed_community_variant(name)
                current = Game(app_state, name, name, "", self.Aplayer, self.Bplayer)
                app_state.games[current.id] = current
                await insert_game_to_db(current, app_state)
                document = await app_state.db.game.find_one({"_id": current.id})
                self.assertEqual(document["if"], fen)
                self.assertEqual(document["z"], 0)

                moves = ["b1d1", "e8e7", "a1a2", "e7e6", "a2a3", "e6e5"]
                for move in moves:
                    await current.play_move(move)
                await current.game_ended(current.bplayer, "resign")
                document = await app_state.db.game.find_one({"_id": current.id})
                self.assertEqual(document["if"], fen)

                # A saved game must not consult the variant's default again.
                with patch.object(
                    FairyBoard, "start_fen", side_effect=AssertionError("regenerated start")
                ):
                    for _ in range(2):
                        app_state.games.pop(current.id, None)
                        reloaded = await load_game_from_doc(app_state, document)
                        self.assertIsInstance(reloaded, Game)
                        reloaded.create_steps()
                        self.assertEqual(reloaded.initial_fen, fen)
                        self.assertEqual(reloaded.board.variant, name)
                        self.assertEqual(reloaded.board.move_stack, moves)
                        self.assertEqual(reloaded.steps[0]["fen"], fen)
                        self.assertEqual(reloaded.steps[1]["san"], "O-O")
                        self.assertEqual(reloaded.steps[-1]["fen"], current.board.fen)

    async def test_community_960_rematches_keep_fixed_start_beyond_two_games(self):
        app_state = get_app_state(self.app)
        fen = self.register_fixed_community_variant()
        current = Game(app_state, "12345678", "pawnsideways960", "", self.Aplayer, self.Bplayer)
        app_state.games[current.id] = current
        with patch.object(FairyBoard, "shuffle_start", side_effect=AssertionError("randomized")):
            for _ in range(3):
                previous = current
                response = await self.play_game_and_rematch_game(current)
                current = app_state.games[response["gameId"]]
                self.assertEqual(current.initial_fen, fen)
                self.assertEqual(current.board.variant, "pawnsideways960")
                self.assertIs(current.wplayer, previous.bplayer)
                self.assertIs(current.bplayer, previous.wplayer)

    def register_random_community_variant(self):
        name = "testsideways960"
        register_catalogued_variant_doc(
            get_app_state(self.app),
            {
                "name": name,
                "ini": f"[{name}:pawnsideways]\nchess960 = true",
                "startFen": STANDARD_FEN,
                "visibility": "public",
            },
        )
        self.addCleanup(unregister_catalogued_server_variant, name)
        return name

    async def test_community_random_start_is_saved_and_replayed_with_literal_name(self):
        app_state = get_app_state(self.app)
        name = self.register_random_community_variant()
        current = Game(app_state, "random01", name, "", self.Aplayer, self.Bplayer)
        app_state.games[current.id] = current
        await insert_game_to_db(current, app_state)
        initial_fen = current.initial_fen
        self.assertTrue(current.chess960)
        self.assertGreaterEqual(current.posnum, 0)
        self.assertEqual(current.board.variant, name)
        for _ in range(4):
            await current.play_move(current.board.legal_moves()[0])
        await current.game_ended(current.bplayer, "resign")
        document = await app_state.db.game.find_one({"_id": current.id})
        self.assertEqual(document["v"], name)
        self.assertEqual(document["z"], 1)
        self.assertEqual(document["if"], initial_fen)
        self.assertIn('[Variant "Testsideways960"]', current.pgn)
        self.assertIn('[Variant "Testsideways960"]', export_pgn(document))
        app_state.games.pop(current.id, None)
        with patch.object(FairyBoard, "start_fen", side_effect=AssertionError("regenerated start")):
            reloaded = await load_game_from_doc(app_state, document)
            reloaded.create_steps()
        self.assertTrue(reloaded.chess960)
        self.assertEqual(reloaded.steps[0]["fen"], initial_fen)
        self.assertEqual(reloaded.steps[-1]["fen"], current.board.fen)

    async def test_community_random_rematches_reuse_then_change_start(self):
        app_state = get_app_state(self.app)
        name = self.register_random_community_variant()
        current = Game(app_state, "random02", name, "", self.Aplayer, self.Bplayer)
        app_state.games[current.id] = current
        first_fen = current.initial_fen
        for rematch in range(2):
            response = await self.play_game_and_rematch_game(current)
            current = app_state.games[response["gameId"]]
            self.assertTrue(current.chess960)
            self.assertEqual(current.board.variant, name)
            if rematch == 0:
                self.assertEqual(current.initial_fen, first_fen)
            else:
                self.assertNotEqual(current.initial_fen, first_fen)

    async def test_community_supplied_and_missing_historical_starts_are_not_randomized(self):
        app_state = get_app_state(self.app)
        name = self.register_random_community_variant()
        supplied = "4k3/8/8/8/8/8/8/RK1R4 w DA - 0 1"
        current = Game(app_state, "random03", name, supplied, self.Aplayer, self.Bplayer)
        self.assertEqual(current.initial_fen, supplied)
        self.assertFalse(current.chess960)
        await current.stopwatch.cancel()
        with patch("fairy.fairy_board.random.shuffle", side_effect=AssertionError("randomized")):
            historical = Game(
                app_state,
                "random04",
                name,
                "",
                self.Aplayer,
                self.Bplayer,
                chess960=True,
                create=False,
            )
        self.assertEqual(historical.initial_fen, STANDARD_FEN)
        await historical.stopwatch.cancel()

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_ramatch_ataxx(self):
        app_state = get_app_state(self.app)
        game = Game(
            app_state,
            "12345678",
            "ataxx",
            "",
            self.Aplayer,
            self.Bplayer,
            chess960=False,
        )
        await self.play_the_match(game)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_ramatch_bug_2vs2(self):
        app_state = get_app_state(self.app)
        game = GameBug(
            app_state,
            "12345678",
            "bughouse",
            "",
            self.Aplayer,
            self.Bplayer,
            self.Cplayer,
            self.Dplayer,
            chess960=True,
        )
        await self.play_the_match(game)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_ramatch_bug_1vs2(self):
        app_state = get_app_state(self.app)
        game = GameBug(
            app_state,
            "12345678",
            "bughouse",
            "",
            self.Aplayer,
            self.Aplayer,
            self.Cplayer,
            self.Dplayer,
            chess960=True,
        )
        await self.play_the_match(game)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_ramatch_bug_1vs1(self):
        app_state = get_app_state(self.app)
        game = GameBug(
            app_state,
            "12345678",
            "bughouse",
            "",
            self.Aplayer,
            self.Aplayer,
            self.Bplayer,
            self.Bplayer,
            chess960=True,
        )
        await self.play_the_match(game)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_ramatch_chess(self):
        app_state = get_app_state(self.app)
        game = Game(
            app_state,
            "12345678",
            "chess",
            "",
            self.Aplayer,
            self.Bplayer,
            chess960=True,
        )
        await self.play_the_match(game)

    async def test_atomic960_rematches_stay_rated(self):
        app_state = get_app_state(self.app)
        current_game = Game(
            app_state,
            "12345678",
            "atomic",
            "",
            self.Aplayer,
            self.Bplayer,
            rated=RATED,
            chess960=True,
        )
        app_state.games[current_game.id] = current_game

        for _ in range(2):
            response = await self.play_game_and_rematch_game(current_game)
            current_game = app_state.games[response["gameId"]]
            self.assertEqual(RATED, current_game.rated)

    async def test_bughouse960_late_rematch_returns_existing_game(self):
        app_state = get_app_state(self.app)
        game = GameBug(
            app_state,
            "12345678",
            "bughouse",
            "",
            self.Aplayer,
            self.Bplayer,
            self.Cplayer,
            self.Dplayer,
            chess960=True,
        )
        app_state.games[game.id] = game
        await game.game_ended(game.wplayer, "flag")

        async def send_rematch(user, delay=0.0):
            await asyncio.sleep(delay)
            return await handle_rematch_bughouse(app_state, game, user)

        responses = await asyncio.gather(
            send_rematch(self.Aplayer, delay=0.0),
            send_rematch(self.Bplayer, delay=0.01),
            send_rematch(self.Cplayer, delay=0.02),
            send_rematch(self.Dplayer, delay=0.03),
        )
        rematch_resp = next(
            resp for resp in responses if resp is not None and resp.get("type") == "new_game"
        )
        game2 = app_state.games[rematch_resp["gameId"]]
        self.assertEqual(game2.initial_fen, game.initial_fen)

        await game2.game_ended(game2.wplayer, "flag")

        existing_game_ids = set(app_state.games.keys())
        late_resp = await send_rematch(self.Dplayer, delay=0.02)
        self.assertIsNotNone(late_resp)
        self.assertEqual(late_resp.get("type"), "view_rematch")
        self.assertEqual(late_resp.get("gameId"), game2.id)
        self.assertEqual(existing_game_ids, set(app_state.games.keys()))

    async def play_the_match(self, game):
        app_state = get_app_state(self.app)
        app_state.games[game.id] = game
        resp = {
            "gameId": game.id,
            "wplayer": "Aplayer",
            "bplayer": "Bplayer",
        }

        x_game_fen = game.initial_fen
        y_game_fen = game.initial_fen

        for i in range(2):
            game = app_state.games[resp["gameId"]]

            resp = await self.play_game_and_rematch_game(game)

            new_game_fen = app_state.games[resp["gameId"]].initial_fen
            if i % 2 == 0:
                x_game_fen = new_game_fen
                self.assertEqual(x_game_fen, y_game_fen)
            else:
                y_game_fen = new_game_fen
                self.assertNotEqual(x_game_fen, y_game_fen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
