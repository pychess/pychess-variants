from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from clock import CorrClock
from const import CASUAL, FLAG, STARTED, T_FINISHED
from game import Game
from glicko2.glicko2 import new_default_perf_map
from newid import id8
from pychess_global_app_state_utils import get_app_state
from tournament.arena import ArenaTournament
from tournament.auto_play_tournament import ArenaTestTournament
from tournament.tournament import upsert_tournament_to_db
from tournament_test_base import TournamentTestCase
from user import User
from utils import insert_game_to_db, load_game_from_doc
from utils import play_move as server_play_move
from variants import VARIANTS
from wsr import _flag_claim_allowed, handle_berserk


def make_test_perfs():
    return new_default_perf_map(VARIANTS)


class TournamentRestartSafetyTestCase(TournamentTestCase):
    def add_user(self, username: str) -> User:
        app_state = get_app_state(self.app)
        user = User(app_state, username=username, perfs=make_test_perfs())
        app_state.users[username] = user
        return user

    async def new_tournament_game(
        self,
        *,
        base: float = 1,
        inc: int = 0,
        byoyomi_period: int = 0,
    ) -> Game:
        app_state = get_app_state(self.app)
        white = self.add_user(f"rw-{id8()}")
        black = self.add_user(f"rb-{id8()}")
        game = Game(
            app_state,
            id8(),
            "chess",
            "",
            white,
            black,
            base=base,
            inc=inc,
            byoyomi_period=byoyomi_period,
            rated=CASUAL,
            tournamentId=id8(),
        )
        await insert_game_to_db(game, app_state)
        return game

    async def test_move_without_cached_tournament_still_broadcasts_to_tv(self):
        app_state = get_app_state(self.app)
        game = await self.new_tournament_game()
        app_state.games[game.id] = game
        app_state.tv = game.id

        with (
            patch.object(game.wplayer, "send_game_message", new_callable=AsyncMock) as white_send,
            patch.object(game.bplayer, "send_game_message", new_callable=AsyncMock) as black_send,
            patch("utils.round_broadcast", new_callable=AsyncMock) as round_send,
            patch.object(app_state.lobby, "lobby_broadcast", new_callable=AsyncMock) as tv_send,
        ):
            await server_play_move(
                app_state, game.wplayer, game, "e2e4", clocks=[59_000, 60_000], ply=1
            )

        self.assertEqual(game.ply, 1)
        self.assertEqual(game.status, STARTED)
        white_send.assert_awaited_once()
        black_send.assert_awaited_once()
        round_send.assert_awaited_once()
        tv_send.assert_any_await(round_send.await_args.args[1])
        doc = await app_state.db.game.find_one({"_id": game.id})
        assert doc is not None
        self.assertEqual(len(doc["m"]), 1)

    async def test_game_end_without_cached_tournament_saves_result_without_errors(self):
        app_state = get_app_state(self.app)
        game = await self.new_tournament_game()
        app_state.games[game.id] = game

        with self.assertNoLogs("game", level="ERROR"):
            await game.game_ended(game.wplayer, "resign")

        doc = await app_state.db.game.find_one({"_id": game.id})
        assert doc is not None
        self.assertEqual(game.result, "0-1")
        self.assertEqual(doc["s"], game.status)
        self.assertEqual(doc["fx"], 2)

    async def test_late_arena_result_does_not_change_finished_standings(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTournament(
            app_state,
            tid,
            variant="chess",
            rated=False,
            before_start=0,
            minutes=10,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        white = self.add_user(f"late-white-{id8()}")
        black = self.add_user(f"late-black-{id8()}")
        await self.tournament.join(white)
        await self.tournament.join(black)
        await self.tournament.start(datetime.now(UTC))
        _, games = await self.tournament.create_new_pairings([white, black])
        game = games[0]
        await self.tournament.finish()
        self.assertEqual(self.tournament.status, T_FINISHED)
        standings = list(self.tournament.leaderboard.items())
        tournament_doc = await app_state.db.tournament.find_one({"_id": tid})
        player_docs = await app_state.db.tournament_player.find({"tid": tid}).to_list(None)

        with self.assertNoLogs("game", level="ERROR"):
            await server_play_move(
                app_state, game.wplayer, game, "e2e4", clocks=[59_000, 60_000], ply=1
            )
            await game.game_ended(game.bplayer, "resign")

        self.assertEqual(list(self.tournament.leaderboard.items()), standings)
        self.assertEqual(await app_state.db.tournament.find_one({"_id": tid}), tournament_doc)
        self.assertEqual(
            await app_state.db.tournament_player.find({"tid": tid}).to_list(None), player_docs
        )
        self.assertEqual(self.tournament.nb_games_finished, 0)
        self.assertTrue(all(not player.points for player in self.tournament.players.values()))

    async def test_non_tournament_casual_games_keep_takeback_clock_policy(self):
        app_state = get_app_state(self.app)
        white = self.add_user(f"cw-{id8()}")
        black = self.add_user(f"cb-{id8()}")
        game = Game(
            app_state,
            id8(),
            "chess",
            "",
            white,
            black,
            base=1,
            inc=0,
            rated=CASUAL,
        )
        await insert_game_to_db(game, app_state)

        initial_doc = await app_state.db.game.find_one({"_id": game.id})
        assert initial_doc is not None
        self.assertNotIn("cw", initial_doc)
        self.assertNotIn("cb", initial_doc)

        await game.play_move("e2e4", clocks=[59_000, 60_000], ply=1)
        after_move = await app_state.db.game.find_one({"_id": game.id})
        assert after_move is not None
        self.assertNotIn("cw", after_move)
        self.assertNotIn("cb", after_move)
        await game.stopwatch.cancel()

    async def test_casual_tournament_clocks_persist_each_move_and_restore_downtime(self):
        app_state = get_app_state(self.app)
        game = await self.new_tournament_game()

        initial_doc = await app_state.db.game.find_one({"_id": game.id})
        assert initial_doc is not None
        self.assertEqual(initial_doc["cw"], [])
        self.assertEqual(initial_doc["cb"], [])

        await game.play_move("e2e4", clocks=[5_000, 60_000], ply=1)
        after_white = await app_state.db.game.find_one({"_id": game.id})
        assert after_white is not None
        self.assertEqual(after_white["cw"], [5_000])
        self.assertEqual(after_white["cb"], [])

        await game.play_move("e7e5", clocks=[5_000, 58_000], ply=2)
        after_black = await app_state.db.game.find_one({"_id": game.id})
        assert after_black is not None
        self.assertEqual(after_black["cw"], [5_000])
        self.assertEqual(after_black["cb"], [58_000])

        # Simulate a process being unavailable for ten seconds after Black's
        # move. White had only five seconds left, so the restored authoritative
        # clock must already be expired.
        ten_seconds_ago = datetime.now(UTC) - timedelta(seconds=10)
        await app_state.db.game.update_one(
            {"_id": game.id},
            {"$set": {"l": ten_seconds_ago}},
        )
        await game.stopwatch.cancel()
        app_state.games.pop(game.id, None)

        persisted = await app_state.db.game.find_one({"_id": game.id})
        assert persisted is not None
        reloaded = await load_game_from_doc(app_state, persisted)
        self.assertIsInstance(reloaded, Game)
        assert isinstance(reloaded, Game)

        self.assertEqual(reloaded.stopwatch.ply, 2)
        self.assertEqual(reloaded.stopwatch.color, reloaded.board.color)
        self.assertLessEqual(reloaded.stopwatch.secs, 0)
        self.assertGreaterEqual(reloaded.elapsed_on_current_turn_ms(), 9_000)
        self.assertEqual(reloaded.get_board(full=True)["clocks"][reloaded.board.color], 0)
        self.assertTrue(_flag_claim_allowed(reloaded, reloaded.wplayer))

        # Clock.countdown() wakes once per second. A move arriving immediately
        # after reconnect must not slip through that tiny window when the
        # restart downtime itself already exhausted the clock.
        game_ended = AsyncMock(return_value={})
        play_move = AsyncMock()
        with (
            patch.object(reloaded, "game_ended", game_ended),
            patch.object(reloaded, "play_move", play_move),
        ):
            await server_play_move(
                app_state,
                reloaded.wplayer,
                reloaded,
                "g1f3",
                clocks=[0, reloaded.clocks_b[-1]],
                ply=3,
            )
        game_ended.assert_awaited_once_with(reloaded.wplayer, "flag")
        play_move.assert_not_awaited()

    async def test_correspondence_first_move_clock_counts_restart_downtime(self):
        app_state = get_app_state(self.app)
        white = self.add_user(f"corr-w-{id8()}")
        black = self.add_user(f"corr-b-{id8()}")

        # Suppress the background countdown so the test can inspect the exact
        # restored value before the expired game is automatically aborted.
        with patch.object(CorrClock, "countdown", new=AsyncMock()):
            game = Game(
                app_state,
                id8(),
                "chess",
                "",
                white,
                black,
                base=1,
                inc=0,
                rated=CASUAL,
                corr=True,
            )
            await insert_game_to_db(game, app_state)
            await game.stopwatch.cancel()

            # No move has been played, so there is no last-move timestamp. The
            # first correspondence turn started at the durable creation time.
            await app_state.db.game.update_one(
                {"_id": game.id},
                {"$set": {"d": datetime.now(UTC) - timedelta(days=2)}},
            )
            persisted = await app_state.db.game.find_one({"_id": game.id})
            assert persisted is not None

            reloaded = await load_game_from_doc(app_state, persisted)
            self.assertIsInstance(reloaded, Game)
            assert isinstance(reloaded, Game)
            self.assertIsInstance(reloaded.stopwatch, CorrClock)
            assert isinstance(reloaded.stopwatch, CorrClock)

            # A one-day game that was untouched for two days must remain
            # expired. Restart must not reset it to one day or grant the old
            # five-minute restart grace period.
            self.assertLessEqual(reloaded.stopwatch.mins, 0)

            game_ended = AsyncMock(return_value={})
            play_move = AsyncMock()
            with (
                patch.object(reloaded, "game_ended", game_ended),
                patch.object(reloaded, "play_move", play_move),
            ):
                await server_play_move(
                    app_state,
                    reloaded.wplayer,
                    reloaded,
                    "e2e4",
                    clocks=None,
                    ply=1,
                )

            # An ordinary correspondence game timing out before its first move
            # is aborted, matching CorrClock.countdown().
            game_ended.assert_awaited_once_with(reloaded.wplayer, "abort")
            play_move.assert_not_awaited()

    async def test_correspondence_expired_turn_gets_no_restart_grace(self):
        app_state = get_app_state(self.app)
        white = self.add_user(f"corr-w-{id8()}")
        black = self.add_user(f"corr-b-{id8()}")

        with patch.object(CorrClock, "countdown", new=AsyncMock()):
            game = Game(
                app_state,
                id8(),
                "chess",
                "",
                white,
                black,
                base=1,
                inc=0,
                rated=CASUAL,
                corr=True,
            )
            game.board.ply = 1
            game.last_move_time = datetime.now(UTC) - timedelta(days=2)
            assert isinstance(game.stopwatch, CorrClock)

            game.stopwatch.restart(from_db=True)

            # The old restart path replaced an expired correspondence clock
            # with five fresh minutes. Preserve the actual expired value so the
            # normal timeout path can finish the game immediately.
            self.assertLessEqual(game.stopwatch.mins, 0)
            await game.stopwatch.cancel()

    async def test_tournament_first_move_timeout_counts_server_downtime(self):
        app_state = get_app_state(self.app)
        game = await self.new_tournament_game()
        await game.stopwatch.cancel()

        # Tournament first-move clocks are finite. Make the persisted creation
        # time old enough that the timeout certainly elapsed while offline.
        await app_state.db.game.update_one(
            {"_id": game.id},
            {"$set": {"d": datetime.now(UTC) - timedelta(minutes=2)}},
        )
        persisted = await app_state.db.game.find_one({"_id": game.id})
        assert persisted is not None
        app_state.games.pop(game.id, None)

        reloaded = await load_game_from_doc(app_state, persisted)
        self.assertIsInstance(reloaded, Game)
        assert isinstance(reloaded, Game)
        self.assertEqual(reloaded.stopwatch.ply, 0)
        self.assertLessEqual(reloaded.stopwatch.secs, 0)
        # Once restored with an already-expired clock, countdown() may finish
        # the game before this coroutine gets to inspect ``running``. Both
        # states prove that server downtime was charged to the first move.
        self.assertTrue(reloaded.stopwatch.running or reloaded.status > STARTED)

    async def test_makruk_manual_count_state_survives_restart(self):
        app_state = get_app_state(self.app)
        white = self.add_user(f"makruk-w-{id8()}")
        black = self.add_user(f"makruk-b-{id8()}")
        game = Game(
            app_state,
            id8(),
            "makruk",
            "",
            white,
            black,
            base=1,
            inc=0,
            rated=CASUAL,
            tournamentId=id8(),
        )
        await insert_game_to_db(game, app_state)

        game.start_manual_count()
        await game.save_manual_count_state()
        first_doc = await app_state.db.game.find_one({"_id": game.id})
        assert first_doc is not None
        self.assertEqual(first_doc["mc"], 1)
        self.assertEqual(first_doc["mct"], [])

        await game.stopwatch.cancel()
        app_state.games.pop(game.id, None)
        reloaded = await load_game_from_doc(app_state, first_doc)
        self.assertIsInstance(reloaded, Game)
        assert isinstance(reloaded, Game)
        self.assertEqual(reloaded.board.count_started, 1)
        self.assertIn(reloaded.wplayer.username, reloaded.draw_offers)
        self.assertEqual(reloaded.manual_count_toggled, [])

        # Stop one count interval, persist it, then start another one. After a
        # second restart the closed interval must remain in the live history
        # while the new active interval is restored separately.
        reloaded.stop_manual_count()
        await reloaded.save_manual_count_state()
        reloaded.start_manual_count()
        await reloaded.save_manual_count_state()
        second_doc = await app_state.db.game.find_one({"_id": game.id})
        assert second_doc is not None
        self.assertEqual(second_doc["mc"], 1)
        self.assertEqual(second_doc["mct"], [[1, 1]])

        await reloaded.stopwatch.cancel()
        app_state.games.pop(game.id, None)
        reloaded_again = await load_game_from_doc(app_state, second_doc)
        self.assertIsInstance(reloaded_again, Game)
        assert isinstance(reloaded_again, Game)
        self.assertEqual(reloaded_again.board.count_started, 1)
        self.assertEqual(reloaded_again.manual_count_toggled, [(1, 1)])
        self.assertEqual(reloaded_again.mct, [(1, 1), (1, 1)])

        reloaded_again.stop_manual_count()
        await reloaded_again.save_manual_count_state()
        final_doc = await app_state.db.game.find_one({"_id": game.id})
        assert final_doc is not None
        self.assertEqual(final_doc["mc"], -1)
        self.assertEqual(final_doc["mct"], [[1, 1], [1, 1]])
        await reloaded_again.stopwatch.cancel()

    async def test_berserk_is_persisted_before_broadcast(self):
        app_state = get_app_state(self.app)
        game = await self.new_tournament_game()
        order: list[str] = []
        original_save_berserk = game.save_berserk

        async def save_berserk() -> None:
            order.append("persist")
            await original_save_berserk()

        async def broadcast(*args, **kwargs) -> None:
            order.append("broadcast")

        with (
            patch.object(game, "save_berserk", side_effect=save_berserk),
            patch("wsr.round_broadcast", side_effect=broadcast),
        ):
            await handle_berserk({"type": "berserk", "color": "white"}, game)

        self.assertEqual(order, ["persist", "broadcast"])
        doc = await app_state.db.game.find_one({"_id": game.id})
        assert doc is not None
        self.assertTrue(doc["wb"])
        await game.stopwatch.cancel()

    async def test_berserk_loses_cleanly_if_first_move_won_the_lock(self):
        app_state = get_app_state(self.app)
        game = await self.new_tournament_game()
        game.status = STARTED
        broadcast = AsyncMock()

        with patch("wsr.round_broadcast", broadcast):
            await handle_berserk({"type": "berserk", "color": "white"}, game)

        self.assertFalse(game.wberserk)
        doc = await app_state.db.game.find_one({"_id": game.id})
        assert doc is not None
        self.assertFalse(doc.get("wb", False))
        broadcast.assert_not_awaited()
        await game.stopwatch.cancel()

    async def test_no_show_pause_is_durable_before_delayed_free(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state,
            tid,
            before_start=0,
            minutes=10,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))

        _, games = await self.tournament.create_new_pairings(self.tournament.waiting_players())
        self.assertEqual(len(games), 1)
        game = games[0]
        game.status = FLAG
        game.result = "0-1"
        game.board.ply = 0

        def discard_background_task(coro, *, name=None):
            coro.close()

        # Do not let delayed_free run. The pause must already be in MongoDB
        # when game_update() returns.
        with patch.object(
            app_state,
            "create_background_task",
            side_effect=discard_background_task,
        ):
            await self.tournament.game_update(game)

        white_data = self.tournament.player_data_by_name(game.wplayer.username)
        assert white_data is not None
        self.assertTrue(white_data.paused)
        white_doc = await app_state.db.tournament_player.find_one(
            {"tid": tid, "uid": game.wplayer.username}
        )
        assert white_doc is not None
        self.assertTrue(white_doc["a"])

    async def test_started_state_is_persisted_before_broadcast(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state,
            tid,
            before_start=0,
            minutes=10,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        persisted_statuses: list[int] = []

        async def broadcast(_response) -> None:
            doc = await app_state.db.tournament.find_one({"_id": tid})
            assert doc is not None
            persisted_statuses.append(doc["status"])

        with patch.object(self.tournament, "broadcast", side_effect=broadcast):
            await self.tournament.start(datetime.now(UTC))

        self.assertEqual(persisted_statuses, [self.tournament.status])

    async def test_player_state_changes_are_persisted_before_broadcast(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state,
            tid,
            before_start=10,
            minutes=10,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        player = self.add_user(f"rp-{id8()}")

        persisted_states: list[tuple[bool, bool]] = []

        async def capture_persisted_state(_response) -> None:
            doc = await app_state.db.tournament_player.find_one(
                {"tid": tid, "uid": player.username}
            )
            assert doc is not None
            persisted_states.append((doc["a"], doc.get("wd", False)))

        with patch.object(self.tournament, "broadcast", side_effect=capture_persisted_state):
            await self.tournament.join(player)
        self.assertEqual(persisted_states[-1], (False, False))

        with patch.object(self.tournament, "broadcast", side_effect=capture_persisted_state):
            await self.tournament.pause(player)
        self.assertEqual(persisted_states[-1], (True, False))

        with patch.object(self.tournament, "broadcast", side_effect=capture_persisted_state):
            await self.tournament.withdraw(player)
        self.assertEqual(persisted_states[-1], (False, True))
