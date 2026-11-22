import asyncio
import json
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from const import FLAG, T_ABORTED, T_CREATED, T_FINISHED, T_STARTED
from glicko2.glicko2 import new_default_perf, new_default_perf_map
from newid import id8
from push_notifications import RRArrangementPushJob
from pychess_global_app_state_utils import get_app_state
from seek import (
    DIRECT_CHALLENGE_CREATED,
    MAX_USER_SEEKS,
    Seek,
    create_seek,
    seek_counts_toward_limit,
    user_reached_seek_limit,
)
from tournament import swiss as swiss_mod
from tournament.auto_play_tournament import (
    ArenaTestTournament,
    RRTestTournament,
    SwissTestTournament,
)
from tournament.rr import (
    ARR_STATUS_EXPIRED,
    ARR_STATUS_FINISHED,
    ARR_STATUS_PENDING,
    ARR_STATUS_STARTED,
)
from tournament.tournament import (
    MANUAL_ROUND_INTERVAL,
    SCORE_SHIFT,
    GameData,
    upsert_tournament_to_db,
)
from tournament_test_base import ONE_TEST_ONLY, TournamentTestCase
from user import User
from variants import VARIANTS


def make_test_perfs():
    return new_default_perf_map(VARIANTS)


class TournamentFlowTestCase(TournamentTestCase):
    @staticmethod
    def _accelerate_arena_clock(tournament):
        """Shrink arena pairing cadence for faster deterministic tests."""
        tournament.wave = timedelta(milliseconds=200)
        tournament.wave_delta = timedelta(milliseconds=25)
        return tournament

    async def _arena_with_discord_failure(self, reminder_minutes: int, *, stalled: bool):
        app_state = get_app_state(self.app)
        now = datetime.now(UTC)
        self.tournament = ArenaTestTournament(
            app_state,
            id8(),
            variant="asean",
            starts_at=now + timedelta(minutes=reminder_minutes),
            minutes=60,
            with_clock=False,
        )
        tournament = self.tournament
        app_state.tournaments[tournament.id] = tournament
        app_state.tourneysockets[tournament.id] = {}
        await upsert_tournament_to_db(tournament, app_state)
        release_discord = asyncio.Event()

        async def send_to_discord(*args):
            nonlocal now
            now = tournament.starts_at
            if stalled:
                await release_discord.wait()
            else:
                raise OSError("Discord unavailable")

        original_start = tournament.start

        async def start(start_time):
            nonlocal now
            await original_start(start_time)
            doc = await app_state.db.tournament.find_one({"_id": tournament.id})
            self.assertEqual(doc["status"], T_STARTED)
            now = tournament.ends_at

        with (
            patch("tournament.tournament.datetime", wraps=datetime) as clock_datetime,
            patch.object(
                app_state.discord, "send_to_discord", side_effect=send_to_discord
            ) as send_mock,
            patch.object(tournament, "start", side_effect=start) as start_mock,
            patch("tournament.tournament.lichess_team_msg", new_callable=AsyncMock),
        ):
            clock_datetime.now.side_effect = lambda _tz: now
            tournament.clock_task = asyncio.create_task(tournament.clock())
            try:
                await asyncio.wait_for(tournament.clock_task, timeout=1)
                send_mock.assert_awaited_once()
                start_mock.assert_awaited_once()
                self.assertEqual(tournament.status, T_FINISHED)
                self.assertIsNone(await app_state.db.tournament.find_one({"_id": tournament.id}))
            finally:
                release_discord.set()
                await asyncio.sleep(0)

    async def test_arena_starts_and_finishes_when_discord_reminder_fails(self):
        for reminder_minutes in (360, 10):
            with self.subTest(reminder_minutes=reminder_minutes):
                await self._arena_with_discord_failure(reminder_minutes, stalled=False)

    async def test_arena_starts_and_finishes_while_discord_reminder_is_stalled(self):
        for reminder_minutes in (360, 10):
            with self.subTest(reminder_minutes=reminder_minutes):
                await self._arena_with_discord_failure(reminder_minutes, stalled=True)

    async def test_stalled_discord_reminder_is_cancelled_after_timeout(self):
        app_state = get_app_state(self.app)
        tournament = ArenaTestTournament(app_state, id8(), with_clock=False)
        cancelled = asyncio.Event()

        async def send_to_discord(*args):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with (
            patch("tournament.tournament.DISCORD_REMINDER_TIMEOUT", 0.01),
            patch.object(app_state.discord, "send_to_discord", side_effect=send_to_discord),
            self.assertLogs("tournament.tournament", level="ERROR") as logs,
        ):
            await asyncio.wait_for(tournament._send_discord_start_reminder("reminder"), timeout=1)

        self.assertTrue(cancelled.is_set())
        self.assertIn(tournament.id, logs.output[0])

    def _new_condition_user(
        self,
        tournament,
        username: str,
        *,
        title: str = "IM",
        rating: int = 1600,
        rated_games: int = 25,
        account_age_days: int = 60,
    ) -> User:
        app_state = get_app_state(self.app)
        perfs = {"chess": new_default_perf()}
        perfs["chess"]["gl"]["r"] = rating
        perfs["chess"]["nb"] = rated_games
        user = User(
            app_state,
            username=username,
            title=title,
            perfs=perfs,
            created_at=datetime.now(UTC) - timedelta(days=account_age_days),
        )
        user.tournament_sockets[tournament.id] = {None}
        app_state.users[user.username] = user
        return user

    async def _assert_non_swiss_entry_conditions(self, tournament) -> None:
        app_state = get_app_state(self.app)
        app_state.tournaments[tournament.id] = tournament

        low_rated = self._new_condition_user(tournament, f"{tournament.id}_low", rating=1300)
        self.assertEqual(
            await tournament.join(low_rated),
            "Your rating is below the minimum allowed for this tournament.",
        )

        too_new = self._new_condition_user(tournament, f"{tournament.id}_new", account_age_days=5)
        self.assertEqual(
            await tournament.join(too_new),
            "This tournament requires accounts to be at least 30 days old.",
        )

        too_few_games = self._new_condition_user(
            tournament, f"{tournament.id}_few_games", rated_games=5
        )
        self.assertEqual(
            await tournament.join(too_few_games),
            "This tournament requires at least 20 rated Chess games.",
        )

        allowed = self._new_condition_user(tournament, f"{tournament.id}_allowed")
        self.assertIsNone(await tournament.join(allowed))

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_arena_join_enforces_generic_entry_conditions(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=1,
            minutes=10,
            with_clock=False,
            entry_min_rating=1400,
            entry_max_rating=1800,
            entry_min_rated_games=20,
            entry_min_account_age_days=30,
        )
        await self._assert_non_swiss_entry_conditions(self.tournament)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_rr_join_enforces_generic_entry_conditions(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=1,
            rounds=0,
            rr_max_players=6,
            with_clock=False,
            entry_min_rating=1400,
            entry_max_rating=1800,
            entry_min_rated_games=20,
            entry_min_account_age_days=30,
        )
        await self._assert_non_swiss_entry_conditions(self.tournament)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_tournament_without_players(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = self._accelerate_arena_clock(
            ArenaTestTournament(app_state, tid, before_start=0, minutes=0.2 / 60.0)
        )
        app_state.tournaments[tid] = self.tournament

        self.assertEqual(self.tournament.status, T_CREATED)

        await asyncio.sleep(0.05)
        self.assertEqual(self.tournament.status, T_STARTED)

        if self.tournament.clock_task is not None:
            await asyncio.wait_for(self.tournament.clock_task, timeout=5)
        self.assertEqual(self.tournament.status, T_FINISHED)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_arena_without_pairings_is_destroyed_on_finish(self):
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
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(1)
        await app_state.db.tournament_chat.insert_one(
            {"tid": tid, "type": "lobbychat", "user": "spam", "message": "spam"}
        )

        await self.tournament.finish()

        self.assertEqual(self.tournament.status, T_FINISHED)
        self.assertNotIn(tid, app_state.tournaments)
        self.assertEqual(await app_state.db.tournament.count_documents({"_id": tid}), 0)
        self.assertEqual(await app_state.db.tournament_player.count_documents({"tid": tid}), 0)
        self.assertEqual(await app_state.db.tournament_chat.count_documents({"tid": tid}), 0)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_arena_with_pairing_history_is_kept_on_finish(self):
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
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(1)
        await app_state.db.tournament_pairing.insert_one({"_id": id8(), "tid": tid})

        await self.tournament.finish()

        self.assertEqual(self.tournament.status, T_FINISHED)
        self.assertIn(tid, app_state.tournaments)
        self.assertEqual(await app_state.db.tournament.count_documents({"_id": tid}), 1)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_swiss_start_reminder_notifies_active_team_players_once(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            rounds=3,
            with_clock=False,
            starts_at=datetime.now(UTC) + timedelta(minutes=10),
            name="Team Swiss reminder test",
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(3)
        self.tournament.team_id = "team-reminder-test"
        usernames = sorted(self.tournament.players_by_name)

        withdrawn_username = usernames[2]
        withdrawn_user = self.tournament.get_player_by_name(withdrawn_username)
        assert withdrawn_user is not None
        await self.tournament.withdraw(withdrawn_user)

        offline_username = usernames[1]
        app_state.users.data.pop(offline_username, None)

        await self.tournament.send_scheduled_start_reminders()

        notifications = await app_state.db.notify.find(
            {"type": "swissStartReminder", "content.tid": tid}
        ).to_list(length=10)
        self.assertEqual(
            {notification["notifies"] for notification in notifications},
            {usernames[0], offline_username},
        )
        self.assertNotIn(offline_username, app_state.users.data)
        self.assertNotIn(withdrawn_username, {n["notifies"] for n in notifications})

        loaded_user = app_state.users[usernames[0]]
        self.assertIsNotNone(loaded_user.notifications)
        assert loaded_user.notifications is not None
        self.assertEqual(loaded_user.notifications[-1]["type"], "swissStartReminder")
        self.assertEqual(loaded_user.notifications[-1]["content"]["tid"], tid)

        await self.tournament.send_scheduled_start_reminders()
        self.assertEqual(
            await app_state.db.notify.count_documents(
                {"type": "swissStartReminder", "content.tid": tid}
            ),
            2,
        )

        # A genuinely rescheduled start gets one new reminder per active player.
        self.tournament.starts_at += timedelta(hours=1)
        await self.tournament.send_scheduled_start_reminders()
        self.assertEqual(
            await app_state.db.notify.count_documents(
                {"type": "swissStartReminder", "content.tid": tid}
            ),
            4,
        )

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_swiss_start_reminder_skips_non_team_swiss(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            rounds=3,
            with_clock=False,
            starts_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(2)

        await self.tournament.send_scheduled_start_reminders()

        self.assertEqual(
            await app_state.db.notify.count_documents(
                {"type": "swissStartReminder", "content.tid": tid}
            ),
            0,
        )

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_swiss_first_round_waits_for_late_players(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            rounds=3,
            round_interval=MANUAL_ROUND_INTERVAL,
            starts_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await asyncio.sleep(0.05)
        self.assertEqual(self.tournament.status, T_CREATED)

        await self.tournament.join_players(2)
        for _ in range(50):
            if self.tournament.status != T_CREATED:
                break
            await asyncio.sleep(0.02)

        self.assertEqual(self.tournament.status, T_STARTED)

        if self.tournament.clock_task is not None:
            task = self.tournament.clock_task
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_swiss_first_round_grace_counts_only_active_players(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            rounds=3,
            starts_at=datetime.now(UTC) - timedelta(minutes=30),
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(2)
        await self.tournament.withdraw(list(self.tournament.players)[0])

        self.tournament.clock_task = asyncio.create_task(
            self.tournament.clock(), name="test-swiss-grace-clock"
        )
        await asyncio.sleep(0.05)

        self.assertEqual(self.tournament.nb_players, 1)
        self.assertEqual(self.tournament.status, T_CREATED)

        if self.tournament.clock_task is not None:
            task = self.tournament.clock_task
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_swiss_first_round_aborts_after_grace_expires(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            rounds=3,
            starts_at=datetime.now(UTC) - timedelta(hours=1, seconds=1),
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        if self.tournament.clock_task is not None:
            await asyncio.wait_for(self.tournament.clock_task, timeout=1)

        self.assertEqual(self.tournament.status, T_ABORTED)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_tournament_players(self):
        app_state = get_app_state(self.app)
        NB_PLAYERS = 15
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, before_start=0, minutes=0, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(NB_PLAYERS)

        self.assertEqual(len(self.tournament.leaderboard), NB_PLAYERS)

        withdrawn_player = next(iter(self.tournament.players))
        await self.tournament.withdraw(withdrawn_player)

        self.assertNotIn(withdrawn_player, self.tournament.leaderboard)
        self.assertEqual(len(self.tournament.players), NB_PLAYERS)
        self.assertEqual(len(self.tournament.leaderboard), NB_PLAYERS - 1)

        self.assertEqual(self.tournament.status, T_CREATED)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_tournament_with_3_active_players(self):
        app_state = get_app_state(self.app)
        NB_PLAYERS = 15
        tid = id8()
        self.tournament = self._accelerate_arena_clock(
            ArenaTestTournament(app_state, tid, before_start=0.001, minutes=0.01)
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(NB_PLAYERS)

        # 12 player leave the tournament lobby
        for i in range(12):
            del list(self.tournament.players.keys())[i].tournament_sockets[self.tournament.id]
        self.assertEqual(len(self.tournament.waiting_players()), NB_PLAYERS - 12)

        await self.tournament.clock_task

        self.assertEqual(self.tournament.status, T_FINISHED)

        for user in self.tournament.players:
            self.assertTrue(self.tournament.players[user].nb_not_paired <= 1)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_tournament_pairing_5_round_SWISS(self):
        app_state = get_app_state(self.app)
        NB_PLAYERS = 15
        NB_ROUNDS = 5
        tid = id8()
        self.tournament = SwissTestTournament(app_state, tid, before_start=0, rounds=NB_ROUNDS)
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(NB_PLAYERS)

        await self.tournament.clock_task

        self.assertEqual(self.tournament.status, T_FINISHED)
        self.assertEqual(
            [len(player.games) for player in self.tournament.players.values()],
            NB_PLAYERS * [NB_ROUNDS],
        )

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_fixed_round_swiss_ignores_minutes_deadline(self):
        app_state = get_app_state(self.app)
        NB_PLAYERS = 7
        NB_ROUNDS = 3
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            before_start=0,
            rounds=NB_ROUNDS,
            minutes=0,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(NB_PLAYERS)

        if self.tournament.clock_task is not None:
            await asyncio.wait_for(self.tournament.clock_task, timeout=20)

        self.assertEqual(self.tournament.status, T_FINISHED)
        self.assertEqual(
            [len(player.games) for player in self.tournament.players.values()],
            NB_PLAYERS * [NB_ROUNDS],
        )

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_tournament_pairing_1_min_ARENA(self):
        app_state = get_app_state(self.app)
        NB_PLAYERS = 15
        tid = id8()
        self.tournament = self._accelerate_arena_clock(
            ArenaTestTournament(app_state, tid, before_start=0.001, minutes=0.01)
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(NB_PLAYERS)

        # withdraw one player
        await self.tournament.withdraw(list(self.tournament.players.keys())[-1])
        self.assertEqual(self.tournament.nb_players, NB_PLAYERS - 1)

        # make the first player leave the tournament lobby
        del list(self.tournament.players.keys())[0].tournament_sockets[self.tournament.id]

        self.assertEqual(len(self.tournament.waiting_players()), NB_PLAYERS - 2)

        await self.tournament.clock_task

        self.assertEqual(self.tournament.status, T_FINISHED)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_rr_start_creates_full_arrangement_matrix(self):
        app_state = get_app_state(self.app)
        NB_PLAYERS = 5

        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=0,
            rr_max_players=NB_PLAYERS,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(NB_PLAYERS)
        await self.tournament.start(datetime.now(UTC))

        self.assertEqual(self.tournament.status, T_STARTED)
        self.assertEqual(self.tournament.rounds, NB_PLAYERS)
        self.assertEqual(len(self.tournament.arrangements), 10)
        payload = self.tournament.arrangement_payload()
        self.assertEqual(payload["totalGames"], 10)
        self.assertEqual(payload["completedGames"], 0)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_rr_prestart_payload_exposes_projected_arrangements(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(3)

        payload = self.tournament.arrangement_payload()
        self.assertEqual(payload["totalGames"], 3)
        self.assertEqual(
            payload["players"], [player.username for player in self.tournament.leaderboard]
        )
        matrix = payload["matrix"]
        first = next(iter(payload["players"]))
        self.assertTrue(any(cell.get("id") for cell in matrix[first].values()))

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_rr_prestart_payload_handles_two_joined_players(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(2)

        payload = self.tournament.arrangement_payload()
        self.assertEqual(payload["totalGames"], 1)
        self.assertEqual(
            payload["players"], [player.username for player in self.tournament.leaderboard]
        )
        first, second = payload["players"]
        self.assertEqual(payload["matrix"][first][second]["round"], 1)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_rr_projected_arrangements_cover_each_pair_once(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=0,
            rr_max_players=8,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(5)

        players = [player.username for player in self.tournament.leaderboard]
        arrangements = self.tournament.arrangement_list()
        self.assertEqual(len(arrangements), 10)
        self.assertEqual({arrangement.round_no for arrangement in arrangements}, {1, 2, 3, 4, 5})

        seen_pairs = {
            tuple(sorted((arrangement.white, arrangement.black))) for arrangement in arrangements
        }
        expected_pairs = {
            tuple(sorted((players[left], players[right])))
            for left in range(len(players))
            for right in range(left + 1, len(players))
        }
        self.assertEqual(seen_pairs, expected_pairs)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_rr_payload_cells_include_player_points(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(2)

        arrangement = self.tournament.arrangement_list()[0]
        arrangement.status = ARR_STATUS_FINISHED
        arrangement.game_id = id8()

        game = GameData(
            arrangement.game_id,
            arrangement.white,
            "1500",
            arrangement.black,
            "1500",
            "1-0",
            datetime.now(UTC),
            False,
            False,
        )

        white_data = self.tournament.player_data_by_name(arrangement.white)
        black_data = self.tournament.player_data_by_name(arrangement.black)
        assert white_data is not None
        assert black_data is not None
        white_data.games.append(game)
        black_data.games.append(game)
        white_data.points.append((2, 1))
        black_data.points.append((0, 1))

        payload = self.tournament.arrangement_payload()
        matrix = payload["matrix"]
        white_cell = matrix[arrangement.white][arrangement.black]
        black_cell = matrix[arrangement.black][arrangement.white]

        self.assertEqual(white_cell["result"], "1-0")
        self.assertEqual(black_cell["result"], "1-0")
        self.assertEqual(white_cell["points"], 2)
        self.assertEqual(black_cell["points"], 0)

    @unittest.skipIf(ONE_TEST_ONLY, "1 test only")
    async def test_rr_finishes_on_minutes_deadline_with_incomplete_arrangements(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            before_start=0.01,
            rounds=0,
            rr_max_players=6,
            minutes=0.001,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(5)

        if self.tournament.clock_task is not None:
            await asyncio.wait_for(self.tournament.clock_task, timeout=20)

        self.assertEqual(self.tournament.status, T_FINISHED)
        self.assertEqual(len(self.tournament.arrangements), 10)
        self.assertFalse(self.tournament.all_arrangements_finished())
        self.assertTrue(
            all(
                arrangement.status == ARR_STATUS_EXPIRED
                for arrangement in self.tournament.arrangements.values()
            )
        )

    async def test_rr_deadline_drains_running_game_before_finishing(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            before_start=0,
            rounds=0,
            rr_max_players=4,
            minutes=45,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))

        running_arrangement = self.tournament.arrangement_list()[0]
        running_game = await self.tournament.start_arrangement_game(running_arrangement.id)
        running_names = set(running_arrangement.players())
        challenged_arrangement = next(
            arrangement
            for arrangement in self.tournament.arrangement_list()
            if running_names.isdisjoint(arrangement.players())
        )
        challenger = app_state.users[challenged_arrangement.white]
        challenge_error = await self.tournament.create_arrangement_challenge(
            challenger, challenged_arrangement.id
        )
        self.assertIsNone(challenge_error)
        challenge_id = challenged_arrangement.invite_id
        self.assertIsNotNone(challenge_id)
        assert challenge_id is not None
        self.assertIn(challenge_id, app_state.invites)

        deadline = datetime.now(UTC) - timedelta(seconds=1)
        self.tournament.ends_at = deadline
        self.tournament.clock_task = asyncio.create_task(
            self.tournament.clock(), name="test-rr-deadline-drain"
        )
        await asyncio.sleep(self.tournament.clock_interval * 3)

        self.assertEqual(self.tournament.status, T_STARTED)
        self.assertIn(running_game, self.tournament.ongoing_games)
        self.assertEqual(running_arrangement.status, ARR_STATUS_STARTED)
        self.assertEqual(challenged_arrangement.status, ARR_STATUS_EXPIRED)
        self.assertNotIn(challenge_id, app_state.invites)
        self.assertFalse(
            any(
                seek.rr_arrangement_id == challenged_arrangement.id
                for seek in app_state.seeks.values()
            )
        )

        self.assertEqual(
            await self.tournament.set_arrangement_time(
                challenger, challenged_arrangement.id, datetime.now(UTC) + timedelta(hours=1)
            ),
            "The round-robin scheduling deadline has passed.",
        )
        self.assertEqual(
            await self.tournament.create_arrangement_challenge(
                challenger, challenged_arrangement.id
            ),
            "The round-robin challenge deadline has passed.",
        )
        accept_result = await self.tournament.accept_arrangement_challenge(
            app_state.users[challenged_arrangement.black], challenged_arrangement.id
        )
        self.assertEqual(accept_result["type"], "error")
        self.assertEqual(accept_result["message"], "The round-robin challenge deadline has passed.")

        running_game.board.ply = 20
        await running_game.game_ended(running_game.bplayer, "resign")
        if self.tournament.clock_task is not None:
            await asyncio.wait_for(self.tournament.clock_task, timeout=2)

        self.assertEqual(self.tournament.status, T_FINISHED)
        self.assertEqual(self.tournament.nb_games_finished, 1)
        self.assertEqual(running_arrangement.status, ARR_STATUS_FINISHED)
        self.assertEqual(len(self.tournament.ongoing_games), 0)
        self.assertGreater(
            self.tournament.leaderboard_score_by_username(running_game.wplayer.username)
            // SCORE_SHIFT,
            0,
        )

    async def test_fixed_round_manual_next_round_waits_for_organizer(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            before_start=0,
            rounds=2,
            round_interval=MANUAL_ROUND_INTERVAL,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))

        self.tournament.current_round = 1
        self.assertTrue(await self.tournament.maybe_schedule_next_fixed_round(datetime.now(UTC)))
        self.assertTrue(self.tournament.manual_next_round_pending)
        self.assertEqual(self.tournament.current_round, 1)
        self.assertEqual(len(self.tournament.ongoing_games), 0)
        self.assertTrue(self.tournament.live_status()["manualNextRound"])

        self.assertTrue(await self.tournament.start_next_round_now(datetime.now(UTC)))
        self.assertFalse(self.tournament.manual_next_round_pending)
        self.assertEqual(self.tournament.current_round, 2)
        self.assertGreater(len(self.tournament.ongoing_games), 0)

    async def test_fixed_round_standings_mark_ongoing_games_with_star(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=0, rounds=3, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(3)
        await self.tournament.start(datetime.now(UTC))

        self.tournament.current_round = 1
        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        self.assertEqual(len(games), 1)

        players_json = self.tournament.players_json()
        star_marked_rows = [
            row
            for row in players_json["players"]
            if any(
                isinstance(point, tuple) and len(point) > 0 and point[0] == "*"
                for point in row["points"]
            )
        ]
        self.assertEqual(len(star_marked_rows), 2)

        for player_data in self.tournament.players.values():
            self.assertFalse(
                any(
                    isinstance(point, tuple) and len(point) > 0 and point[0] == "*"
                    for point in player_data.points
                )
            )

    async def test_fixed_round_players_remain_pairable_from_finished_game_socket(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = swiss_mod.SwissTournament(
            app_state, tid, variant="chess", before_start=0, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}

        class _DummyWs:
            def __init__(self):
                self.messages: list[dict[str, object]] = []

            async def send_str(self, payload: str) -> None:
                self.messages.append(json.loads(payload))

            async def close(self) -> None:
                return None

        lobby_ws = _DummyWs()
        players = []
        for suffix in ("A", "B", "C", "D"):
            user = User(app_state, username=f"fixed_round_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {lobby_ws}
            app_state.tourneysockets[tid][user.username] = user.tournament_sockets[tid]
            await self.tournament.join(user)
            players.append(user)

        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1

        waiting_round_1 = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_round_1)
        self.assertEqual(len(games), 2)

        for game in games:
            game.result = "1-0"
            game.status = FLAG
            game.board.ply = 20
            await self.tournament.game_update(game)

        await asyncio.sleep(0)

        game_ws_by_user: dict[str, _DummyWs] = {}
        for game in games:
            for player in (game.wplayer, game.bplayer):
                game_ws = _DummyWs()
                game_ws_by_user[player.username] = game_ws
                player.tournament_sockets[tid] = set()
                app_state.tourneysockets[tid][player.username] = player.tournament_sockets[tid]
                player.game_sockets[game.id] = {game_ws}

        self.tournament.current_round = 2
        waiting_round_2 = list(self.tournament.waiting_players())
        self.assertEqual(
            {player.username for player in waiting_round_2},
            {player.username for player in players},
        )

        _, round_2_games = await self.tournament.create_new_pairings(waiting_round_2)
        self.assertEqual(len(round_2_games), 2)

        for player in players:
            player_data = self.tournament.player_data_by_name(player.username)
            self.assertIsNotNone(player_data)
            assert player_data is not None
            self.assertFalse(player_data.paused)
            self.assertTrue(
                any(
                    msg.get("type") == "new_game"
                    for msg in game_ws_by_user[player.username].messages
                )
            )

    async def test_rr_waiting_players_ignore_socket_presence(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=6,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))

        for player in self.tournament.players:
            player.tournament_sockets[self.tournament.id] = set()

        waiting_players = list(self.tournament.waiting_players())
        self.assertEqual(
            {player.username for player in waiting_players},
            {player.username for player in self.tournament.players},
        )

    async def test_rr_join_refuses_players_beyond_max_players(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=10,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        await self.tournament.join_players(10)
        self.assertEqual(self.tournament.nb_players, 10)
        self.assertEqual(len(self.tournament.players), 10)

        extra = User(app_state, username=f"{tid}_extra", perfs=make_test_perfs())
        extra.tournament_sockets[self.tournament.id] = {None}
        app_state.users[extra.username] = extra
        self.assertEqual(await self.tournament.join(extra), "This round-robin tournament is full.")

    async def test_rr_start_derives_rounds_from_joined_players(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=10,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        await self.tournament.join_players(5)
        await self.tournament.start(datetime.now(UTC))
        self.assertEqual(self.tournament.rounds, 5)

        tid_even = id8()
        even_tournament = RRTestTournament(
            app_state,
            tid_even,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=10,
            with_clock=False,
        )
        app_state.tournaments[tid_even] = even_tournament

        await even_tournament.join_players(4)
        await even_tournament.start(datetime.now(UTC))
        self.assertEqual(even_tournament.rounds, 3)

    async def test_rr_late_join_is_closed_after_start(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=10,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))

        late = User(app_state, username=f"{tid}_late", perfs=make_test_perfs())
        late.tournament_sockets[self.tournament.id] = {None}
        app_state.users[late.username] = late

        self.assertEqual(
            await self.tournament.join(late),
            "Late join is closed for this round-robin tournament.",
        )

        self.assertEqual(self.tournament.nb_players, 4)
        self.assertEqual(len(self.tournament.players), 4)

    async def test_rr_join_request_requires_organizer_approval_when_enabled(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=8,
            rr_requires_approval=True,
            with_clock=False,
        )
        self.tournament.created_by = "rr_host"
        app_state.tournaments[tid] = self.tournament

        organizer = User(app_state, username="rr_host", perfs=make_test_perfs())
        app_state.users[organizer.username] = organizer

        applicant = User(app_state, username=f"{tid}_pending", perfs=make_test_perfs())
        applicant.tournament_sockets[self.tournament.id] = {None}
        app_state.users[applicant.username] = applicant

        self.assertEqual(await self.tournament.join(applicant), "JOIN_REQUESTED")
        self.assertEqual(self.tournament.user_status(applicant), "pending")
        self.assertIn(applicant.username, self.tournament.rr_pending_players)
        self.assertEqual(self.tournament.nb_players, 0)

        self.assertIsNone(await self.tournament.rr_approve_player(applicant.username))
        self.assertEqual(self.tournament.user_status(applicant), "joined")
        self.assertNotIn(applicant.username, self.tournament.rr_pending_players)
        self.assertEqual(self.tournament.nb_players, 1)

    async def test_rr_joining_can_be_closed_and_reopened_by_organizer(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=8,
            with_clock=False,
        )
        self.tournament.created_by = "rr_host"
        app_state.tournaments[tid] = self.tournament

        organizer = User(app_state, username="rr_host", perfs=make_test_perfs())
        app_state.users[organizer.username] = organizer

        applicant = User(app_state, username=f"{tid}_closed", perfs=make_test_perfs())
        app_state.users[applicant.username] = applicant

        self.assertIsNone(await self.tournament.rr_set_joining_closed(True))
        self.assertTrue(self.tournament.rr_joining_closed)
        self.assertEqual(
            await self.tournament.join(applicant),
            "Joining is currently closed for this round-robin tournament.",
        )
        self.assertEqual(self.tournament.nb_players, 0)

        self.assertIsNone(await self.tournament.rr_set_joining_closed(False))
        self.assertFalse(self.tournament.rr_joining_closed)
        self.assertIsNone(await self.tournament.join(applicant))
        self.assertEqual(self.tournament.nb_players, 1)

    async def test_rr_challenge_creates_notification_for_opponent(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B", "C"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))

        arrangement = next(
            arr for arr in self.tournament.arrangement_list() if arr.involves(users[0].username)
        )
        challenger = next(user for user in users if user.username == arrangement.white)
        opponent_name = arrangement.black
        opponent = app_state.users[opponent_name]

        self.assertIsNone(
            await self.tournament.create_arrangement_challenge(challenger, arrangement.id)
        )
        self.assertIsNotNone(opponent.notifications)
        assert opponent.notifications is not None
        self.assertEqual(opponent.notifications[-1]["type"], "rrChallenge")
        self.assertEqual(opponent.notifications[-1]["content"]["tid"], tid)
        self.assertEqual(opponent.notifications[-1]["content"]["arr"], arrangement.id)
        self.assertEqual(opponent.notifications[-1]["content"]["opp"], challenger.username)

    async def test_rr_challenge_bypasses_lobby_seek_limit_and_does_not_count_toward_it(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        players = {user.username: user for user in users}
        challenger = players[arrangement.white]

        for _ in range(MAX_USER_SEEKS):
            seek = Seek(id8(), challenger, "chess", player1=challenger)
            app_state.seeks[seek.id] = seek
            challenger.seeks[seek.id] = seek

        self.assertTrue(user_reached_seek_limit(challenger, 0))

        forged_seek = await create_seek(
            app_state.db,
            app_state.invites,
            app_state.seeks,
            challenger,
            {
                "variant": "chess",
                "fen": "",
                "color": "w",
                "minutes": 5,
                "increment": 0,
                "byoyomiPeriod": 0,
                "rated": False,
                "chess960": False,
                "target": arrangement.black,
                "reserveGameId": True,
                "tournamentId": tid,
                "rrArrangementId": arrangement.id,
            },
        )
        self.assertIsNone(forged_seek)

        self.assertIsNone(
            await self.tournament.create_arrangement_challenge(challenger, arrangement.id)
        )
        rr_seek = next(
            seek for seek in app_state.seeks.values() if seek.rr_arrangement_id == arrangement.id
        )
        self.assertFalse(seek_counts_toward_limit(rr_seek))
        self.assertEqual(
            MAX_USER_SEEKS,
            sum(seek_counts_toward_limit(seek) for seek in challenger.seeks.values()),
        )

    async def test_rr_challenge_bypasses_mutual_blocks_on_create_and_accept(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        players = {user.username: user for user in users}
        challenger = players[arrangement.white]
        opponent = players[arrangement.black]
        challenger.blocked.add(opponent.username)
        opponent.blocked.add(challenger.username)

        self.assertIsNone(
            await self.tournament.create_arrangement_challenge(challenger, arrangement.id)
        )
        result = await self.tournament.accept_arrangement_challenge(opponent, arrangement.id)

        self.assertEqual("new_game", result["type"])
        game = app_state.games[result["gameId"]]
        self.assertEqual(tid, game.tournamentId)
        self.assertEqual(arrangement.id, getattr(game, "tournamentArrangementId", None))

    async def test_rr_challenge_does_not_replace_normal_direct_challenge(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        players = {user.username: user for user in users}
        challenger = players[arrangement.white]
        opponent = players[arrangement.black]
        normal_seek = await create_seek(
            app_state.db,
            app_state.invites,
            app_state.seeks,
            challenger,
            {
                "variant": "chess",
                "fen": "",
                "color": "r",
                "minutes": 5,
                "increment": 3,
                "byoyomiPeriod": 0,
                "rated": False,
                "chess960": False,
                "target": opponent.username,
            },
        )
        assert normal_seek is not None

        self.assertIsNone(
            await self.tournament.create_arrangement_challenge(challenger, arrangement.id)
        )
        rr_seek = next(
            seek for seek in app_state.seeks.values() if seek.rr_arrangement_id == arrangement.id
        )

        self.assertEqual(DIRECT_CHALLENGE_CREATED, normal_seek.challenge_status)
        self.assertEqual(DIRECT_CHALLENGE_CREATED, rr_seek.challenge_status)

        replacement = await create_seek(
            app_state.db,
            app_state.invites,
            app_state.seeks,
            challenger,
            {
                "variant": "chess",
                "fen": "",
                "color": "r",
                "minutes": 3,
                "increment": 2,
                "byoyomiPeriod": 0,
                "rated": False,
                "chess960": False,
                "target": opponent.username,
            },
        )
        assert replacement is not None
        self.assertEqual(DIRECT_CHALLENGE_CREATED, rr_seek.challenge_status)
        self.assertNotEqual(rr_seek.id, replacement.id)

    async def test_rr_simultaneous_challenges_create_only_one_invite(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        players = {user.username: user for user in users}
        white = players[arrangement.white]
        black = players[arrangement.black]

        from tournament.rr import tournament as rr_tournament_module

        original_create_seek = rr_tournament_module.create_seek
        create_seek_calls = 0

        async def yielding_create_seek(*args, **kwargs):
            nonlocal create_seek_calls
            create_seek_calls += 1
            # Without RR mutation serialization this yield lets the opponent pass
            # the same "no invite" check and create a second orphaned seek.
            await asyncio.sleep(0)
            return await original_create_seek(*args, **kwargs)

        with patch(
            "tournament.rr.tournament.create_seek",
            new=yielding_create_seek,
        ):
            results = await asyncio.gather(
                self.tournament.create_arrangement_challenge(white, arrangement.id),
                self.tournament.create_arrangement_challenge(black, arrangement.id),
            )

        self.assertEqual(results, [None, None])
        self.assertEqual(create_seek_calls, 1)
        arrangement_seeks = [
            seek for seek in app_state.seeks.values() if seek.rr_arrangement_id == arrangement.id
        ]
        self.assertEqual(len(arrangement_seeks), 1)
        self.assertEqual(arrangement.invite_id, arrangement_seeks[0].game_id)
        self.assertIn(arrangement.invite_id, app_state.invites)

    async def test_rr_prestart_challenge_survives_start(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=10,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B", "C"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        payload = self.tournament.arrangement_payload()
        arrangement_id = next(
            cell["id"]
            for row in payload["matrix"].values()
            for cell in row.values()
            if cell["id"] and cell["white"] == users[0].username
        )
        self.assertIsNone(
            await self.tournament.create_arrangement_challenge(users[0], arrangement_id)
        )

        arrangement_before = self.tournament.arrangement_by_id(arrangement_id)
        assert arrangement_before is not None
        self.assertEqual(arrangement_before.status, "challenged")
        self.assertIsNotNone(arrangement_before.invite_id)

        await self.tournament.start(datetime.now(UTC))

        arrangement_after = self.tournament.arrangement_by_id(arrangement_id)
        assert arrangement_after is not None
        self.assertEqual(arrangement_after.status, "challenged")
        self.assertEqual(arrangement_after.invite_id, arrangement_before.invite_id)

    async def test_rr_scheduling_sets_player_proposals_and_agreed_time(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            minutes=7 * 24 * 60,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B", "C"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            user.rr_push_enabled = True
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))

        arrangement = next(
            arr for arr in self.tournament.arrangement_list() if arr.involves(users[0].username)
        )
        white = next(user for user in users if user.username == arrangement.white)
        black = next(user for user in users if user.username == arrangement.black)

        proposed = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)
        self.assertIsNone(
            await self.tournament.set_arrangement_time(white, arrangement.id, proposed)
        )
        self.assertEqual(arrangement.white_date, proposed)
        self.assertIsNone(arrangement.scheduled_at)

        agreed = proposed + timedelta(seconds=45)
        self.assertIsNone(await self.tournament.set_arrangement_time(black, arrangement.id, agreed))
        self.assertEqual(arrangement.black_date, agreed)
        self.assertEqual(arrangement.scheduled_at, proposed)

        job = app_state.push_notifier.queue.get_nowait()
        self.assertIsInstance(job, RRArrangementPushJob)
        assert isinstance(job, RRArrangementPushJob)
        self.assertEqual(job.username, white.username)
        self.assertEqual(job.kind, "confirmed")
        self.assertEqual(job.arrangement_id, arrangement.id)
        app_state.push_notifier.queue.task_done()

    async def test_rr_prestart_scheduling_rejects_stale_and_post_deadline_times(self):
        app_state = get_app_state(self.app)
        tid = id8()
        now = datetime.now(UTC).replace(microsecond=0)
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            starts_at=now + timedelta(hours=1),
            minutes=120,
            rounds=0,
            rr_max_players=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        arrangement = self.tournament.arrangement_list()[0]
        white = next(user for user in users if user.username == arrangement.white)

        self.assertEqual(
            await self.tournament.set_arrangement_time(
                white, arrangement.id, now - timedelta(minutes=6)
            ),
            "Round-robin game times cannot be scheduled in the past.",
        )
        self.assertIsNone(arrangement.white_date)

        self.assertEqual(
            await self.tournament.set_arrangement_time(
                white, arrangement.id, self.tournament.ends_at
            ),
            "Round-robin game times must be before the tournament deadline.",
        )
        self.assertEqual(
            await self.tournament.set_arrangement_time(
                white, arrangement.id, self.tournament.ends_at + timedelta(minutes=1)
            ),
            "Round-robin game times must be before the tournament deadline.",
        )
        self.assertIsNone(arrangement.white_date)

        near_now = now - timedelta(minutes=1)
        self.assertIsNone(
            await self.tournament.set_arrangement_time(white, arrangement.id, near_now)
        )
        self.assertEqual(arrangement.white_date, near_now)

    async def test_rr_started_scheduling_accepts_time_before_deadline(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            minutes=24 * 60,
            rounds=0,
            rr_max_players=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        white = next(user for user in users if user.username == arrangement.white)
        before_deadline = self.tournament.ends_at - timedelta(minutes=1)

        self.assertIsNone(
            await self.tournament.set_arrangement_time(white, arrangement.id, before_deadline)
        )
        self.assertEqual(arrangement.white_date, before_deadline.replace(microsecond=0))
        self.assertEqual(
            await self.tournament.set_arrangement_time(
                white, arrangement.id, self.tournament.ends_at
            ),
            "Round-robin game times must be before the tournament deadline.",
        )
        self.assertEqual(arrangement.white_date, before_deadline.replace(microsecond=0))

    async def test_rr_scheduling_keeps_db_write_inside_mutation_lock(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            minutes=7 * 24 * 60,
            rounds=0,
            rr_max_players=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        players = {user.username: user for user in users}
        white = players[arrangement.white]
        black = players[arrangement.black]
        proposed = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)
        agreed = proposed + timedelta(seconds=30)

        first_write_started = asyncio.Event()
        release_first_write = asyncio.Event()
        write_calls = 0

        async def delayed_db_update(current_arrangement):
            nonlocal write_calls
            write_calls += 1
            snapshot = current_arrangement.update_doc(self.tournament.id)
            if write_calls == 1:
                first_write_started.set()
                await release_first_write.wait()
            await app_state.db.tournament_arrangement.update_one(
                {"_id": current_arrangement.id},
                {"$set": snapshot},
                upsert=True,
            )

        with patch.object(
            self.tournament,
            "db_update_arrangement",
            new=delayed_db_update,
        ):
            white_task = asyncio.create_task(
                self.tournament.set_arrangement_time(white, arrangement.id, proposed)
            )
            await first_write_started.wait()

            black_task = asyncio.create_task(
                self.tournament.set_arrangement_time(black, arrangement.id, agreed)
            )
            await asyncio.sleep(0)
            self.assertEqual(
                write_calls,
                1,
                "A second arrangement mutation entered while the first DB write was pending",
            )

            release_first_write.set()
            self.assertEqual(await asyncio.gather(white_task, black_task), [None, None])

        self.assertEqual(write_calls, 2)
        stored = await app_state.db.tournament_arrangement.find_one({"_id": arrangement.id})
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["d1"], proposed)
        self.assertEqual(stored["d2"], agreed)
        self.assertEqual(stored["sa"], proposed)

    async def test_rr_scheduling_clears_agreement_when_player_changes_time(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            minutes=7 * 24 * 60,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B", "C"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))

        arrangement = next(
            arr for arr in self.tournament.arrangement_list() if arr.involves(users[0].username)
        )
        white = next(user for user in users if user.username == arrangement.white)
        black = next(user for user in users if user.username == arrangement.black)

        proposed = datetime.now(UTC).replace(microsecond=0) + timedelta(days=2)
        self.assertIsNone(
            await self.tournament.set_arrangement_time(white, arrangement.id, proposed)
        )
        self.assertIsNone(
            await self.tournament.set_arrangement_time(
                black, arrangement.id, proposed + timedelta(seconds=30)
            )
        )
        self.assertEqual(arrangement.scheduled_at, proposed)

        later = proposed + timedelta(hours=2)
        self.assertIsNone(await self.tournament.set_arrangement_time(white, arrangement.id, later))
        self.assertEqual(arrangement.white_date, later)
        self.assertIsNone(arrangement.scheduled_at)

    async def test_rr_prestart_scheduling_survives_start(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=10,
            minutes=7 * 24 * 60,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B", "C"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        arrangement_id = next(
            cell["id"]
            for row in self.tournament.arrangement_payload()["matrix"].values()
            for cell in row.values()
            if cell["id"] and cell["white"] == users[0].username
        )
        proposed = datetime.now(UTC).replace(microsecond=0) + timedelta(days=3)
        self.assertIsNone(
            await self.tournament.set_arrangement_time(users[0], arrangement_id, proposed)
        )

        arrangement_before = self.tournament.arrangement_by_id(arrangement_id)
        assert arrangement_before is not None
        self.assertEqual(arrangement_before.white_date, proposed)

        await self.tournament.start(datetime.now(UTC))

        arrangement_after = self.tournament.arrangement_by_id(arrangement_id)
        assert arrangement_after is not None
        self.assertEqual(arrangement_after.white_date, proposed)

    async def test_rr_arrangement_reminders_fire_for_agreed_games(self):
        app_state = get_app_state(self.app)
        app_state.push_notifier.enabled = True
        tid = id8()
        self.tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=4,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament

        users = []
        for suffix in ("A", "B", "C"):
            user = User(app_state, username=f"{tid}_{suffix}", perfs=make_test_perfs())
            user.rr_push_enabled = True
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)
            users.append(user)

        await self.tournament.start(datetime.now(UTC))

        arrangement = next(
            arr for arr in self.tournament.arrangement_list() if arr.involves(users[0].username)
        )
        arrangement.scheduled_at = datetime.now(UTC) + timedelta(hours=23, minutes=30)
        arrangement.date = datetime.now(UTC) - timedelta(hours=4)

        await self.tournament.send_arrangement_reminders(datetime.now(UTC))

        for user in (app_state.users[arrangement.white], app_state.users[arrangement.black]):
            self.assertIsNotNone(user.notifications)
            assert user.notifications is not None
            self.assertEqual(user.notifications[-1]["type"], "rrArrangementReminder")
            self.assertEqual(user.notifications[-1]["content"]["arr"], arrangement.id)

        jobs = [app_state.push_notifier.queue.get_nowait() for _ in range(2)]
        rr_jobs = [job for job in jobs if isinstance(job, RRArrangementPushJob)]
        self.assertEqual(len(rr_jobs), 2)
        self.assertEqual({job.username for job in rr_jobs}, {arrangement.white, arrangement.black})
        self.assertEqual({job.kind for job in rr_jobs}, {"reminder"})
        for _ in jobs:
            app_state.push_notifier.queue.task_done()

    async def test_swiss_ws_redirect_failure_does_not_pause_players(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = swiss_mod.SwissTournament(
            app_state, tid, variant="chess", before_start=0, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament

        players = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"fixed_round_wsless_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            await self.tournament.join(user)
            players.append(user)

        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1

        waiting_players = list(self.tournament.waiting_players())
        self.assertEqual(
            {player.username for player in waiting_players},
            {player.username for player in players},
        )

        _, games = await self.tournament.create_new_pairings(waiting_players)
        self.assertEqual(len(games), 1)

        for player in players:
            player_data = self.tournament.player_data_by_name(player.username)
            self.assertIsNotNone(player_data)
            assert player_data is not None
            self.assertFalse(player_data.paused)
            self.assertFalse(player_data.withdrawn)
            self.assertFalse(player_data.free)

    async def test_arena_standings_do_not_mark_ongoing_games_with_star(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))

        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        self.assertEqual(len(games), 1)

        players_json = self.tournament.players_json()
        self.assertTrue(
            all(
                not any(
                    isinstance(point, tuple) and len(point) > 0 and point[0] == "*"
                    for point in row["points"]
                )
                for row in players_json["players"]
            )
        )

    async def test_fixed_round_standings_render_absent_as_dash(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=0, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1

        absent = list(self.tournament.players.keys())[0]
        await self.tournament.pause(absent)

        waiting_players = list(self.tournament.waiting_players())
        await self.tournament.create_new_pairings(waiting_players)

        players_json = self.tournament.players_json()
        absent_row = next(row for row in players_json["players"] if row["name"] == absent.username)
        self.assertEqual(absent_row["points"][-1], "-")

        absent_data = self.tournament.players[absent]
        self.assertEqual(absent_data.points[-1], (0, 0))

    async def test_tournament_rating_update_on_rejoin(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=1, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(1)

        player = list(self.tournament.players.keys())[0]
        initial_rating = self.tournament.players[player].rating

        await self.tournament.withdraw(player)

        # Simulate rating change
        new_rating = initial_rating + 100
        player.perfs["chess"] = new_default_perf()
        player.perfs["chess"]["gl"]["r"] = new_rating

        await self.tournament.join(player)

        self.assertEqual(self.tournament.players[player].rating, new_rating)

    async def test_tournament_sorting_before_start(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=1, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament

        await self.tournament.join_players(3)

        players_json = self.tournament.players_json()
        leaderboard_ratings = [p["rating"] for p in players_json["players"]]

        self.assertEqual(leaderboard_ratings, sorted(leaderboard_ratings, reverse=True))

        # Add a new player with a higher rating
        await self.tournament.join_players(1, rating=2000)

        players_json = self.tournament.players_json()
        leaderboard_ratings = [p["rating"] for p in players_json["players"]]
        self.assertEqual(leaderboard_ratings, sorted(leaderboard_ratings, reverse=True))

    async def test_withdraw_after_start_pauses(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        player = list(self.tournament.players.keys())[0]
        await self.tournament.start(datetime.now(UTC))

        await self.tournament.withdraw(player)

        player_data = self.tournament.players[player]
        self.assertTrue(player_data.paused)
        self.assertFalse(player_data.withdrawn)
        self.assertEqual(self.tournament.nb_players, 2)
        self.assertIn(player, self.tournament.leaderboard)

        doc = await app_state.db.tournament_player.find_one({"_id": player_data.id})
        self.assertTrue(doc["a"])
        self.assertFalse(doc.get("wd", False))

    async def test_tournament_handles_replaced_user_instance(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await self.tournament.join_players(1)

        original_player = list(self.tournament.players.keys())[0]
        username = original_player.username

        replacement = User(
            app_state,
            username=username,
            title=original_player.title,
            perfs=original_player.perfs,
        )
        app_state.users[username] = replacement
        replacement.tournament_sockets[tid] = {None}
        app_state.tourneysockets[tid][username] = replacement.tournament_sockets[tid]

        self.assertEqual(len(self.tournament.waiting_players()), 1)

        games = await self.tournament.games_json(username)
        self.assertEqual(games["name"], username)
        self.assertEqual(games["rank"], 1)

    async def test_update_players_handles_replaced_user_instance(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(2)

        white = list(self.tournament.players.keys())[0]
        black = list(self.tournament.players.keys())[1]

        replacement_black = User(
            app_state,
            username=black.username,
            title=black.title,
            perfs=black.perfs,
        )
        app_state.users[black.username] = replacement_black

        game = GameData(
            "syntheticGame",
            white.username,
            str(self.tournament.players[white].rating),
            replacement_black.username,
            str(self.tournament.players[black].rating),
            "1-0",
            datetime.now(UTC),
            False,
            False,
            wtitle=white.title,
            btitle=replacement_black.title,
        )
        self.tournament.update_players(game)

        black_data = self.tournament.player_data_by_name(black.username)
        self.assertIsNotNone(black_data)
        assert black_data is not None
        self.assertEqual(len(self.tournament.players[white].games), 1)
        self.assertEqual(len(black_data.games), 1)
        self.assertEqual(game.bplayer.username, black.username)

    async def test_player_name_index_rebuilds_from_user_key_map(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(1)

        original_player = list(self.tournament.players.keys())[0]
        original_data = self.tournament.players[original_player]
        username = original_player.username

        self.tournament.players_by_name.clear()
        self.tournament.player_keys_by_name.clear()

        rebuilt_player = self.tournament.get_player_by_name(username)
        self.assertIs(rebuilt_player, original_player)
        self.assertIs(self.tournament.player_data_by_name(username), original_data)

    async def test_gamedata_with_username_only_values(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(2)

        white = list(self.tournament.players.keys())[0]
        black = list(self.tournament.players.keys())[1]

        game = GameData(
            "syntheticGameByName",
            white.username,
            str(self.tournament.players[white].rating),
            black.username,
            str(self.tournament.players[black].rating),
            "1-0",
            datetime.now(UTC),
            False,
            False,
            wtitle=white.title,
            btitle=black.title,
        )
        self.tournament.update_players(game)

        self.assertEqual(game.wplayer.username, white.username)
        self.assertEqual(game.bplayer.username, black.username)

        black_view = game.game_json(black)
        self.assertEqual(black_view["color"], "b")
        self.assertEqual(black_view["name"], white.username)
        self.assertEqual(black_view["title"], white.title)

    async def test_players_json_and_waiting_players_tolerate_stale_player_key(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(1)

        player = list(self.tournament.players.keys())[0]
        player_data = self.tournament.players.pop(player)
        self.tournament.players_by_name[player.username] = player_data
        self.tournament.player_keys_by_name.pop(player.username, None)

        waiting = self.tournament.waiting_players()
        self.assertEqual(len(waiting), 1)
        self.assertEqual(waiting[0].username, player.username)

        page = self.tournament.players_json()
        self.assertEqual(len(page["players"]), 1)
        self.assertEqual(page["players"][0]["name"], player.username)

    async def test_get_player_by_name_recovers_from_players_key_drift(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(2)

        white = list(self.tournament.players.keys())[0]
        black = list(self.tournament.players.keys())[1]
        black_data = self.tournament.players.pop(black)
        self.tournament.players_by_name[black.username] = black_data
        self.tournament.player_keys_by_name.pop(black.username, None)

        game = GameData(
            "syntheticRecoveredByName",
            white.username,
            str(self.tournament.players[white].rating),
            black.username,
            str(black_data.rating),
            "1-0",
            datetime.now(UTC),
            False,
            False,
        )
        self.tournament.update_players(game)

        recovered_black = self.tournament.get_player_by_name(black.username)
        self.assertIsNotNone(recovered_black)
        assert recovered_black is not None
        self.assertIn(recovered_black, self.tournament.players)
        self.assertEqual(len(self.tournament.players[recovered_black].games), 1)
        self.assertEqual(game.bplayer.username, black.username)

    async def test_join_with_replaced_user_does_not_duplicate_leaderboard_entry(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=10, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(1)

        original = list(self.tournament.players.keys())[0]
        username = original.username
        player_data = self.tournament.players.pop(original)
        self.tournament.players_by_name[username] = player_data
        self.tournament.player_keys_by_name.pop(username, None)

        replacement = User(
            app_state,
            username=username,
            title=original.title,
            perfs=original.perfs,
        )
        app_state.users[username] = replacement
        new_rating = int(player_data.rating) + 25
        replacement.perfs["chess960"] = new_default_perf()
        replacement.perfs["chess960"]["gl"]["r"] = new_rating

        await self.tournament.join(replacement)

        leaderboard_entries = [p for p in self.tournament.leaderboard if p.username == username]
        self.assertEqual(len(leaderboard_entries), 1)
        self.assertEqual(self.tournament.nb_players, 1)
        updated = self.tournament.player_data_by_name(username)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.rating, new_rating)

    async def test_get_player_by_name_recovers_without_user_cache_entry(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await self.tournament.join_players(1)

        player = list(self.tournament.players.keys())[0]
        username = player.username
        player_data = self.tournament.players.pop(player)
        self.tournament.players_by_name[username] = player_data
        self.tournament.player_keys_by_name.pop(username, None)
        app_state.users.data.pop(username, None)

        recovered_player = self.tournament.get_player_by_name(username)
        self.assertIsNotNone(recovered_player)
        assert recovered_player is not None
        self.assertEqual(recovered_player.username, username)
        self.assertIn(recovered_player, self.tournament.players)
        self.assertIs(self.tournament.players[recovered_player], player_data)

    async def test_game_update_handles_stale_user_key_without_user_cache_entry(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess960", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))

        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]

        stale_player = game.bplayer
        stale_data = self.tournament.players.pop(stale_player)
        self.tournament.players_by_name[stale_player.username] = stale_data
        self.tournament.player_keys_by_name.pop(stale_player.username, None)
        app_state.users.data.pop(stale_player.username, None)

        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20

        await self.tournament.game_update(game)

        repaired_data = self.tournament.player_data_by_name(stale_player.username)
        self.assertIsNotNone(repaired_data)
        assert repaired_data is not None
        self.assertEqual(len(repaired_data.points), 1)
        self.assertEqual(self.tournament.nb_games_finished, 1)

        stale_doc = await app_state.db.tournament_player.find_one(
            {"tid": tid, "uid": stale_player.username}
        )
        self.assertIsNotNone(stale_doc)
        assert stale_doc is not None
        self.assertEqual(len(stale_doc["p"]), 1)

    async def test_rr_aborted_arrangement_game_reopens_pairing(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=0, rounds=1, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        players = []
        for suffix in ("A", "B"):
            user = User(app_state, username=f"rr_abort_{suffix}", perfs=make_test_perfs())
            app_state.users[user.username] = user
            await self.tournament.join(user)
            players.append(user)

        await self.tournament.start(datetime.now(UTC))
        arrangement = next(iter(self.tournament.arrangements.values()))

        seek_error = await self.tournament.create_arrangement_challenge(players[0], arrangement.id)
        self.assertIsNone(seek_error)
        accept_result = await self.tournament.accept_arrangement_challenge(
            players[1], arrangement.id
        )
        self.assertEqual(accept_result["type"], "new_game")

        game = app_state.games[accept_result["gameId"]]
        self.assertEqual(arrangement.status, ARR_STATUS_STARTED)
        self.assertEqual(arrangement.game_id, game.id)

        await game.game_ended(game.wplayer, "abort")

        self.assertEqual(arrangement.status, ARR_STATUS_PENDING)
        self.assertIsNone(arrangement.game_id)
        self.assertIsNone(arrangement.invite_id)
        self.assertIsNone(arrangement.challenger)
        self.assertIsNone(arrangement.scheduled_at)
        self.assertNotIn(game, self.tournament.ongoing_games)

    async def test_rr_annul_finished_game_reopens_pairing_and_reverses_score(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=0, rounds=0, rr_max_players=4, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        game = await self.tournament.start_arrangement_game(arrangement.id)
        game.board.ply = 20
        await game.game_ended(game.bplayer, "resign")

        self.assertEqual(arrangement.status, ARR_STATUS_FINISHED)
        self.assertEqual(arrangement.game_id, game.id)
        self.assertEqual(self.tournament.nb_games_finished, 1)
        self.assertEqual(
            self.tournament.leaderboard_score_by_username(game.wplayer.username) // SCORE_SHIFT,
            2,
        )

        error = await self.tournament.annul_arrangement_game(arrangement.id, game.id)
        self.assertIsNone(error)
        self.assertEqual(arrangement.status, ARR_STATUS_PENDING)
        self.assertIsNone(arrangement.game_id)
        self.assertEqual(arrangement.previous_game_ids, [game.id])
        self.assertEqual(self.tournament.nb_games_finished, 0)
        for username in arrangement.players():
            player_data = self.tournament.player_data_by_name(username)
            assert player_data is not None
            self.assertEqual(player_data.games, [])
            self.assertEqual(player_data.points, [])
            self.assertEqual(self.tournament.leaderboard_score_by_username(username), 0)

        pairing_doc = await app_state.db.tournament_pairing.find_one({"_id": game.id})
        self.assertIsNotNone(pairing_doc)
        assert pairing_doc is not None
        self.assertTrue(pairing_doc.get("an"))
        arrangement_doc = await app_state.db.tournament_arrangement.find_one(
            {"_id": arrangement.id}
        )
        self.assertIsNotNone(arrangement_doc)
        assert arrangement_doc is not None
        self.assertEqual(arrangement_doc.get("pg"), [game.id])
        self.assertIsNone(arrangement_doc.get("gid"))

        payload_cell = self.tournament.arrangement_payload()["matrix"][arrangement.white][
            arrangement.black
        ]
        self.assertEqual(payload_cell["previousGameIds"], [game.id])

        replay = await self.tournament.start_arrangement_game(arrangement.id)
        self.assertNotEqual(replay.id, game.id)
        self.assertEqual(arrangement.previous_game_ids, [game.id])

        repeat_error = await self.tournament.annul_arrangement_game(arrangement.id, game.id)
        self.assertEqual(repeat_error, "This game is no longer the current round-robin result.")
        self.assertEqual(self.tournament.nb_games_finished, 0)

        replay.board.ply = 20
        await replay.game_ended(replay.bplayer, "resign")
        self.assertEqual(self.tournament.nb_games_finished, 1)
        self.assertIsNone(await self.tournament.annul_arrangement_game(arrangement.id, replay.id))
        self.assertEqual(arrangement.previous_game_ids, [replay.id, game.id])
        self.assertEqual(self.tournament.nb_games_finished, 0)

    async def test_rr_aborted_arrangement_after_deadline_expires_and_finishes(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=0, rounds=0, rr_max_players=4, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))

        finished_arrangement = self.tournament.arrangement_list()[0]
        finished_game = await self.tournament.start_arrangement_game(finished_arrangement.id)
        finished_game.board.ply = 20
        await finished_game.game_ended(finished_game.bplayer, "resign")
        self.assertEqual(self.tournament.nb_games_finished, 1)
        self.assertEqual(finished_arrangement.status, ARR_STATUS_FINISHED)

        finished_names = set(finished_arrangement.players())
        arrangement = next(
            candidate
            for candidate in self.tournament.arrangement_list()
            if finished_names.isdisjoint(candidate.players())
        )
        game = await self.tournament.start_arrangement_game(arrangement.id)

        self.tournament.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        self.assertTrue(self.tournament.deadline_reached())
        self.assertIn(game, self.tournament.ongoing_games)

        await game.game_ended(game.wplayer, "abort")

        self.assertEqual(self.tournament.status, T_FINISHED)
        self.assertEqual(arrangement.status, ARR_STATUS_EXPIRED)
        self.assertIsNone(arrangement.game_id)
        self.assertNotIn(game, self.tournament.ongoing_games)
        self.assertEqual(self.tournament.nb_games_finished, 1)
        self.assertEqual(
            self.tournament.leaderboard_score_by_username(game.wplayer.username) // SCORE_SHIFT,
            0,
        )
        self.assertEqual(
            self.tournament.leaderboard_score_by_username(game.bplayer.username) // SCORE_SHIFT,
            0,
        )

        arrangement_doc = await app_state.db.tournament_arrangement.find_one(
            {"_id": arrangement.id}
        )
        self.assertIsNotNone(arrangement_doc)
        assert arrangement_doc is not None
        self.assertEqual(arrangement_doc["s"], ARR_STATUS_EXPIRED)
        tournament_doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(tournament_doc)
        assert tournament_doc is not None
        self.assertEqual(tournament_doc["status"], T_FINISHED)
