import json
import unittest
from typing import cast
from unittest.mock import AsyncMock, patch

import test_logger
from catalogued_variants import (
    FSF_CATALOGUED_BUILTIN_VARIANTS,
    _build_fsf_builtin_doc,
    register_catalogued_variant_doc,
)
from game import Game
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from user import User
from utils import MAX_CUSTOM_FEN_LENGTH, sanitize_fen
from variants import unregister_catalogued_server_variant
from wsr import handle_rematch

from server import init_state, make_app

test_logger.init_test_logger()


class RematchTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = make_app(db_client=cast(AsyncMongoClient, AsyncMongoMockClient(tz_aware=True)))
        await init_state(self.app)
        self.state = get_app_state(self.app)
        self.player = User(self.state, username="rematch-player")
        self.opponent = User(self.state, username="rematch-opponent")
        for user in (self.player, self.opponent):
            self.state.users[user.username] = user
        self.bot = self.state.users["Fairy-Stockfish"]
        self.bot.online = True
        self.bot_start = self.enterContext(
            patch("wsr.send_bot_game_start_unless_streaming", new_callable=AsyncMock)
        )

    async def asyncTearDown(self):
        await self.state.server_shutdown()

    def register_kingless_variants(self):
        register_catalogued_variant_doc(
            self.state, _build_fsf_builtin_doc("joust", FSF_CATALOGUED_BUILTIN_VARIANTS["joust"])
        )
        register_catalogued_variant_doc(
            self.state,
            {
                "name": "rematch_way",
                "ini": """[rematch_way]
maxRank = 8
maxFile = 8
startFen = 8/8/8/8/8/8/8/8[PPPPPPPPpppppppp] w - - 0 1
pieceDrops = true
doubleStep = false
castling = false
immobilityIllegal = false
connectN = 5
connectPieceTypes = p
customPiece1 = p:mKmDmA
""",
                "startFen": "8/8/8/8/8/8/8/8[PPPPPPPPpppppppp] w - - 0 1",
                "enabled": True,
                "visibility": "public",
            },
        )
        self.addCleanup(unregister_catalogued_server_variant, "rematch_way")

    async def finished_game(self, variant, opponent):
        current = Game(self.state, id8(), variant, "", self.player, opponent)
        self.state.games[current.id] = current
        await current.game_ended(self.player, "resign")
        if not opponent.bot:
            current.rematch_offers.add(opponent.username)
        return current

    async def rematch(self, current, ws):
        return await handle_rematch(
            self.state,
            ws,
            self.player,
            {"type": "rematch", "gameId": current.id, "handicap": False},
            current,
        )

    async def test_kingless_community_rematches_preserve_saved_start(self):
        self.register_kingless_variants()
        oversized_pocket = "8/8/8/8/8/8/8/8[" + "P" * 17 + "] w - - 0 1"
        self.assertFalse(sanitize_fen("rematch_way", oversized_pocket, False)[0])
        for variant in ("joust", "rematch_way"):
            for opponent in (self.bot, self.opponent):
                with self.subTest(variant=variant, bot=opponent.bot):
                    current = await self.finished_game(variant, opponent)
                    self.assertTrue(current.initial_fen)
                    response = await self.rematch(current, AsyncMock())
                    self.assertEqual(response["type"], "new_game")
                    rematch = self.state.games[response["gameId"]]
                    self.assertEqual(rematch.initial_fen, current.initial_fen)
                    self.assertEqual(current.rematch_id, rematch.id)
                    self.assertIs(rematch.wplayer, opponent)
                    self.assertIs(rematch.bplayer, self.player)
                    await rematch.game_ended(self.player, "resign")
        self.assertEqual(self.bot_start.await_count, 2)

    async def test_failed_rematches_clean_up_and_can_be_retried(self):
        for opponent in (self.bot, self.opponent):
            with self.subTest(bot=opponent.bot):
                current = await self.finished_game("chess", opponent)
                existing_games = set(self.state.games)
                existing_seeks = set(self.state.seeks)
                existing_queues = set(self.bot.game_queues)
                opponent.blocked.add(self.player.username)
                ws = AsyncMock()
                with patch("wsr.round_broadcast", new_callable=AsyncMock) as broadcast:
                    for _ in range(2):
                        response = await self.rematch(current, ws)
                        self.assertEqual(response["type"], "error")
                        self.assertEqual(response["message"], "You cannot accept this seek.")
                        self.assertEqual(json.loads(ws.send_str.await_args.args[0]), response)
                        self.assertIsNone(current.rematch_id)
                        self.assertEqual(set(self.state.games), existing_games)
                        self.assertEqual(set(self.state.seeks), existing_seeks)
                        self.assertEqual(set(self.bot.game_queues), existing_queues)
                    broadcast.assert_not_awaited()
                opponent.blocked.remove(self.player.username)
                response = await self.rematch(current, ws)
                self.assertEqual(response["type"], "new_game")
                self.assertEqual(current.rematch_id, response["gameId"])
                await self.state.games[response["gameId"]].game_ended(self.player, "resign")

    async def test_community_fen_validation_still_rejects_invalid_input(self):
        register_catalogued_variant_doc(
            self.state, _build_fsf_builtin_doc("joust", FSF_CATALOGUED_BUILTIN_VARIANTS["joust"])
        )
        for fen in (
            "not a FEN",
            "8/8/8/4n3/3N4/8/8/8 x - - 0 1",
            "8" * (MAX_CUSTOM_FEN_LENGTH + 1),
        ):
            with self.subTest(fen=fen[:50]):
                self.assertFalse(sanitize_fen("joust", fen, False)[0])
