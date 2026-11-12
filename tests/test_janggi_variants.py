from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import AioHTTPTestCase
from catalogued.builtin_data import (
    FSF_CATALOGUED_BUILTIN_VARIANTS,
    FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES,
)
from catalogued.documents import _build_fsf_builtin_doc, _client_doc
from catalogued.variants import register_catalogued_variant_doc
from const import CLAIM, DRAW, STARTED, VARIANTEND
from fairy.fairy_board import NOTATION_JANGGI, FairyBoard, sf
from game import Game
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import insert_game_to_db, load_game, should_send_game_start_to_bot
from variants import JANGGI_VARIANTS, unregister_catalogued_server_variant
from wsr import handle_setup

from server import make_app

NAMES = ("janggitraditional", "janggimodern", "janggicasual")
BIKJANG = {"janggi", "janggitraditional"}
POINTS = {"janggi", "janggimodern"}
POSITION = "9/4k4/9/p8/9/4P4/9/9/4K4/R8 w - - 0 1"
RED_SETUP = "rbna1abnr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RNBA1ABNR w - - 0 1"
BOTH_SETUP = "rbna1abnr/4k4/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/4K4/RBNA1ANBR w - - 0 1"


class JanggiRulesTestCase(unittest.TestCase):
    def test_native_metadata(self):
        for name in NAMES:
            with self.subTest(name=name):
                self.assertNotIn(name, FSF_CATALOGUED_BUILTIN_VARIANTS_CANDIDATES)
                doc = _build_fsf_builtin_doc(name, FSF_CATALOGUED_BUILTIN_VARIANTS[name])
                self.assertEqual(doc["baseVariant"], "janggi")
                self.assertEqual(doc["clientVariant"], "janggi")
                self.assertEqual(doc["boardFamilyOverride"], "janggi9x10")
                self.assertEqual(doc["pieceFamilyOverride"], "janggi")
                self.assertTrue(doc["legalMovesNeedHistory"])
                self.assertTrue(doc["rulesPass"])
                self.assertFalse(_client_doc(doc)["replayOnly"])
                self.assertEqual(doc["startFen"], sf.start_fen(name))

    def test_bikjang_requires_resolution_only_in_tournament_and_traditional(self):
        for name in JANGGI_VARIANTS:
            with self.subTest(name=name):
                board = FairyBoard(name, POSITION)
                self.assertEqual(board.notation, NOTATION_JANGGI)
                board.push("e5d5")
                self.assertIn("e9e9", board.legal_moves())
                self.assertEqual("a7a6" not in board.legal_moves(), name in BIKJANG)
                board.push("e9e9")
                self.assertEqual(board.is_immediate_game_end()[0], name in BIKJANG)
                board.pop()
                self.assertEqual("a7a6" not in board.legal_moves(), name in BIKJANG)
                board.push("e9d9")
                self.assertFalse(board.is_immediate_game_end()[0])

    def test_pass_in_check_requires_bikjang(self):
        for name in JANGGI_VARIANTS:
            with self.subTest(name=name):
                board = FairyBoard(name, POSITION.replace("4P4/9/9", "4P4/9/4r4"))
                self.assertTrue(board.is_checked())
                self.assertNotIn("e2e2", board.legal_moves())
                board = FairyBoard(name, POSITION.replace("4P4", "4N4"))
                board.push("e5d7")
                self.assertTrue(board.is_checked())
                self.assertEqual("e9e9" in board.legal_moves(), name in BIKJANG)

    def test_no_capture_limit_is_doubled_for_modern(self):
        for name in JANGGI_VARIANTS:
            for halfmoves in (99, 199):
                with self.subTest(name=name, halfmoves=halfmoves):
                    fen = sf.start_fen(name).replace(" 0 1", f" {halfmoves} 100")
                    ended, value = sf.is_optional_game_end(name, fen, ["e2d2"])
                    self.assertEqual(ended, name != "janggimodern" or halfmoves == 199)
                    if ended:
                        self.assertEqual(value == 0, name not in POINTS)


class JanggiGameTestCase(AioHTTPTestCase):
    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))

        async def register(app):
            state = get_app_state(app)
            for name in NAMES:
                register_catalogued_variant_doc(
                    state, _build_fsf_builtin_doc(name, FSF_CATALOGUED_BUILTIN_VARIANTS[name])
                )

        app.on_startup.append(register)
        return app

    async def tearDownAsync(self):
        await self.client.close()
        for name in NAMES:
            unregister_catalogued_server_variant(name)

    def new_game(self, name, fen="", corr=False):
        state = get_app_state(self.app)
        players = []
        for color in ("blue", "red"):
            username = "janggi-" + color
            player = (
                state.users[username] if username in state.users else User(state, username=username)
            )
            state.users[username] = player
            players.append(player)
        game = Game(state, id8(), name, fen, *players, base=5, corr=corr)
        state.games[game.id] = game
        return game

    async def test_bikjang_and_double_pass_results_survive_reload(self):
        state = get_app_state(self.app)
        for name in JANGGI_VARIANTS:
            for initial, prefix, tail in (
                (POSITION, ["a1a2", "a7a6"], ["e2e2", "e9e9"]),
                (POSITION, ["a1a2", "a7a6"], ["e5d5", "e9e9"]),
                (sf.start_fen(name), ["a4a5", "a7a6"], ["e2e2", "e9e9"]),
            ):
                with self.subTest(name=name, initial=initial, tail=tail):
                    game = self.new_game(name, initial)
                    await insert_game_to_db(game, state)
                    for move in prefix + tail:
                        self.assertIn(move, game.board.legal_moves())
                        await game.play_move(move)
                        if move == "e5d5":
                            # Facing-kings restrictions must survive an active-game reload.
                            state.games.pop(game.id)
                            game = await load_game(state, game.id)
                            self.assertIsNotNone(game)
                            state.games[game.id] = game
                            self.assertEqual(
                                "a6a5" not in game.board.legal_moves(), name in BIKJANG
                            )
                    ended = tail[0] == "e2e2" or name in BIKJANG
                    if ended:
                        self.assertEqual(game.status, VARIANTEND)
                        self.assertEqual(
                            game.result,
                            ("1-0" if initial == POSITION else "0-1")
                            if name in POINTS
                            else "1/2-1/2",
                        )
                    else:
                        self.assertEqual(game.result, "*")
                        await game.game_ended(game.wplayer, "resign")
                    state.games.pop(game.id)
                    restored = await load_game(state, game.id)
                    self.assertIsNotNone(restored)
                    self.assertEqual(restored.board.move_stack, game.board.move_stack)
                    self.assertEqual(restored.board.fen, game.board.fen)
                    self.assertEqual(restored.result, game.result)
                    self.assertEqual(restored.status, game.status)
                    self.assertEqual(restored.board.notation, NOTATION_JANGGI)

    async def test_move_limit_adjudication(self):
        for name in NAMES:
            for halfmoves in (99, 199):
                with self.subTest(name=name, halfmoves=halfmoves):
                    fen = sf.start_fen(name).replace(" 0 1", f" {halfmoves} 100")
                    game = self.new_game(name, fen)
                    await game.play_move("e2d2")
                    if name == "janggimodern" and halfmoves == 99:
                        self.assertEqual(game.result, "*")
                        await game.game_ended(game.wplayer, "resign")
                    elif name == "janggimodern":
                        self.assertEqual(game.result, "0-1")
                        self.assertEqual(game.status, CLAIM)
                    else:
                        self.assertEqual(game.result, "1/2-1/2")
                        self.assertEqual(game.status, DRAW)

    async def test_native_repetition_thresholds_and_adjudication(self):
        for name in NAMES:
            with self.subTest(name=name):
                game = self.new_game(name, sf.start_fen(name))
                moves = ["e2d2", "e9d9", "d2e2", "d9e9"] * (3 if name == "janggimodern" else 2)
                for i, move in enumerate(moves):
                    self.assertEqual(game.result, "*")
                    await game.play_move(move)
                    if i < len(moves) - 1:
                        self.assertEqual(game.result, "*")
                self.assertEqual(game.result, "0-1" if name == "janggimodern" else "1/2-1/2")
                self.assertEqual(game.status, CLAIM if name == "janggimodern" else DRAW)

    async def test_setup_clock_and_bot_setup(self):
        state = get_app_state(self.app)
        for name in NAMES:
            for waiting in ("black", "white"):
                with self.subTest(name=name, waiting=waiting):
                    game = self.new_game(name)
                    self.assertEqual(game.stopwatch.time_for_first_move, 45000)
                    game.bsetup = waiting == "black"
                    await game.game_ended(
                        game.wplayer if waiting == "black" else game.bplayer, "flag"
                    )
                    self.assertEqual(game.result, "1-0" if waiting == "black" else "0-1")
            with self.subTest(name=name, bot=True):
                human = state.users["janggi-blue"]
                bot = User(state, username="janggi-setup-bot", bot=True)
                game = Game(state, id8(), name, "", human, bot, base=5)
                self.assertFalse(game.bsetup)
                self.assertTrue(game.wsetup)
                self.assertFalse(should_send_game_start_to_bot(game))
                self.assertEqual(sf.validate_fen(game.board.fen, name), sf.FEN_OK)
                await game.game_ended(human, "resign")

    async def test_setup_order_bot_gate_reload_and_takeback(self):
        state = get_app_state(self.app)
        for name in NAMES:
            with self.subTest(name=name):
                game = self.new_game(name, corr=True)
                await insert_game_to_db(game, state)
                self.assertTrue(game.bsetup and game.wsetup)
                self.assertFalse(should_send_game_start_to_bot(game))

                async def setup(active_game, color, fen):
                    await handle_setup(
                        AsyncMock(),
                        state.users,
                        active_game.bplayer if color == "black" else active_game.wplayer,
                        {"type": "setup", "gameId": active_game.id, "color": color, "fen": fen},
                        active_game,
                    )

                with patch("wsr.ws_send_json", new=AsyncMock()):
                    await setup(game, "white", BOTH_SETUP)
                    self.assertEqual(game.board.fen, sf.start_fen(name))
                    await setup(game, "black", RED_SETUP)
                    self.assertFalse(game.bsetup)
                    self.assertTrue(game.wsetup)
                    state.games.pop(game.id)
                    game = await load_game(state, game.id)
                    self.assertIsNotNone(game)
                    state.games[game.id] = game
                    self.assertFalse(game.bsetup)
                    self.assertTrue(game.wsetup)
                    self.assertEqual(game.board.fen, RED_SETUP)
                    self.assertFalse(should_send_game_start_to_bot(game))
                    await setup(game, "white", BOTH_SETUP)
                self.assertFalse(game.bsetup or game.wsetup)
                self.assertTrue(should_send_game_start_to_bot(game))
                self.assertEqual(game.status, STARTED)
                await game.play_move("c1d3")
                await game.play_move("c10d8")
                state.games.pop(game.id)
                restored = await load_game(state, game.id)
                self.assertIsNotNone(restored)
                self.assertEqual(restored.board.initial_fen, BOTH_SETUP)
                self.assertEqual(restored.board.move_stack, ["c1d3", "c10d8"])
                restored.ensure_steps()
                await restored.takeback(restored.wplayer)
                self.assertEqual(restored.board.fen, BOTH_SETUP)
                self.assertEqual(restored.status, STARTED)
                await restored.game_ended(restored.wplayer, "resign")


if __name__ == "__main__":
    unittest.main()
