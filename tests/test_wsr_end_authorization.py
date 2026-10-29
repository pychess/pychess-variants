import json
from unittest.mock import AsyncMock, patch

import test_logger
from aiohttp import WSMsgType
from aiohttp.test_utils import AioHTTPTestCase
from bug.game_bug import GameBug
from bug.utils_bug import insert_game_to_db_bughouse
from const import ABANDON, ABORTED, FLAG, RATED, RESIGN, STARTED
from game import Game
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from user import User
from utils import insert_game_to_db
from variants import VARIANTS
from wsr import process_message

from server import make_app

test_logger.init_test_logger()


class RoundEndAuthorizationTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    async def new_game(self, *, bughouse=False, anonymous_player=False):
        state = get_app_state(self.app)
        players = [
            User(
                state,
                username=f"end-player-{seat}",
                anon=anonymous_player and seat == 0,
                perfs=new_default_perf_map(VARIANTS),
            )
            for seat in range(4 if bughouse else 2)
        ]
        for player in players:
            state.users[player.username] = player
        if bughouse:
            game = GameBug(state, id8(), "bughouse", "", *players, rated=RATED)
            self.addAsyncCleanup(game.gameClocks.cancel_stopwatches)
            await insert_game_to_db_bughouse(game, state)
        else:
            game = Game(state, id8(), "chess", "", *players, rated=RATED)
            self.addAsyncCleanup(game.stopwatch.cancel)
            await insert_game_to_db(game, state)
        state.games[game.id] = game
        # Keep abort eligible while also exercising an ongoing game.
        if bughouse:
            await game.play_move("e2e4", clocks=[60000, 60000], clocks_b=[60000, 60000])
            await game._persist_queue.join()
        else:
            await game.play_move("e2e4")
        return state, game, players

    async def test_spectators_cannot_end_games_or_trigger_game_end_side_effects(self):
        for bughouse in (False, True):
            for anonymous in (False, True):
                with self.subTest(bughouse=bughouse, anonymous=anonymous):
                    state, game, players = await self.new_game(bughouse=bughouse)
                    spectator = User(state, username="end-spectator", anon=anonymous)
                    game.spectators.add(spectator)
                    before = await state.db.game.find_one({"_id": game.id})
                    perfs_before = json.dumps([player.perfs for player in players], sort_keys=True)
                    ws = AsyncMock()
                    with (
                        patch.object(game, "game_ended", wraps=game.game_ended) as end,
                        patch("wsr.round_broadcast", new=AsyncMock()) as broadcast,
                        patch("bug.wsr_bug.round_broadcast", new=AsyncMock()) as bug_broadcast,
                    ):
                        for control in ("resign", "abandon", "abort", "flag"):
                            await process_message(
                                state, spectator, ws, {"type": control, "gameId": game.id}, game
                            )
                            self.assertEqual(game.status, STARTED)
                            self.assertEqual(game.result, "*")
                        end.assert_not_awaited()
                        broadcast.assert_not_awaited()
                        bug_broadcast.assert_not_awaited()
                    ws.send_str.assert_not_awaited()
                    self.assertEqual(await state.db.game.find_one({"_id": game.id}), before)
                    self.assertEqual(
                        json.dumps([player.perfs for player in players], sort_keys=True),
                        perfs_before,
                    )
                    if bughouse:
                        self.assertIsNone(game.resign_offer)

    async def test_cookie_free_spectator_socket_cannot_end_games(self):
        for bughouse in (False, True):
            with self.subTest(bughouse=bughouse):
                state, game, players = await self.new_game(bughouse=bughouse)
                if not bughouse:
                    # A White draw offer is the prerequisite for the published exploit.
                    game.draw_offers.add(players[0].username)
                before = await state.db.game.find_one({"_id": game.id})
                self.client.session.cookie_jar.clear()
                origin = str(self.client.make_url("/")).rstrip("/")
                async with self.client.ws_connect(
                    f"/wsr/{game.id}", headers={"Origin": origin}
                ) as ws:
                    while True:
                        message = await ws.receive_json(timeout=2)
                        if message["type"] == "game_user_connected":
                            spectator = state.users[message["username"]]
                            break
                    self.assertTrue(spectator.anon)
                    self.assertFalse(game.is_player(spectator))
                    self.assertIn(spectator, game.spectators)
                    for control in (
                        "resign",
                        "abandon",
                        "abort",
                        "flag",
                        "draw",
                        "reject_draw",
                        "moretime",
                    ):
                        await ws.send_json({"type": control, "gameId": game.id})
                    # The echoed ping is a barrier: all four control messages were processed.
                    await ws.send_str("/n")
                    while True:
                        response = await ws.receive(timeout=2)
                        self.assertEqual(response.type, WSMsgType.TEXT)
                        if response.data == "/n":
                            break
                        self.assertNotEqual(json.loads(response.data)["type"], "gameEnd")
                    self.assertEqual(game.status, STARTED)
                    self.assertEqual(game.result, "*")
                    if not bughouse:
                        self.assertEqual(game.draw_offers, {players[0].username})
                    self.assertEqual(await state.db.game.find_one({"_id": game.id}), before)

    async def test_each_player_can_still_end_their_game(self):
        for anonymous in (False, True):
            for seat in (0, 1):
                for control, status in (
                    ("resign", RESIGN),
                    ("abandon", ABANDON),
                    ("abort", ABORTED),
                ):
                    with self.subTest(anonymous=anonymous, seat=seat, control=control):
                        state, game, players = await self.new_game(anonymous_player=anonymous)
                        with patch.object(game, "save_game", new=AsyncMock()) as save:
                            await process_message(
                                state,
                                players[seat],
                                AsyncMock(),
                                {"type": control, "gameId": game.id},
                                game,
                            )
                        self.assertEqual(game.status, status)
                        expected = "*" if control == "abort" else ("0-1" if seat == 0 else "1-0")
                        self.assertEqual(game.result, expected)
                        save.assert_awaited_once()

    async def test_all_four_bughouse_players_can_still_end_their_game(self):
        for seat in range(4):
            for control, status in (
                ("resign", RESIGN),
                ("abandon", ABANDON),
                ("abort", ABORTED),
                ("flag", FLAG),
            ):
                with self.subTest(seat=seat, control=control):
                    state, game, players = await self.new_game(bughouse=True)
                    player = players[seat]
                    with patch.object(game, "save_game", new=AsyncMock()) as save:
                        await process_message(
                            state, player, AsyncMock(), {"type": control, "gameId": game.id}, game
                        )
                        if control == "resign":
                            self.assertEqual(game.status, STARTED)
                            partner = state.users[game.partner_of(player.username)]
                            await process_message(
                                state,
                                partner,
                                AsyncMock(),
                                {"type": control, "gameId": game.id},
                                game,
                            )
                    self.assertEqual(game.status, status)
                    expected = "*" if control == "abort" else ("0-1" if seat in (0, 3) else "1-0")
                    self.assertEqual(game.result, expected)
                    save.assert_awaited_once()

    async def test_spectator_cannot_accept_or_reject_draw_offer(self):
        state, game, players = await self.new_game()
        spectator = User(state, username="draw-spectator")
        game.draw_offers.add(players[0].username)
        ws = AsyncMock()
        before = await state.db.game.find_one({"_id": game.id})
        with patch("wsr.round_broadcast", new=AsyncMock()) as broadcast:
            await process_message(state, spectator, ws, {"type": "draw", "gameId": game.id}, game)
            await process_message(
                state, spectator, ws, {"type": "reject_draw", "gameId": game.id}, game
            )
            self.assertEqual(game.result, "*")
            self.assertEqual(game.status, STARTED)
            self.assertEqual(game.draw_offers, {players[0].username})
            self.assertEqual(await state.db.game.find_one({"_id": game.id}), before)
            broadcast.assert_not_awaited()
            ws.send_str.assert_not_awaited()

            # A real opponent can accept White's offer, but White cannot accept it.
            await process_message(state, players[0], ws, {"type": "draw", "gameId": game.id}, game)
            self.assertEqual(game.result, "*")
            await process_message(state, players[1], ws, {"type": "draw", "gameId": game.id}, game)
            self.assertEqual(game.result, "1/2-1/2")
            self.assertGreater(game.status, STARTED)

    async def test_only_opposing_player_can_reject_draw_offer(self):
        state, game, players = await self.new_game()
        game.draw_offers.add(players[0].username)
        with patch("wsr.round_broadcast", new=AsyncMock()) as broadcast:
            await process_message(state, players[0], AsyncMock(), {"type": "reject_draw"}, game)
            self.assertEqual(game.draw_offers, {players[0].username})
            await process_message(state, players[1], AsyncMock(), {"type": "reject_draw"}, game)
            self.assertFalse(game.draw_offers)
            broadcast.assert_awaited_once()
            self.assertEqual(game.result, "*")

    async def test_spectator_cannot_add_time_and_players_credit_only_opponent(self):
        state, game, players = await self.new_game()
        from const import CASUAL
        from wsr import MORE_TIME

        game.rated = CASUAL
        spectator = User(state, username="time-spectator")
        request = {"type": "moretime", "gameId": game.id}
        clocks_before = (game.clocks_w[-1], game.clocks_b[-1])
        await process_message(state, spectator, AsyncMock(), request, game)
        self.assertEqual((game.clocks_w[-1], game.clocks_b[-1]), clocks_before)

        await process_message(state, players[0], AsyncMock(), request, game)
        self.assertEqual(game.clocks_w[-1], clocks_before[0])
        self.assertEqual(game.clocks_b[-1], clocks_before[1] + MORE_TIME)
        await process_message(state, players[1], AsyncMock(), request, game)
        self.assertEqual(game.clocks_w[-1], clocks_before[0] + MORE_TIME)
        self.assertEqual(game.clocks_b[-1], clocks_before[1] + MORE_TIME)

    async def test_berserk_cannot_be_used_by_spectator_or_for_other_seat(self):
        state = get_app_state(self.app)
        players = [User(state, username=f"berserk-{n}") for n in (0, 1)]
        for player in players:
            state.users[player.username] = player
        game = Game(state, id8(), "chess", "", *players, rated=RATED, tournamentId=id8())
        self.addAsyncCleanup(game.stopwatch.cancel)
        await insert_game_to_db(game, state)
        state.games[game.id] = game
        spectator = User(state, username="berserk-spectator")
        with patch("wsr.round_broadcast", new=AsyncMock()) as broadcast:
            for actor, color in (
                (spectator, "white"),
                (players[1], "white"),
                (players[0], "black"),
            ):
                await process_message(
                    state,
                    actor,
                    AsyncMock(),
                    {"type": "berserk", "color": color, "gameId": game.id},
                    game,
                )
            self.assertFalse(game.wberserk)
            self.assertFalse(game.bberserk)
            broadcast.assert_not_awaited()

            await process_message(
                state,
                players[1],
                AsyncMock(),
                {"type": "berserk", "color": "black", "gameId": game.id},
                game,
            )
            self.assertFalse(game.wberserk)
            self.assertTrue(game.bberserk)
            broadcast.assert_awaited_once()
            doc = await state.db.game.find_one({"_id": game.id})
            self.assertTrue(doc["bb"])
            self.assertFalse(doc["wb"])

    async def test_draw_result_waits_for_move_lock_and_rechecks_status(self):
        import asyncio

        state, game, players = await self.new_game()
        game.draw_offers.add(players[0].username)
        await game.move_lock.acquire()
        task = asyncio.create_task(
            process_message(
                state, players[1], AsyncMock(), {"type": "draw", "gameId": game.id}, game
            )
        )
        try:
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertEqual(game.result, "*")
            # Model a concurrent game-ending move that won the lock first.
            game.status = RESIGN
            game.result = "1-0"
        finally:
            game.move_lock.release()
            await task
        self.assertEqual(game.result, "1-0")

    async def test_bughouse_draw_offer_requires_opposing_team_member(self):
        state, game, players = await self.new_game(bughouse=True)
        spectator = User(state, username="bugdraw-spectator")
        with patch("bug.wsr_bug.round_broadcast", new=AsyncMock()) as broadcast:
            await process_message(
                state, spectator, AsyncMock(), {"type": "draw", "gameId": game.id}, game
            )
            self.assertIsNone(game.draw_offer_team)
            broadcast.assert_not_awaited()

            await process_message(
                state, players[0], AsyncMock(), {"type": "draw", "gameId": game.id}, game
            )
            offering_team = game.team_of(players[0].username)
            self.assertIs(game.draw_offer_team, offering_team)
            partner = next(p for p in players if p.username in offering_team and p != players[0])
            await process_message(
                state, partner, AsyncMock(), {"type": "draw", "gameId": game.id}, game
            )
            await process_message(state, spectator, AsyncMock(), {"type": "reject_draw"}, game)
            self.assertIs(game.draw_offer_team, offering_team)
            self.assertEqual(game.result, "*")

            opponent = next(p for p in players if p.username not in offering_team)
            await process_message(
                state, opponent, AsyncMock(), {"type": "draw", "gameId": game.id}, game
            )
            self.assertEqual(game.result, "1/2-1/2")
            self.assertGreater(game.status, STARTED)

    async def test_other_participant_only_controls_reject_spectators(self):
        state, game, _players = await self.new_game()
        spectator = User(state, username="other-control-spectator")
        for control in ("ready", "rematch", "reject_rematch", "leave", "count"):
            with (
                self.subTest(control=control),
                patch("wsr.round_broadcast", new=AsyncMock()) as broadcast,
            ):
                await process_message(
                    state,
                    spectator,
                    AsyncMock(),
                    {"type": control, "gameId": game.id, "handicap": False, "mode": "start"},
                    game,
                )
                broadcast.assert_not_awaited()
        self.assertFalse(game.rematch_offers)

    async def test_payload_game_id_cannot_redirect_actions(self):
        state, game, players = await self.new_game()
        with patch("wsr.round_broadcast", new=AsyncMock()) as broadcast:
            await process_message(
                state,
                players[0],
                AsyncMock(),
                {"type": "draw", "gameId": "another-game"},
                game,
            )
            self.assertFalse(game.draw_offers)
            broadcast.assert_not_awaited()

    async def test_corr_board_refresh_cannot_claim_draw(self):
        from wsr import handle_board

        state = get_app_state(self.app)
        white = User(state, username="corr-draw-white")
        black = User(state, username="corr-draw-black")
        game = Game(state, id8(), "chess", "", white, black, corr=True)
        game.draw_offers.add(white.username)
        ws = AsyncMock()
        with patch("wsr.draw", new=AsyncMock()) as draw_claim:
            await handle_board(ws, black, game)
            draw_claim.assert_not_awaited()
        self.assertEqual(game.result, "*")
        self.assertEqual(game.draw_offers, {white.username})
        self.assertEqual(json.loads(ws.send_str.await_args.args[0])["type"], "draw_offer")

    async def test_spectator_cannot_post_in_player_chat_room(self):
        for bughouse in (False, True):
            with self.subTest(bughouse=bughouse):
                state, game, _players = await self.new_game(bughouse=bughouse)
                spectator = User(state, username="spoofed-player-chat")
                msg_type = "bugroundchat" if bughouse else "roundchat"
                room_msg = {
                    "type": msg_type,
                    "gameId": game.id,
                    "room": "player",
                    "message": "forged player-room message",
                }
                before = list(game.messages)
                broadcast_module = "bug.wsr_bug" if bughouse else "wsr"
                with patch(f"{broadcast_module}.round_broadcast", new=AsyncMock()) as broadcast:
                    await process_message(state, spectator, AsyncMock(), room_msg, game)
                    broadcast.assert_not_awaited()
                self.assertEqual(list(game.messages), before)
