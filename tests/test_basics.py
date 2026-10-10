import unittest
from datetime import UTC, datetime
from operator import neg
from unittest.mock import AsyncMock, patch

import game
import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from bug.game_bug import GameBug
from const import CLAIM, CREATED, MATE, STALEMATE, reserved
from fairy import FairyBoard
from game import Game
from glicko2.glicko2 import LOSS, WIN, Glicko2, new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from sortedcollections import ValueSortedDict
from user import User
from utils import play_move, sanitize_fen
from variants import (
    VARIANTS,
    register_catalogued_server_variant,
    unregister_catalogued_server_variant,
)

from server import make_app

game.KEEP_TIME = 0
game.MAX_PLY = 120

test_logger.init_test_logger()

ZH960 = {
    "user0|NM": 1868,
    "user1|IM": 1861,
    "user2|GM": 1696,
    "user3|": 1685,
    "user4|": 1681,
    "user5|": 1668,
    "user6|": 1644,
    "user7|": 1642,  # peekitem(7)
    "user8|": 1642,
    "user9|": 1639,
}

PERFS = {
    "user7": new_default_perf_map(VARIANTS),
    "newplayer": new_default_perf_map(VARIANTS),
    "strongplayer": new_default_perf_map(VARIANTS),
    "weakplayer": new_default_perf_map(VARIANTS),
}
PERFS["user7"]["crazyhouse960"] = {
    "gl": {"r": 1642, "d": 125, "v": 0.06},
    "la": datetime.now(UTC),
    "nb": 100,
}

PERFS["newplayer"]["crazyhouse960"] = {
    "gl": {"r": 1500, "d": 136, "v": 0.06},
    "la": datetime.now(UTC),
    "nb": 100,
}

PERFS["strongplayer"]["crazyhouse960"] = {
    "gl": {"r": 1500, "d": 350, "v": 0.06},
    "la": datetime.now(UTC),
    "nb": 100,
}

PERFS["weakplayer"]["crazyhouse960"] = {
    "gl": {"r": 1450, "d": 350, "v": 0.06},
    "la": datetime.now(UTC),
    "nb": 100,
}

CLOCKS = [60, 60]


class GameResultTestCase(AioHTTPTestCase):
    async def startup(self, app):
        self.bplayer = User(get_app_state(self.app), username="bplayer", perfs=PERFS["newplayer"])
        self.wplayer = User(get_app_state(self.app), username="wplayer", perfs=PERFS["newplayer"])

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def test_bughouse_checkmate(self):
        FEN = "r1b2Q2/ppp4p/1kn5/1q3N2/8/2P5/P1PK1q~1P/1R6[Npp] w - - 0 33 | 1r1k3r/pPpn2pp/4Qn2/3p4/2pNP3/1Bb5/PPPP1PPP/R1B1K2R[RBBNPPPqrbbnppp] w KQ - 1 19"
        game = GameBug(
            get_app_state(self.app),
            "12345678",
            "bughouse",
            FEN,
            self.wplayer,
            self.wplayer,
            self.bplayer,
            self.bplayer,
            rated=False,
        )

        await game.play_move("d4c6", board="b", clocks=CLOCKS, clocks_b=CLOCKS)

        self.assertEqual(game.result, "0-1")
        self.assertEqual(game.status, MATE)

    async def test_atomic_stalemate(self):
        FEN = "K7/Rk6/2B5/8/8/8/7Q/8 w - - 0 1"
        game = Game(
            get_app_state(self.app),
            "12345678",
            "atomic",
            FEN,
            self.wplayer,
            self.bplayer,
            rated=False,
        )
        await game.play_move("h2b8", clocks=CLOCKS)

        self.assertEqual(game.result, "1/2-1/2")
        self.assertEqual(game.status, STALEMATE)

    async def test_atomic_checkmate(self):
        FEN = "B6Q/Rk6/8/8/8/8/8/4K3 w - - 0 1"
        game = Game(
            get_app_state(self.app),
            "12345678",
            "atomic",
            FEN,
            self.wplayer,
            self.bplayer,
            rated=False,
        )
        await game.play_move("h8b8", clocks=CLOCKS)

        self.assertEqual(game.result, "1-0")
        self.assertEqual(game.status, MATE)

    async def test_janggi_flag_results_during_and_after_setup(self):
        scenarios = (
            (True, True, self.bplayer, "1-0"),
            (True, False, self.wplayer, "0-1"),
            (False, False, self.wplayer, "0-1"),
            (False, False, self.bplayer, "1-0"),
        )
        for index, (wsetup, bsetup, loser, expected_result) in enumerate(scenarios):
            with self.subTest(wsetup=wsetup, bsetup=bsetup, loser=loser.username):
                game = Game(
                    get_app_state(self.app),
                    f"jgflag{index}",
                    "janggi",
                    "",
                    self.wplayer,
                    self.bplayer,
                )
                game.wsetup = wsetup
                game.bsetup = bsetup
                await game.game_ended(loser, "flag")
                self.assertEqual(expected_result, game.result)

    async def test_xiangqi_perpetual_check(self):
        FEN = "3k5/9/9/9/9/5p3/9/5p3/5K3/5C3 w - - 0 1"
        game = Game(get_app_state(self.app), "12345678", "xiangqi", FEN, self.wplayer, self.wplayer)

        for move in ("f2e2", "f3e3", "e2f2", "e3f3", "f2e2", "f3e3", "e2f2", "e3f3"):
            await game.play_move(move, clocks=CLOCKS)

        self.assertEqual(game.result, "1-0")
        self.assertEqual(game.status, CLAIM)

    async def test_late_move_on_finished_game_is_not_error(self):
        game = Game(get_app_state(self.app), "12345678", "chess", "", self.wplayer, self.bplayer)
        game.status = MATE

        with patch("utils.log.error") as mock_error:
            await play_move(
                get_app_state(self.app), self.wplayer, game, "e2e4", clocks=CLOCKS, ply=1
            )

        mock_error.assert_not_called()
        self.assertEqual(game.ply, 0)

    async def test_out_of_turn_move_is_ignored(self):
        game = Game(get_app_state(self.app), "12345678", "chess", "", self.wplayer, self.bplayer)

        await play_move(get_app_state(self.app), self.bplayer, game, "e7e5", clocks=CLOCKS, ply=1)

        self.assertEqual(game.ply, 0)
        self.assertEqual(game.status, CREATED)
        self.assertEqual(game.result, "*")

    async def test_missing_bot_queue_is_ignored(self):
        app_state = get_app_state(self.app)
        bot = app_state.users["Random-Mover"]
        game = Game(app_state, "bot-race", "chess", "", self.wplayer, bot, rated=False)

        bot.game_queues.pop(game.id, None)

        with patch.object(bot.event_queue, "put", new=AsyncMock()) as mock_event_put:
            await play_move(app_state, self.wplayer, game, "e2e4", clocks=CLOCKS, ply=1)

        self.assertEqual(game.ply, 1)
        self.assertEqual(game.lastmove, "e2e4")
        self.assertTrue(bot.game_queues.get(game.id) is None)
        mock_event_put.assert_not_called()

    @unittest.skip("TODO: is_optional_game_end() should be fixed for Jieqi")
    async def test_jieqi_perpetual_check(self):
        FEN = "3k5/9/9/9/9/5p3/9/5p3/5K3/5C3 w - - 0 1"
        game = Game(get_app_state(self.app), "12345678", "jieqi", FEN, self.wplayer, self.wplayer)

        for move in ("f2e2", "f3e3", "e2f2", "e3f3", "f2e2", "f3e3", "e2f2", "e3f3"):
            await game.play_move(move, clocks=CLOCKS)

        self.assertEqual(game.result, "1-0")
        self.assertEqual(game.status, CLAIM)


class SanitizeFenTestCase(unittest.TestCase):
    def test_reserved_ignores_none(self):
        self.assertFalse(reserved(None))

    def test_alice_stockfish_is_reserved(self):
        self.assertTrue(reserved("Alice-Stockfish"))
        self.assertTrue(reserved("alice-stockfish"))

    def test_start_fen_accepts_960_variant_keys(self):
        for variant_key in ("chess960", "atomic960", "seirawan960", "capablanca960"):
            fen = FairyBoard.start_fen(variant_key)
            self.assertIsInstance(fen, str)
            self.assertIn(" w ", fen)

    def test_fen_default(self):
        for variant in VARIANTS:
            chess960 = variant.endswith("960")
            variant_name = variant[:-3] if chess960 else variant
            board = FairyBoard(variant_name, chess960=chess960)
            fen = board.initial_fen
            valid, _sanitized = sanitize_fen(variant_name, fen, chess960)
            self.assertTrue(valid)

    def test_fen_lichess_zh_pockets(self):
        chess960 = False
        lichess_fen = "r7/5pkp/b1pPpNpn/p2pP3/N7/BP6/KP3PPP/r3q~3/RQNRPQBb w - - 2 51"
        pychess_fen = "r7/5pkp/b1pPpNpn/p2pP3/N7/BP6/KP3PPP/r3q~3[RQNRPQBb] w - - 2 51"
        _valid, sanitized = sanitize_fen("crazyhouse", lichess_fen, chess960)
        self.assertEqual(sanitized, pychess_fen)

    def test_fen_slashes(self):
        chess960 = False
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR/ w KQkq - 0 1"
        valid, _sanitized = sanitize_fen("chess", fen, chess960)
        self.assertFalse(valid)

    def test_fen_castling_rights(self):
        chess960 = False
        # missing h1 rook
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN1 w KQkq - 0 1"
        valid, _missing_rook_sanitized = sanitize_fen("chess", fen, chess960)
        self.assertFalse(valid)

        # https://www.pychess.org/xYbsTWKM
        fen = "rnbqk1nr/1ppp1ppp/1pb1p3/7e/1b2P3/2NP1N2/PPPQBPPP/R2EK2R[HH] w KQAEHkqabcdegh - 4 9"
        valid, _sanitized = sanitize_fen("shouse", fen, chess960)
        self.assertTrue(valid)

    def test_fen_allows_extra_pocket_material_within_engine_limits(self):
        start_fen = FairyBoard.start_fen("crazyhouse")
        fen = start_fen.replace("[]", "[%s]" % ("Q" * 14))
        valid, sanitized = sanitize_fen("crazyhouse", fen, False)
        self.assertTrue(valid)
        self.assertEqual(sanitized, fen)

    def test_fen_rejects_too_many_pieces_of_one_pocket_role(self):
        start_fen = FairyBoard.start_fen("crazyhouse")
        valid, sanitized = sanitize_fen(
            "crazyhouse", start_fen.replace("[]", "[%s]" % ("Q" * 15)), False
        )
        self.assertFalse(valid)
        self.assertEqual(sanitized, "")

    def test_fen_rejects_too_many_active_engine_features(self):
        start_fen = FairyBoard.start_fen("mansindam")
        extra_pieces = "".join(piece * 16 for piece in "NBRQAC")
        valid, sanitized = sanitize_fen(
            "mansindam", start_fen.replace("[]", "[%s]" % extra_pieces), False
        )
        self.assertFalse(valid)
        self.assertEqual(sanitized, "")

    def test_fen_rejects_more_pieces_in_one_hand_than_engine_allocates(self):
        start_fen = FairyBoard.start_fen("torishogi")
        two_swallows_on_board = start_fen.replace("sssssss/2s1S2/SSSSSSS", "7/2s1S2/7")

        fen = two_swallows_on_board.replace("[-]", "[%s]" % ("S" * 14))
        valid, sanitized = sanitize_fen("torishogi", fen, False)
        self.assertTrue(valid)
        self.assertEqual(sanitized, fen)

        valid, sanitized = sanitize_fen(
            "torishogi",
            two_swallows_on_board.replace("[-]", "[%s]" % ("S" * 15)),
            False,
        )
        self.assertFalse(valid)
        self.assertEqual(sanitized, "")

    def test_fen_rejects_input_near_http_request_line_limit(self):
        start_fen = FairyBoard.start_fen("crazyhouse")
        valid, sanitized = sanitize_fen(
            "crazyhouse", start_fen.replace("[]", "[%s]" % ("Q" * 4096)), False
        )
        self.assertFalse(valid)
        self.assertEqual(sanitized, "")

    def test_fen_opp_king_in_check(self):
        chess960 = False
        fen = "5k3/4a4/3CN4/9/1PP5p/9/8P/4C4/4A4/2B1K4 w - - 0 46"
        valid, _sanitized = sanitize_fen("janggi", fen, chess960)
        self.assertFalse(valid)


class RequestLobbyTestCase(AioHTTPTestCase):
    async def tearDownAsync(self):
        await self.client.close()

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        return app

    async def test_example(self):
        resp = await self.client.request("GET", "/")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertIn("<title>PyChess", text)

    async def test_analysis_960_route_normalizes_variant_and_chess960(self):
        resp = await self.client.request("GET", "/analysis/chess960")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertIn('data-variant="chess"', text)
        self.assertIn('data-chess960="True"', text)

    async def test_editor_960_route_normalizes_variant_and_chess960(self):
        resp = await self.client.request("GET", "/editor/chess960")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertIn('data-variant="chess"', text)
        self.assertIn('data-chess960="True"', text)

    async def test_editor_keeps_accessible_catalogued_variant(self):
        name = "editor-catalogued-test"
        app_state = get_app_state(self.app)
        app_state.catalogued_variants[name] = {
            "name": name,
            "displayName": "Editor catalogued test",
            "ini": f"[{name}:shogi]\nmaxFile = 10\nmaxRank = 10\n",
            "baseVariant": "shogi",
            "startFen": "10/10/10/10/10/10/10/10/10/10 w - - 0 1",
            "width": 10,
            "height": 10,
            "pieces": ["k", "p"],
            "kingRoles": ["k"],
            "promotionType": "shogi",
            "promotionRoles": ["p"],
            "promotionOrder": ["+"],
            "author": "",
            "visibility": "unlisted",
            "enabled": True,
            "archived": False,
        }
        register_catalogued_server_variant(name, "Editor catalogued test")
        self.addCleanup(unregister_catalogued_server_variant, name)

        fen = "10/10/10/10/10/10/10/10/10/10_w_-_-_0_1"
        resp = await self.client.request("GET", f"/editor/{name}?fen={fen}")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertIn(f'data-variant="{name}"', text)
        self.assertRegex(text, r'data-catalogued-variants="[^"]*editor-catalogued-test[^"]*"')

    async def test_rules_page_preloads_accessible_unlisted_catalogued_variant(self):
        name = "rules-unlisted-catalogued-test"
        app_state = get_app_state(self.app)
        app_state.catalogued_variants[name] = {
            "name": name,
            "displayName": "Rules unlisted catalogued test",
            "ini": f"[{name}:shogi]\nmaxFile = 10\nmaxRank = 10\n",
            "baseVariant": "shogi",
            "startFen": "10/10/10/10/10/10/10/10/10/10 w - - 0 1",
            "width": 10,
            "height": 10,
            "pieces": ["k", "p"],
            "kingRoles": ["k"],
            "promotionType": "shogi",
            "promotionRoles": ["p"],
            "promotionOrder": ["+"],
            "author": "author",
            "visibility": "unlisted",
            "enabled": True,
            "archived": False,
        }
        register_catalogued_server_variant(name, "Rules unlisted catalogued test")
        self.addCleanup(unregister_catalogued_server_variant, name)

        resp = await self.client.request("GET", f"/variants/{name}")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertRegex(text, rf'data-catalogued-variants="[^"]*{name}[^"]*"')

    async def test_games_unknown_variant_is_normalized(self):
        resp = await self.client.request("GET", "/games/notavariant")
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertIn('data-view="games"', text)
        self.assertIn('data-variant=""', text)

    async def test_forum_route_uses_cross_origin_resource_policy(self):
        resp = await self.client.request("GET", "/forum")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Cross-Origin-Resource-Policy"), "cross-origin")
        self.assertIsNone(resp.headers.get("Cross-Origin-Opener-Policy"))
        self.assertIsNone(resp.headers.get("Cross-Origin-Embedder-Policy"))


class HighscoreTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        app_state.highscore = {variant: ValueSortedDict(neg) for variant in VARIANTS}
        app_state.highscore["crazyhouse960"] = ValueSortedDict(neg, ZH960)

        self.wplayer = User(app_state, username="user7", perfs=PERFS["user7"])
        self.bplayer = User(app_state, username="newplayer", perfs=PERFS["newplayer"])
        self.strong_player = User(app_state, username="strongplayer", perfs=PERFS["strongplayer"])
        self.weak_player = User(app_state, username="weakplayer", perfs=PERFS["weakplayer"])

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def play_and_resign(self, game, player):
        clocks = (game.clocks_w[0], game.clocks_b[0])
        for i, move in enumerate(("e2e4", "e7e5", "f2f4"), start=1):
            await game.play_move(move, clocks=clocks, ply=i)
        await game.game_ended(player, "resign")

    async def test_highscore_updates_both_players_when_first_changes_top(self):
        game = Game(
            get_app_state(self.app),
            id8(),
            "crazyhouse",
            "",
            self.wplayer,
            self.bplayer,
            rated=True,
            chess960=True,
            create=True,
        )
        white_rating = self.wplayer.get_rating("crazyhouse", True)
        black_rating = self.bplayer.get_rating("crazyhouse", True)

        set_highscore = AsyncMock(side_effect=[True, False])
        refresh = AsyncMock()
        with (
            patch.object(game, "set_highscore", new=set_highscore),
            patch("game.refresh_lobby_leaderboard_cache", new=refresh),
        ):
            await game.apply_rating_update(white_rating, black_rating)

        self.assertEqual(set_highscore.await_count, 2)
        refresh.assert_awaited_once_with(game.app_state)

    async def test_lost_but_still_there(self):
        game_id = id8()
        game = Game(
            get_app_state(self.app),
            game_id,
            "crazyhouse",
            "",
            self.wplayer,
            self.bplayer,
            rated=True,
            chess960=True,
            create=True,
        )
        app_state = get_app_state(self.app)
        app_state.games[game.id] = game
        self.assertEqual(game.status, CREATED)
        self.assertEqual(len(game.crosstable["r"]), 0)

        highscore0 = game.app_state.highscore["crazyhouse960"].peekitem(7)

        # wplayer resign 0-1
        await self.play_and_resign(game, self.wplayer)

        highscore1 = game.app_state.highscore["crazyhouse960"].peekitem(7)

        self.assertEqual(len(game.crosstable["r"]), 1)
        self.assertNotEqual(highscore0, highscore1)
        self.assertTrue(self.wplayer.username + "|" in game.app_state.highscore["crazyhouse960"])

    async def test_lost_and_out(self):
        game_id = id8()
        game = Game(
            get_app_state(self.app),
            game_id,
            "crazyhouse",
            "",
            self.wplayer,
            self.strong_player,
            rated=True,
            chess960=True,
            create=True,
        )
        app_state = get_app_state(self.app)
        app_state.games[game.id] = game
        self.assertEqual(game.status, CREATED, msg="status not equal to CREATED")
        self.assertEqual(len(game.crosstable["r"]), 0, msg="game.crosstable not empty")

        highscore0 = game.app_state.highscore["crazyhouse960"].peekitem(7)

        # wplayer resign 0-1
        await self.play_and_resign(game, self.wplayer)

        highscore1 = game.app_state.highscore["crazyhouse960"].peekitem(7)

        self.assertEqual(len(game.crosstable["r"]), 1, msg="game.crosstable still empty")
        self.assertNotEqual(highscore0, highscore1, msg="highscore not changed")
        self.assertTrue(
            self.wplayer.username + "|"
            not in game.app_state.highscore["crazyhouse960"].keys()[:10],
            msg="wplayer not in highscore",
        )

    async def test_win_and_in_then_lost_and_out(self):
        game_id = id8()
        game = Game(
            get_app_state(self.app),
            game_id,
            "crazyhouse",
            "",
            self.strong_player,
            self.weak_player,
            rated=True,
            chess960=True,
            create=True,
        )
        app_state = get_app_state(self.app)
        app_state.games[game.id] = game
        self.assertEqual(game.status, CREATED)
        self.assertEqual(len(game.crosstable["r"]), 0)

        # weak_player resign 1-0
        await self.play_and_resign(game, self.weak_player)

        self.assertEqual(len(game.crosstable["r"]), 1)
        self.assertTrue(
            self.weak_player.username + "|"
            not in game.app_state.highscore["crazyhouse960"].keys()[:10]
        )
        self.assertTrue(
            self.strong_player.username + "|"
            in game.app_state.highscore["crazyhouse960"].keys()[:10]
        )

        # now strong player will lose to weak_player and should be out from leaderboard
        game_id = id8()
        game = Game(
            get_app_state(self.app),
            game_id,
            "crazyhouse",
            "",
            self.strong_player,
            self.weak_player,
            rated=True,
            chess960=True,
            create=True,
        )
        app_state.games[game.id] = game

        doc = await game.app_state.db.crosstable.find_one({"_id": game.ct_id})
        if doc is not None:
            game.crosstable = doc

        # strong_player resign 0-1
        await self.play_and_resign(game, self.strong_player)

        self.assertEqual(len(game.crosstable["r"]), 2)
        self.assertTrue(
            self.weak_player.username + "|"
            not in game.app_state.highscore["crazyhouse960"].keys()[:10]
        )
        self.assertTrue(
            self.strong_player.username + "|"
            not in game.app_state.highscore["crazyhouse960"].keys()[:10]
        )


class RatingTestCase(AioHTTPTestCase):
    async def startup(self, app):
        self.gl2 = Glicko2(tau=0.5)

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def test_new_rating(self):
        # New User ratings are equals to default

        default_rating = self.gl2.create_rating()

        user = User(
            get_app_state(self.app),
            username="testuser",
            perfs=new_default_perf_map(VARIANTS),
        )
        result = user.get_rating("chess", False)

        self.assertEqual(result.mu, default_rating.mu)

    async def test_rating(self):
        # New Glicko2 rating calculation example from original paper

        u1 = User(
            get_app_state(self.app),
            username="testuser1",
            perfs={
                "chess": {
                    "la": datetime.now(UTC),
                    "gl": {"r": 1500, "d": 200, "v": 0.06},
                }
            },
        )
        r1 = u1.get_rating("chess", False)

        self.assertEqual(r1.mu, 1500)
        self.assertEqual(r1.phi, 200)
        self.assertEqual(r1.sigma, 0.06)

        u2 = User(
            get_app_state(self.app),
            username="testuser2",
            perfs={
                "chess": {
                    "la": datetime.now(UTC),
                    "gl": {"r": 1400, "d": 30, "v": 0.06},
                }
            },
        )
        r2 = u2.get_rating("chess", False)
        self.assertEqual(r2.mu, 1400)

        u3 = User(
            get_app_state(self.app),
            username="testuser3",
            perfs={
                "chess": {
                    "la": datetime.now(UTC),
                    "gl": {"r": 1550, "d": 100, "v": 0.06},
                }
            },
        )
        r3 = u3.get_rating("chess", False)
        self.assertEqual(r3.mu, 1550)

        u4 = User(
            get_app_state(self.app),
            username="testuser4",
            perfs={
                "chess": {
                    "la": datetime.now(UTC),
                    "gl": {"r": 1700, "d": 300, "v": 0.06},
                }
            },
        )
        r4 = u4.get_rating("chess", False)
        self.assertEqual(r4.mu, 1700)

        new_rating = self.gl2.rate(r1, [(WIN, r2), (LOSS, r3), (LOSS, r4)])

        self.assertEqual(round(new_rating.mu, 3), 1464.051)
        self.assertEqual(round(new_rating.phi, 3), 151.517)
        self.assertEqual(round(new_rating.sigma, 6), 0.059996)

        await u1.set_rating("chess", False, new_rating)

        r1 = u1.get_rating("chess", False)

        self.assertEqual(round(r1.mu, 3), 1464.051)
        self.assertEqual(round(r1.phi, 3), 151.517)
        self.assertEqual(round(r1.sigma, 6), 0.059996)


class FirstRatedGameTestCase(AioHTTPTestCase):
    async def startup(self, app):
        self.bplayer1 = User(get_app_state(self.app), username="bplayer", perfs=PERFS["newplayer"])
        self.wplayer1 = User(get_app_state(self.app), username="wplayer", perfs=PERFS["newplayer"])

        self.bplayer2 = User(get_app_state(self.app), username="bplayer", perfs=PERFS["newplayer"])
        self.wplayer2 = User(get_app_state(self.app), username="wplayer", perfs=PERFS["newplayer"])

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def test_ratings(self):
        game = Game(
            get_app_state(self.app),
            "12345678",
            "chess",
            "",
            self.wplayer1,
            self.bplayer1,
            rated=True,
        )
        game.board.ply = 3
        await game.game_ended(self.bplayer1, "flag")

        rw = self.wplayer1.get_rating("chess", False)
        rb = self.bplayer1.get_rating("chess", False)

        self.assertEqual(round(rw.mu, 3), 1662.212)
        self.assertEqual(round(rb.mu, 3), 1337.788)

        game = Game(
            get_app_state(self.app),
            "12345678",
            "chess",
            "",
            self.wplayer2,
            self.bplayer2,
            rated=True,
        )
        game.board.ply = 3
        await game.game_ended(self.wplayer2, "flag")

        rw = self.wplayer2.get_rating("chess", False)
        rb = self.bplayer2.get_rating("chess", False)

        self.assertEqual(round(rb.mu, 3), 1662.212)
        self.assertEqual(round(rw.mu, 3), 1337.788)


if __name__ == "__main__":
    unittest.main(verbosity=2)
