import asyncio
import gc
from datetime import UTC, datetime, timedelta
from time import monotonic
from unittest.mock import AsyncMock, patch

from aiohttp import web
from const import BYEGAME, FLAG, RATED, SHIELD, T_FINISHED, T_STARTED, TEST_PREFIX
from fairy.cwda import CWDA_START_FENS
from glicko2.glicko2 import new_default_perf_map
from newid import id8
from pychess_global_app_state import (
    TOURNAMENT_KEEP_TIME,
    recover_pending_tournament_game_side_effects,
)
from pychess_global_app_state_utils import get_app_state
from rated_start import CHESS_NO_CASTLE_FEN
from team import PERMISSION_TOURNAMENTS
from tournament.arena import ArenaTournament
from tournament.auto_play_tournament import (
    ArenaTestTournament,
    RRTestTournament,
    SwissTestTournament,
)
from tournament.rr import (
    ARR_STATUS_CHALLENGED,
    ARR_STATUS_FINISHED,
    ARR_STATUS_PENDING,
    ARR_STATUS_STARTED,
    RRTournament,
)
from tournament.tournament import (
    SCORE_SHIFT,
    SWISS_FINISH_REASON_NO_LEGAL_PAIRING,
    ByeGame,
    GameData,
    PairingUnavailable,
    PlayerData,
    Tournament,
    upsert_tournament_to_db,
)
from tournament.tournaments import (
    create_or_update_tournament,
    creator_can_manage_tournament,
    get_latest_tournaments,
    load_tournament,
)
from tournament_test_base import TournamentTestCase
from user import User
from variants import (
    VARIANTS,
    register_catalogued_server_variant,
    unregister_catalogued_server_variant,
)


def make_test_perfs():
    return new_default_perf_map(VARIANTS)


class TournamentPersistenceTestCase(TournamentTestCase):
    SHORT_SWISS_MINUTES = 0.08

    @staticmethod
    def _community_arena_form(**overrides: str) -> dict[str, str]:
        form = {
            "variant": "chess",
            "rated": "1",
            "clockTime": "3.0",
            "clockIncrement": "2",
            "byoyomiPeriod": "0",
            "system": str(ArenaTournament.system),
            "rounds": "0",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": "",
            "endDate": "",
            "description": "",
            "password": "",
            "position": "",
            "waitMinutes": "5",
            "minutes": "45",
            "name": "Community Arena",
        }
        form.update(overrides)
        return form

    @staticmethod
    def _fixed_round_form(system: str = "2", **overrides: str) -> dict[str, str]:
        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": "5",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "system": system,
            "rounds": "5",
            "rrMaxPlayers": "10",
            "rrRequiresApproval": "",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": "",
            "endDate": "",
            "name": "Team Tournament",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }
        form.update(overrides)
        return form

    async def test_catalogued_tournament_persists_variant_snapshot(self):
        app_state = get_app_state(self.app)
        name = f"tournament_snapshot_{id8().lower()}"
        ini = f"[{name}:chess]\n"
        register_catalogued_server_variant(name, "Tournament snapshot")
        self.addCleanup(unregister_catalogued_server_variant, name)
        app_state.catalogued_variants[name] = {
            "_id": name,
            "name": name,
            "displayName": "Tournament snapshot",
            "author": "author",
            "ini": ini,
            "visibility": "public",
            "enabled": True,
            "archived": False,
        }

        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            "author",
            self._community_arena_form(variant=name, rated="0"),
        )
        tid = (set(app_state.tournaments) - before_ids).pop()
        doc = await app_state.db.tournament.find_one({"_id": tid})

        self.assertEqual(doc["v"], name)
        self.assertEqual(doc["vini"], ini)
        self.assertEqual(doc["vd"], "Tournament snapshot")
        self.assertEqual(doc["vby"], "author")

    async def test_latest_tournaments_skips_legacy_deleted_variant_orphan(self):
        app_state = get_app_state(self.app)
        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            "PyChess",
            self._community_arena_form(),
        )
        tid = (set(app_state.tournaments) - before_ids).pop()
        await app_state.db.tournament.update_one(
            {"_id": tid},
            {"$set": {"v": "deleted_catalogued_variant"}, "$unset": {"vini": ""}},
        )
        tournament = app_state.tournaments.pop(tid)
        if tournament.clock_task is not None:
            tournament.clock_task.cancel()

        started, scheduled, completed = await get_latest_tournaments(app_state, "en")

        self.assertNotIn(tid, {t.id for t in started + scheduled + completed})

    async def test_legacy_archived_catalogued_tournament_uses_catalogue_fallback(self):
        app_state = get_app_state(self.app)
        name = f"tournament_archive_{id8().lower()}"
        ini = f"[{name}:chess]\n"
        register_catalogued_server_variant(name, "Tournament archive")
        self.addCleanup(unregister_catalogued_server_variant, name)
        app_state.catalogued_variants[name] = {
            "_id": name,
            "name": name,
            "displayName": "Tournament archive",
            "author": "author",
            "ini": ini,
            "visibility": "public",
            "enabled": True,
            "archived": False,
        }

        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            "author",
            self._community_arena_form(variant=name, rated="0"),
        )
        tid = (set(app_state.tournaments) - before_ids).pop()
        await app_state.db.tournament.update_one(
            {"_id": tid},
            {"$set": {"status": T_FINISHED}, "$unset": {"vini": "", "vd": "", "vby": ""}},
        )
        await app_state.db.catalogued_variant.insert_one(
            {
                "_id": name,
                "name": name,
                "displayName": "Tournament archive",
                "author": "author",
                "ini": ini,
                "visibility": "public",
                "enabled": False,
                "archived": True,
            }
        )
        tournament = app_state.tournaments.pop(tid)
        if tournament.clock_task is not None:
            tournament.clock_task.cancel()
        app_state.catalogued_variants.pop(name, None)
        unregister_catalogued_server_variant(name)

        started, scheduled, completed = await get_latest_tournaments(app_state, "en")

        self.assertIn(tid, {t.id for t in started + scheduled + completed})
        self.assertNotIn(name, app_state.catalogued_variants)

    async def test_finished_catalogued_tournament_restores_from_inline_snapshot(self):
        app_state = get_app_state(self.app)
        name = f"tournament_restore_{id8().lower()}"
        ini = f"[{name}:chess]\n"
        register_catalogued_server_variant(name, "Tournament restore")
        self.addCleanup(unregister_catalogued_server_variant, name)
        app_state.catalogued_variants[name] = {
            "_id": name,
            "name": name,
            "displayName": "Tournament restore",
            "author": "author",
            "ini": ini,
            "visibility": "public",
            "enabled": True,
            "archived": False,
        }

        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            "author",
            self._community_arena_form(variant=name, rated="0"),
        )
        tid = (set(app_state.tournaments) - before_ids).pop()
        await app_state.db.tournament.update_one({"_id": tid}, {"$set": {"status": T_FINISHED}})
        tournament = app_state.tournaments.pop(tid)
        if tournament.clock_task is not None:
            tournament.clock_task.cancel()
        app_state.catalogued_variants.pop(name, None)
        unregister_catalogued_server_variant(name)

        restored = await load_tournament(app_state, tid)

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.variant, name)
        self.assertNotIn(name, app_state.catalogued_variants)

    async def test_regular_user_can_create_only_one_arena_per_24_hours(self):
        app_state = get_app_state(self.app)
        username = f"CommunityArena{id8()}"
        await app_state.db.user.insert_one({"_id": username})

        before_ids = set(app_state.tournaments)
        discord_send = AsyncMock()
        with patch.object(app_state.discord, "send_to_discord", new=discord_send):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(),
                creator_is_director=False,
            )
        discord_send.assert_not_awaited()
        new_ids = set(app_state.tournaments) - before_ids
        self.assertEqual(len(new_ids), 1)
        tournament = app_state.tournaments[new_ids.pop()]
        self.assertEqual(tournament.system, ArenaTournament.system)

        await create_or_update_tournament(
            app_state,
            username,
            self._community_arena_form(name="Edited Community Arena"),
            tournament,
            creator_is_director=False,
        )
        self.assertEqual(tournament.name, "Edited Community Arena")

        await tournament.abort()
        with self.assertRaises(web.HTTPTooManyRequests):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(name="Second Arena"),
                creator_is_director=False,
            )

        user_doc = await app_state.db.user.find_one({"_id": username})
        history = list((user_doc or {}).get("arenaCreationHistory", []))
        self.assertEqual(len(history), 1)
        history[0]["at"] = datetime.now(UTC) - timedelta(hours=25)
        await app_state.db.user.update_one(
            {"_id": username},
            {"$set": {"arenaCreationHistory": history}},
        )
        await create_or_update_tournament(
            app_state,
            username,
            self._community_arena_form(name="Next Day Arena"),
            creator_is_director=False,
        )

    async def test_community_arena_quota_constant_controls_rolling_24h_limit(self):
        app_state = get_app_state(self.app)
        username = f"CommunityQuota{id8()}"
        await app_state.db.user.insert_one({"_id": username})

        with patch("tournament.tournaments.COMMUNITY_ARENA_MAX_CREATIONS_PER_24H", 2):
            for number in (1, 2):
                before_ids = set(app_state.tournaments)
                await create_or_update_tournament(
                    app_state,
                    username,
                    self._community_arena_form(name=f"Quota Arena {number}"),
                    creator_is_director=False,
                )
                tournament_id = (set(app_state.tournaments) - before_ids).pop()
                await app_state.tournaments[tournament_id].abort()

            with self.assertRaises(web.HTTPTooManyRequests):
                await create_or_update_tournament(
                    app_state,
                    username,
                    self._community_arena_form(name="Quota Arena 3"),
                    creator_is_director=False,
                )

            user_doc = await app_state.db.user.find_one({"_id": username})
            history = list((user_doc or {}).get("arenaCreationHistory", []))
            self.assertEqual(len(history), 2)

            history[0]["at"] = datetime.now(UTC) - timedelta(hours=25)
            await app_state.db.user.update_one(
                {"_id": username},
                {"$set": {"arenaCreationHistory": history}},
            )
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(name="Quota Arena 3"),
                creator_is_director=False,
            )

            user_doc = await app_state.db.user.find_one({"_id": username})
            history = list((user_doc or {}).get("arenaCreationHistory", []))
            self.assertEqual(len(history), 2)
            self.assertGreater(history[0]["at"], datetime.now(UTC) - timedelta(hours=24))

    async def test_community_arena_quota_migrates_legacy_timestamp(self):
        app_state = get_app_state(self.app)
        username = f"CommunityLegacyQuota{id8()}"
        await app_state.db.user.insert_one(
            {"_id": username, "lastArenaCreatedAt": datetime.now(UTC) - timedelta(hours=1)}
        )

        with self.assertRaises(web.HTTPTooManyRequests):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(name="Blocked Legacy Arena"),
                creator_is_director=False,
            )

        await app_state.db.user.update_one(
            {"_id": username},
            {"$set": {"lastArenaCreatedAt": datetime.now(UTC) - timedelta(hours=25)}},
        )
        await create_or_update_tournament(
            app_state,
            username,
            self._community_arena_form(name="Migrated Legacy Arena"),
            creator_is_director=False,
        )

        user_doc = await app_state.db.user.find_one({"_id": username})
        self.assertNotIn("lastArenaCreatedAt", user_doc or {})
        history = list((user_doc or {}).get("arenaCreationHistory", []))
        self.assertEqual(len(history), 1)

        raised_username = f"CommunityLegacyRaisedQuota{id8()}"
        legacy_created_at = datetime.now(UTC) - timedelta(hours=1)
        await app_state.db.user.insert_one(
            {"_id": raised_username, "lastArenaCreatedAt": legacy_created_at}
        )
        with patch("tournament.tournaments.COMMUNITY_ARENA_MAX_CREATIONS_PER_24H", 2):
            before_ids = set(app_state.tournaments)
            await create_or_update_tournament(
                app_state,
                raised_username,
                self._community_arena_form(name="Legacy Second Slot Arena"),
                creator_is_director=False,
            )
            tournament_id = (set(app_state.tournaments) - before_ids).pop()
            await app_state.tournaments[tournament_id].abort()

            with self.assertRaises(web.HTTPTooManyRequests):
                await create_or_update_tournament(
                    app_state,
                    raised_username,
                    self._community_arena_form(name="Legacy Third Slot Arena"),
                    creator_is_director=False,
                )

            raised_doc = await app_state.db.user.find_one({"_id": raised_username})
            raised_history = list((raised_doc or {}).get("arenaCreationHistory", []))
            self.assertEqual(len(raised_history), 2)
            self.assertLess(
                abs((raised_history[0]["at"] - legacy_created_at).total_seconds()),
                0.001,
            )
            self.assertNotIn("lastArenaCreatedAt", raised_doc or {})

    async def test_community_arena_failed_creation_releases_quota_claim(self):
        app_state = get_app_state(self.app)
        username = f"CommunityQuotaRollback{id8()}"
        await app_state.db.user.insert_one({"_id": username})

        with (
            patch(
                "tournament.tournaments.new_tournament",
                new=AsyncMock(side_effect=RuntimeError("simulated creation failure")),
            ),
            self.assertRaisesRegex(RuntimeError, "simulated creation failure"),
        ):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(name="Failed Quota Arena"),
                creator_is_director=False,
            )

        user_doc = await app_state.db.user.find_one({"_id": username})
        self.assertEqual((user_doc or {}).get("arenaCreationHistory"), [])

        await create_or_update_tournament(
            app_state,
            username,
            self._community_arena_form(name="Successful Quota Arena"),
            creator_is_director=False,
        )

    async def test_regular_user_arena_limits_and_system_conflict(self):
        app_state = get_app_state(self.app)
        username = f"CommunityLimits{id8()}"
        await app_state.db.user.insert_one({"_id": username})

        with self.assertRaises(web.HTTPBadRequest):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(system="1"),
                creator_is_director=False,
            )

        with self.assertRaises(web.HTTPBadRequest):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(minutes="150"),
                creator_is_director=False,
            )

        with self.assertRaises(web.HTTPBadRequest):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(variant="bughouse"),
                creator_is_director=False,
            )

        too_late = datetime.now(UTC) + timedelta(hours=25)
        with self.assertRaises(web.HTTPBadRequest):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(startDate=too_late.isoformat()),
                creator_is_director=False,
            )

        protected_start = datetime.now(UTC) + timedelta(minutes=30)
        protected = ArenaTournament(
            app_state,
            id8(),
            name="Weekly Chess Arena",
            created_by="PyChess",
            frequency=SHIELD,
            starts_at=protected_start,
            minutes=90,
            with_clock=False,
        )
        app_state.tournaments[protected.id] = protected

        conflict_start = protected_start - timedelta(minutes=20)
        with self.assertRaises(web.HTTPBadRequest):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(startDate=conflict_start.isoformat()),
                creator_is_director=False,
            )

        user_doc = await app_state.db.user.find_one({"_id": username})
        self.assertIsNotNone(user_doc)
        self.assertNotIn("lastArenaCreatedAt", user_doc or {})
        self.assertNotIn("arenaCreationHistory", user_doc or {})

    async def test_regular_user_cannot_create_byoyomi_arena_for_unsupported_variant(self):
        app_state = get_app_state(self.app)
        username = f"CommunityByoyomi{id8()}"
        await app_state.db.user.insert_one({"_id": username})

        with self.assertRaises(web.HTTPBadRequest) as context:
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(variant="racingkings", byoyomiPeriod="3"),
                creator_is_director=False,
            )
        self.assertEqual(
            context.exception.text, "Byoyomi is not supported for this tournament variant."
        )

    async def test_regular_user_cannot_stack_active_arenas(self):
        app_state = get_app_state(self.app)
        username = f"CommunityActive{id8()}"
        await app_state.db.user.insert_one({"_id": username})

        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            username,
            self._community_arena_form(),
            creator_is_director=False,
        )
        tournament_id = (set(app_state.tournaments) - before_ids).pop()

        user_doc = await app_state.db.user.find_one({"_id": username})
        history = list((user_doc or {}).get("arenaCreationHistory", []))
        self.assertEqual(len(history), 1)
        history[0]["at"] = datetime.now(UTC) - timedelta(hours=25)
        await app_state.db.user.update_one(
            {"_id": username},
            {"$set": {"arenaCreationHistory": history}},
        )
        with self.assertRaises(web.HTTPTooManyRequests):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(name="Overlapping Arena"),
                creator_is_director=False,
            )

        await app_state.tournaments[tournament_id].abort()

    async def test_only_curated_custom_start_tournaments_can_be_rated(self):
        app_state = get_app_state(self.app)
        base_form = {
            "variant": "chess",
            "rated": "1",
            "clockTime": "5",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "shield": "",
            "system": str(ArenaTournament.system),
            "rounds": "0",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": "",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }
        cases = (
            ("Curated start", "chess", CHESS_NO_CASTLE_FEN, True, {}),
            (
                "Unsafe start",
                "chess",
                "RNBKQBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbkqbnr w - - 0 1",
                False,
                {},
            ),
            (
                "Casual-only variant",
                "cwda",
                next(iter(CWDA_START_FENS)),
                False,
                {
                    "entryMinRating": "1200",
                    "entryMaxRating": "2200",
                    "entryMinRatedGames": "20",
                },
            ),
        )

        for name, variant, position, expected_rated, overrides in cases:
            with self.subTest(name=name):
                before_ids = set(app_state.tournaments)
                await create_or_update_tournament(
                    app_state,
                    "tester",
                    {
                        **base_form,
                        **overrides,
                        "name": name,
                        "variant": variant,
                        "position": position,
                    },
                )

                new_ids = set(app_state.tournaments) - before_ids
                self.assertEqual(len(new_ids), 1)
                tournament = app_state.tournaments[new_ids.pop()]
                self.assertEqual(bool(tournament.rated), expected_rated)
                if variant == "cwda":
                    self.assertEqual(tournament.entry_min_rating, 0)
                    self.assertEqual(tournament.entry_max_rating, 0)
                    self.assertEqual(tournament.entry_min_rated_games, 0)

    async def test_arena_entry_conditions_persisted_from_form(self):
        app_state = get_app_state(self.app)
        before_ids = set(app_state.tournaments)
        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": "5",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "shield": "",
            "system": str(ArenaTournament.system),
            "rounds": "0",
            "roundInterval": "auto",
            "entryMinRating": "1500",
            "entryMaxRating": "2100",
            "entryMinRatedGames": "30",
            "entryMinAccountAgeDays": "14",
            "forbiddenPairings": "alice bob",
            "manualPairings": "carol dave",
            "startDate": "",
            "name": "Arena Conditions",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }

        await create_or_update_tournament(app_state, "tester", form)

        new_ids = set(app_state.tournaments) - before_ids
        self.assertEqual(len(new_ids), 1)
        tournament = app_state.tournaments[new_ids.pop()]
        self.assertEqual(tournament.system, ArenaTournament.system)
        self.assertEqual(tournament.entry_min_rating, 1500)
        self.assertEqual(tournament.entry_max_rating, 2100)
        self.assertEqual(tournament.entry_min_rated_games, 30)
        self.assertEqual(tournament.entry_min_account_age_days, 14)
        self.assertFalse(tournament.entry_titled_only)
        self.assertEqual(tournament.forbidden_pairings, "")
        self.assertEqual(tournament.manual_pairings, "")

        doc = await app_state.db.tournament.find_one({"_id": tournament.id})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("entryMinRating"), 1500)
        self.assertEqual(doc.get("entryMaxRating"), 2100)
        self.assertEqual(doc.get("entryMinRatedGames"), 30)
        self.assertEqual(doc.get("entryMinAccountAgeDays"), 14)
        self.assertIsNone(doc.get("entryTitledOnly"))
        self.assertEqual(doc.get("forbiddenPairings"), "")
        self.assertEqual(doc.get("manualPairings"), "")

    async def test_production_requires_team_for_fixed_round_creation(self):
        app_state = get_app_state(self.app)

        with patch("tournament.tournaments.DEV", False):
            for system in ("1", "2"):
                with self.assertRaises(web.HTTPBadRequest):
                    await create_or_update_tournament(
                        app_state, "tester", self._fixed_round_form(system)
                    )

    async def test_team_tournament_permission_unlocks_all_pairing_systems(self):
        app_state = get_app_state(self.app)
        username = f"TeamTournament{id8()}"
        team_id = f"team-{id8()}"
        now = datetime.now(UTC)
        await app_state.db.user.insert_one({"_id": username})
        await app_state.db.team.insert_one(
            {
                "_id": team_id,
                "name": "Tournament Team",
                "enabled": True,
                "memberCount": 1,
                "createdBy": username,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        await app_state.db.team_member.insert_one(
            {
                "_id": f"{username}@{team_id}",
                "team": team_id,
                "user": username,
                "joinedAt": now,
                "permissions": [PERMISSION_TOURNAMENTS],
            }
        )

        with patch("tournament.tournaments.DEV", False):
            for system in ("0", "1", "2"):
                before_ids = set(app_state.tournaments)
                form = (
                    self._community_arena_form(
                        teamId=team_id,
                        name=f"Team Tournament {system}",
                    )
                    if system == "0"
                    else self._fixed_round_form(
                        system,
                        teamId=team_id,
                        name=f"Team Tournament {system}",
                    )
                )
                await create_or_update_tournament(
                    app_state,
                    username,
                    form,
                    creator_is_director=False,
                )
                tournament_id = (set(app_state.tournaments) - before_ids).pop()
                tournament = app_state.tournaments[tournament_id]
                self.assertEqual(team_id, tournament.team_id)
                doc = await app_state.db.tournament.find_one({"_id": tournament_id})
                self.assertIsNotNone(doc)
                assert doc is not None
                self.assertEqual(team_id, doc.get("teamId"))
                await tournament.abort()

    async def test_team_tournament_creation_rejects_missing_tournament_permission(self):
        app_state = get_app_state(self.app)
        team_id = f"team-{id8()}"
        now = datetime.now(UTC)
        await app_state.db.team.insert_one(
            {
                "_id": team_id,
                "name": "Member Only Team",
                "enabled": True,
                "memberCount": 1,
                "createdBy": "someone-else",
                "createdAt": now,
                "updatedAt": now,
            }
        )
        await app_state.db.team_member.insert_one(
            {
                "_id": f"tester@{team_id}",
                "team": team_id,
                "user": "tester",
                "joinedAt": now,
                "permissions": [],
            }
        )

        with patch("tournament.tournaments.DEV", False):
            for system in ("0", "1", "2"):
                form = (
                    self._community_arena_form(teamId=team_id)
                    if system == "0"
                    else self._fixed_round_form(system, teamId=team_id)
                )
                with self.assertRaises(web.HTTPForbidden):
                    await create_or_update_tournament(
                        app_state,
                        "tester",
                        form,
                        creator_is_director=False,
                    )

    async def test_team_tournament_creator_loses_management_when_permission_is_removed(self):
        app_state = get_app_state(self.app)
        username = f"TeamOrganizer{id8()}"
        team_id = f"team-{id8()}"
        now = datetime.now(UTC)
        await app_state.db.user.insert_one({"_id": username})
        await app_state.db.team.insert_one(
            {
                "_id": team_id,
                "name": "Organizer Lifecycle Team",
                "enabled": True,
                "memberCount": 1,
                "createdBy": "team-owner",
                "createdAt": now,
                "updatedAt": now,
            }
        )
        member_id = f"{username}@{team_id}"
        await app_state.db.team_member.insert_one(
            {
                "_id": member_id,
                "team": team_id,
                "user": username,
                "joinedAt": now,
                "permissions": [PERMISSION_TOURNAMENTS],
            }
        )

        before_ids = set(app_state.tournaments)
        form = self._fixed_round_form("2", teamId=team_id, name="Organizer Swiss")
        await create_or_update_tournament(
            app_state,
            username,
            form,
            creator_is_director=False,
        )
        tournament_id = (set(app_state.tournaments) - before_ids).pop()
        tournament = app_state.tournaments[tournament_id]
        self.assertTrue(await creator_can_manage_tournament(app_state, tournament, username))

        await app_state.db.team_member.update_one(
            {"_id": member_id},
            {"$set": {"permissions": []}},
        )
        self.assertFalse(await creator_can_manage_tournament(app_state, tournament, username))

        for creator_is_director in (False, True):
            with self.assertRaises(web.HTTPForbidden):
                await create_or_update_tournament(
                    app_state,
                    username,
                    {**form, "name": "Unauthorized edit"},
                    tournament,
                    creator_is_director=creator_is_director,
                )

        await tournament.abort()

    async def test_team_arena_uses_regular_user_arena_quota(self):
        app_state = get_app_state(self.app)
        username = f"TeamArenaQuota{id8()}"
        team_id = f"team-{id8()}"
        now = datetime.now(UTC)
        await app_state.db.user.insert_one({"_id": username})
        await app_state.db.team.insert_one(
            {
                "_id": team_id,
                "name": "Arena Team",
                "enabled": True,
                "memberCount": 1,
                "createdBy": username,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        await app_state.db.team_member.insert_one(
            {
                "_id": f"{username}@{team_id}",
                "team": team_id,
                "user": username,
                "joinedAt": now,
                "permissions": [PERMISSION_TOURNAMENTS],
            }
        )

        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            username,
            self._community_arena_form(teamId=team_id, name="Team Arena"),
            creator_is_director=False,
        )
        tournament_id = (set(app_state.tournaments) - before_ids).pop()
        await app_state.tournaments[tournament_id].abort()

        with self.assertRaises(web.HTTPTooManyRequests):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(name="Public Arena"),
                creator_is_director=False,
            )

    async def test_team_arena_can_be_scheduled_far_ahead_despite_public_arena_conflicts(self):
        app_state = get_app_state(self.app)
        username = f"TeamArenaSchedule{id8()}"
        team_id = f"team-{id8()}"
        now = datetime.now(UTC)
        future_start = now + timedelta(days=2)
        await app_state.db.user.insert_one({"_id": username})
        await app_state.db.team.insert_one(
            {
                "_id": team_id,
                "name": "Scheduled Arena Team",
                "enabled": True,
                "memberCount": 1,
                "createdBy": username,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        await app_state.db.team_member.insert_one(
            {
                "_id": f"{username}@{team_id}",
                "team": team_id,
                "user": username,
                "joinedAt": now,
                "permissions": [PERMISSION_TOURNAMENTS],
            }
        )

        existing = ArenaTournament(
            app_state,
            id8(),
            name="Existing Community Arena",
            created_by=username,
            starts_at=now + timedelta(minutes=5),
            minutes=45,
            with_clock=False,
        )
        protected = ArenaTournament(
            app_state,
            id8(),
            name="Future PyChess Arena",
            created_by="PyChess",
            frequency=SHIELD,
            starts_at=future_start,
            minutes=90,
            with_clock=False,
        )
        app_state.tournaments[existing.id] = existing
        app_state.tournaments[protected.id] = protected

        with self.assertRaises(web.HTTPBadRequest):
            await create_or_update_tournament(
                app_state,
                username,
                self._community_arena_form(
                    teamId=team_id,
                    startDate=future_start.isoformat(),
                    minutes="150",
                ),
                creator_is_director=False,
            )

        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            username,
            self._community_arena_form(
                teamId=team_id,
                name="Future Team Arena",
                startDate=future_start.isoformat(),
            ),
            creator_is_director=False,
        )
        tournament_id = (set(app_state.tournaments) - before_ids).pop()
        tournament = app_state.tournaments[tournament_id]
        self.assertEqual(team_id, tournament.team_id)
        self.assertEqual(future_start, tournament.starts_at)
        await tournament.abort()
        app_state.tournaments.pop(existing.id, None)
        app_state.tournaments.pop(protected.id, None)

    async def test_team_fixed_round_quota_is_shared_and_rolling(self):
        app_state = get_app_state(self.app)
        username = f"TeamFixedQuota{id8()}"
        team_id = f"team-{id8()}"
        now = datetime.now(UTC)
        await app_state.db.user.insert_one({"_id": username})
        await app_state.db.team.insert_one(
            {
                "_id": team_id,
                "name": "Fixed Round Quota Team",
                "enabled": True,
                "memberCount": 1,
                "createdBy": username,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        await app_state.db.team_member.insert_one(
            {
                "_id": f"{username}@{team_id}",
                "team": team_id,
                "user": username,
                "joinedAt": now,
                "permissions": [PERMISSION_TOURNAMENTS],
            }
        )

        with patch("tournament.tournaments.FIXED_ROUND_MAX_CREATIONS_PER_24H", 2):
            for number, system in enumerate(("1", "2"), start=1):
                before_ids = set(app_state.tournaments)
                await create_or_update_tournament(
                    app_state,
                    username,
                    self._fixed_round_form(
                        system,
                        teamId=team_id,
                        name=f"Fixed Round {number}",
                    ),
                    creator_is_director=False,
                )
                tournament_id = (set(app_state.tournaments) - before_ids).pop()
                await app_state.tournaments[tournament_id].abort()

            with self.assertRaises(web.HTTPTooManyRequests):
                await create_or_update_tournament(
                    app_state,
                    username,
                    self._fixed_round_form("1", teamId=team_id, name="Blocked Fixed Round"),
                    creator_is_director=False,
                )

            user_doc = await app_state.db.user.find_one({"_id": username})
            history = list((user_doc or {}).get("fixedRoundCreationHistory", []))
            self.assertEqual(len(history), 2)

            history[0]["at"] = datetime.now(UTC) - timedelta(hours=25)
            await app_state.db.user.update_one(
                {"_id": username},
                {"$set": {"fixedRoundCreationHistory": history}},
            )

            before_ids = set(app_state.tournaments)
            await create_or_update_tournament(
                app_state,
                username,
                self._fixed_round_form("2", teamId=team_id, name="Next Day Fixed Round"),
                creator_is_director=False,
            )
            tournament_id = (set(app_state.tournaments) - before_ids).pop()
            await app_state.tournaments[tournament_id].abort()

            user_doc = await app_state.db.user.find_one({"_id": username})
            history = list((user_doc or {}).get("fixedRoundCreationHistory", []))
            self.assertEqual(len(history), 2)
            self.assertGreater(history[0]["at"], datetime.now(UTC) - timedelta(hours=24))

    async def test_team_fixed_round_failed_creation_releases_quota_claim(self):
        app_state = get_app_state(self.app)
        username = f"TeamFixedRollback{id8()}"
        team_id = f"team-{id8()}"
        now = datetime.now(UTC)
        await app_state.db.user.insert_one({"_id": username})
        await app_state.db.team.insert_one(
            {
                "_id": team_id,
                "name": "Fixed Round Rollback Team",
                "enabled": True,
                "memberCount": 1,
                "createdBy": username,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        await app_state.db.team_member.insert_one(
            {
                "_id": f"{username}@{team_id}",
                "team": team_id,
                "user": username,
                "joinedAt": now,
                "permissions": [PERMISSION_TOURNAMENTS],
            }
        )

        with (
            patch("tournament.tournaments.FIXED_ROUND_MAX_CREATIONS_PER_24H", 1),
            patch(
                "tournament.tournaments.new_tournament",
                new=AsyncMock(side_effect=RuntimeError("simulated fixed-round creation failure")),
            ),
            self.assertRaisesRegex(RuntimeError, "simulated fixed-round creation failure"),
        ):
            await create_or_update_tournament(
                app_state,
                username,
                self._fixed_round_form("2", teamId=team_id),
                creator_is_director=False,
            )

        user_doc = await app_state.db.user.find_one({"_id": username})
        self.assertEqual((user_doc or {}).get("fixedRoundCreationHistory"), [])

        with patch("tournament.tournaments.FIXED_ROUND_MAX_CREATIONS_PER_24H", 1):
            before_ids = set(app_state.tournaments)
            await create_or_update_tournament(
                app_state,
                username,
                self._fixed_round_form("2", teamId=team_id),
                creator_is_director=False,
            )
            tournament_id = (set(app_state.tournaments) - before_ids).pop()
            await app_state.tournaments[tournament_id].abort()

    async def test_rejects_past_custom_start_date(self):
        app_state = get_app_state(self.app)
        past_start = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": "2",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "system": "1",
            "rounds": "0",
            "rrMaxPlayers": "6",
            "rrRequiresApproval": "",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": past_start,
            "endDate": "",
            "name": "Past RR",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }

        with self.assertRaises(web.HTTPBadRequest):
            await create_or_update_tournament(app_state, "tester", form)

    async def test_rescheduled_created_swiss_resets_start_reminder_flags(self):
        app_state = get_app_state(self.app)
        tid = id8()
        tournament = SwissTestTournament(
            app_state,
            tid,
            variant="chess",
            rounds=5,
            starts_at=datetime.now(UTC) + timedelta(hours=1),
            with_clock=False,
        )
        tournament.notify1 = True
        tournament.notify2 = True
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)

        new_start = datetime.now(UTC) + timedelta(hours=2)
        form = self._fixed_round_form(
            "2",
            rounds="5",
            startDate=new_start.isoformat(),
            name=tournament.name,
            minutes=str(tournament.minutes),
        )
        await create_or_update_tournament(
            app_state,
            "tester",
            form,
            tournament,
            creator_is_director=True,
        )

        self.assertEqual(tournament.starts_at, new_start)
        self.assertFalse(tournament.notify1)
        self.assertFalse(tournament.notify2)

    async def test_rejects_started_tournament_start_date_edit_with_meaningful_message(self):
        app_state = get_app_state(self.app)
        tid = id8()
        tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=0,
            rr_max_players=6,
            with_clock=False,
        )
        tournament.status = T_STARTED
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)

        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": str(tournament.base),
            "clockIncrement": str(tournament.inc),
            "byoyomiPeriod": str(tournament.byoyomi_period),
            "system": "1",
            "rounds": "0",
            "rrMaxPlayers": "6",
            "rrRequiresApproval": "",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
            "endDate": "",
            "name": tournament.name,
            "description": tournament.description,
            "password": tournament.password,
            "waitMinutes": "5",
            "minutes": str(tournament.minutes),
        }

        with self.assertRaises(web.HTTPForbidden) as ctx:
            await create_or_update_tournament(app_state, "tester", form, tournament)
        self.assertEqual(
            str(ctx.exception.text),
            "Start date cannot be changed after the tournament has started.",
        )

    async def test_swiss_form_enforces_supported_round_range(self):
        app_state = get_app_state(self.app)

        for rounds in ("2", "16", "not-a-number"):
            with self.subTest(rounds=rounds), self.assertRaises(web.HTTPBadRequest):
                await create_or_update_tournament(
                    app_state,
                    "tester",
                    self._fixed_round_form("2", rounds=rounds),
                )

        before_ids = set(app_state.tournaments)
        await create_or_update_tournament(
            app_state,
            "tester",
            self._fixed_round_form("2", rounds="15", name="Maximum Swiss"),
        )
        tournament_id = (set(app_state.tournaments) - before_ids).pop()
        tournament = app_state.tournaments[tournament_id]
        self.assertEqual(tournament.rounds, 15)
        await tournament.abort()

    async def test_started_swiss_cannot_reduce_rounds_below_current_round(self):
        app_state = get_app_state(self.app)
        tid = id8()
        tournament = SwissTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=7,
            with_clock=False,
        )
        tournament.status = T_STARTED
        tournament.current_round = 4
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)

        form = self._fixed_round_form(
            "2",
            rounds="3",
            clockTime=str(tournament.base),
            clockIncrement=str(tournament.inc),
            byoyomiPeriod=str(tournament.byoyomi_period),
            name=tournament.name,
            minutes=str(tournament.minutes),
        )
        with self.assertRaises(web.HTTPBadRequest) as ctx:
            await create_or_update_tournament(app_state, "tester", form, tournament)
        self.assertEqual(
            str(ctx.exception.text),
            "Swiss round count cannot be lower than the current round (4).",
        )
        self.assertEqual(tournament.rounds, 7)

    async def test_swiss_form_caps_pairing_input_lines(self):
        app_state = get_app_state(self.app)

        forbidden_pairings = "\n".join(f"player{i} opponent{i}" for i in range(2049))
        with self.assertRaises(web.HTTPBadRequest) as forbidden_ctx:
            await create_or_update_tournament(
                app_state,
                "tester",
                self._fixed_round_form("2", forbiddenPairings=forbidden_pairings),
            )
        self.assertEqual(
            str(forbidden_ctx.exception.text),
            "Swiss forbidden pairings are limited to 2048 lines.",
        )

        manual_pairings = "\n".join(f"player{i} 1" for i in range(65))
        with self.assertRaises(web.HTTPBadRequest) as manual_ctx:
            await create_or_update_tournament(
                app_state,
                "tester",
                self._fixed_round_form("2", manualPairings=manual_pairings),
            )
        self.assertEqual(
            str(manual_ctx.exception.text),
            "Swiss manual pairings are limited to 64 lines.",
        )

    async def test_swiss_form_rejects_malformed_or_duplicate_manual_pairings(self):
        app_state = get_app_state(self.app)
        invalid_manual_pairings = (
            "alice",
            "alice alice",
            "alice bob extra",
            "Alice bob\ncarol ALICE",
            "alice 1\nalice bob",
            "alice bob\nbob alice",
        )

        for manual_pairings in invalid_manual_pairings:
            with (
                self.subTest(manual_pairings=manual_pairings),
                self.assertRaises(web.HTTPBadRequest),
            ):
                await create_or_update_tournament(
                    app_state,
                    "tester",
                    self._fixed_round_form("2", manualPairings=manual_pairings),
                )

    async def test_started_swiss_allows_safe_edit_fields(self):
        app_state = get_app_state(self.app)
        tid = id8()
        tournament = SwissTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=5,
            with_clock=False,
        )
        tournament.status = T_STARTED
        tournament.description = "before"
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)

        form = {
            "variant": "chess",
            "rated": "",
            "position": "",
            "clockTime": str(tournament.base),
            "clockIncrement": str(tournament.inc),
            "byoyomiPeriod": str(tournament.byoyomi_period),
            "system": "2",
            "rounds": "7",
            "rrMaxPlayers": "0",
            "rrRequiresApproval": "",
            "roundInterval": "900",
            "entryMinRating": "1400",
            "entryMaxRating": "0",
            "entryMinRatedGames": "10",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "alice bob",
            "manualPairings": "carol dave",
            "name": "Updated Swiss",
            "description": "after",
            "password": "secret",
            "waitMinutes": "5",
            "minutes": str(tournament.minutes),
        }

        await create_or_update_tournament(app_state, "tester", form, tournament)

        self.assertEqual(tournament.name, "Updated Swiss")
        self.assertEqual(tournament.description, "after")
        self.assertEqual(tournament.password, "secret")
        self.assertEqual(tournament.rounds, 7)
        self.assertEqual(tournament.round_interval, 900)
        self.assertEqual(tournament.entry_min_rating, 1400)
        self.assertEqual(tournament.entry_min_rated_games, 10)
        self.assertEqual(tournament.forbidden_pairings, "alice bob")
        self.assertEqual(tournament.manual_pairings, "carol dave")
        self.assertFalse(tournament.rated)

    async def test_edit_preserves_existing_shield_frequency(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=10, minutes=45, with_clock=False
        )
        self.tournament.frequency = SHIELD
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": "5",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "system": str(ArenaTournament.system),
            "rounds": "0",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": "",
            "name": "Shield Edit",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }

        with patch("tournament.tournaments.broadcast_tournament_creation", new=AsyncMock()):
            await create_or_update_tournament(app_state, "tester", form, self.tournament)

        self.assertEqual(self.tournament.frequency, SHIELD)
        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("fr"), SHIELD)

    async def test_rr_form_persists_max_players_and_defers_round_count(self):
        app_state = get_app_state(self.app)
        before_ids = set(app_state.tournaments)
        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": "5",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "system": "1",
            "rounds": "0",
            "rrMaxPlayers": "12",
            "rrRequiresApproval": "1",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": "",
            "name": "RR Cap",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }

        await create_or_update_tournament(app_state, "tester", form)

        new_ids = set(app_state.tournaments) - before_ids
        self.assertEqual(len(new_ids), 1)
        tournament = app_state.tournaments[new_ids.pop()]
        self.assertEqual(tournament.rounds, 0)
        self.assertEqual(tournament.rr_max_players, 12)
        self.assertTrue(tournament.rr_requires_approval)
        self.assertFalse(tournament.rr_joining_closed)

        doc = await app_state.db.tournament.find_one({"_id": tournament.id})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("rounds"), 0)
        self.assertEqual(doc.get("rrMaxPlayers"), 12)
        self.assertEqual(doc.get("rrRequiresApproval"), True)
        self.assertEqual(doc.get("rrJoiningClosed"), False)

    async def test_save_keeps_joined_rr_without_finished_games(self):
        app_state = get_app_state(self.app)
        tid = id8()
        tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=10,
            rounds=0,
            rr_max_players=6,
            with_clock=False,
        )
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)
        await tournament.join_players(2)

        await tournament.save()

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("status"), tournament.status)
        self.assertEqual(doc.get("nbPlayers"), 2)

    async def test_rr_management_state_persists_across_restart(self):
        app_state = get_app_state(self.app)
        tid = id8()
        tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=10,
            rounds=0,
            rr_max_players=6,
            rr_requires_approval=True,
            with_clock=False,
        )
        tournament.created_by = "rr_host"
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)

        denied = User(app_state, username=f"{tid}_denied", perfs=make_test_perfs())
        pending = User(app_state, username=f"{tid}_pending", perfs=make_test_perfs())
        app_state.users[denied.username] = denied
        app_state.users[pending.username] = pending

        # An approval request can be the first state-changing action on an RR,
        # while the tournament still has zero joined players.  It must not delete
        # the tournament document, and all organizer state must be durable.
        self.assertEqual(await tournament.join(denied), "JOIN_REQUESTED")
        self.assertIsNotNone(await app_state.db.tournament.find_one({"_id": tid}))
        self.assertIsNone(await tournament.rr_deny_player(denied.username))
        self.assertEqual(await tournament.join(pending), "JOIN_REQUESTED")
        self.assertIsNone(await tournament.rr_set_joining_closed(True))

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("rrPendingPlayers"), [pending.username])
        self.assertEqual(doc.get("rrDeniedPlayers"), [denied.username])
        self.assertEqual(doc.get("rrJoiningClosed"), True)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.rr_pending_players, {pending.username})
        self.assertEqual(reloaded_tournament.rr_denied_players, {denied.username})
        self.assertTrue(reloaded_tournament.rr_joining_closed)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_reopening_joining_persists_false_state(self):
        app_state = get_app_state(self.app)
        tid = id8()
        tournament = RRTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=10,
            rounds=0,
            rr_max_players=6,
            with_clock=False,
        )
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)

        self.assertIsNone(await tournament.rr_set_joining_closed(True))
        self.assertIsNone(await tournament.rr_set_joining_closed(False))

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("rrJoiningClosed"), False)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertFalse(reloaded_tournament.rr_joining_closed)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_form_end_date_updates_start_and_minutes(self):
        app_state = get_app_state(self.app)
        before_ids = set(app_state.tournaments)
        start_at = (datetime.now(UTC) + timedelta(days=1)).replace(second=0, microsecond=0)
        end_at = start_at + timedelta(minutes=77)
        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": "5",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "system": "1",
            "rounds": "0",
            "rrMaxPlayers": "10",
            "rrRequiresApproval": "",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": start_at.isoformat().replace("+00:00", "Z"),
            "endDate": end_at.isoformat().replace("+00:00", "Z"),
            "name": "RR End Date",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }

        await create_or_update_tournament(app_state, "tester", form)

        new_ids = set(app_state.tournaments) - before_ids
        self.assertEqual(len(new_ids), 1)
        tournament = app_state.tournaments[new_ids.pop()]
        self.assertEqual(tournament.starts_at, start_at)
        self.assertEqual(tournament.minutes, 77)
        self.assertEqual(tournament.ends_at, end_at)

    async def test_swiss_form_ignores_custom_end_date(self):
        app_state = get_app_state(self.app)
        tid = id8()
        start_at = (datetime.now(UTC) + timedelta(days=1)).replace(second=0, microsecond=0)
        tournament = SwissTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=5,
            starts_at=start_at,
            minutes=45,
            rounds=5,
            with_clock=False,
        )
        app_state.tournaments[tid] = tournament
        await upsert_tournament_to_db(tournament, app_state)

        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": str(tournament.base),
            "clockIncrement": str(tournament.inc),
            "byoyomiPeriod": str(tournament.byoyomi_period),
            "system": "2",
            "rounds": "5",
            "rrMaxPlayers": "0",
            "rrRequiresApproval": "",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": start_at.isoformat().replace("+00:00", "Z"),
            "endDate": (start_at + timedelta(minutes=120)).isoformat().replace("+00:00", "Z"),
            "name": "Swiss End Date Ignored",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }

        await create_or_update_tournament(app_state, "tester", form, tournament)

        self.assertEqual(tournament.minutes, 45)
        self.assertEqual(tournament.starts_at, start_at)
        self.assertEqual(tournament.ends_at, start_at + timedelta(minutes=45))

    async def test_arena_form_ignores_custom_end_date(self):
        app_state = get_app_state(self.app)
        before_ids = set(app_state.tournaments)
        start_at = (datetime.now(UTC) + timedelta(days=1)).replace(second=0, microsecond=0)
        form = {
            "variant": "chess",
            "rated": "1",
            "position": "",
            "clockTime": "5",
            "clockIncrement": "0",
            "byoyomiPeriod": "0",
            "system": "0",
            "rounds": "0",
            "rrMaxPlayers": "0",
            "rrRequiresApproval": "",
            "roundInterval": "auto",
            "entryMinRating": "0",
            "entryMaxRating": "0",
            "entryMinRatedGames": "0",
            "entryMinAccountAgeDays": "0",
            "entryTitledOnly": "",
            "forbiddenPairings": "",
            "manualPairings": "",
            "startDate": start_at.isoformat().replace("+00:00", "Z"),
            "endDate": (start_at + timedelta(minutes=120)).isoformat().replace("+00:00", "Z"),
            "name": "Arena End Date Ignored",
            "description": "",
            "password": "",
            "waitMinutes": "5",
            "minutes": "45",
        }

        await create_or_update_tournament(app_state, "tester", form)

        new_ids = set(app_state.tournaments) - before_ids
        self.assertEqual(len(new_ids), 1)
        tournament = app_state.tournaments[new_ids.pop()]
        self.assertEqual(tournament.starts_at, start_at)
        self.assertEqual(tournament.minutes, 45)
        self.assertEqual(tournament.ends_at, start_at + timedelta(minutes=45))

    async def test_tournament_pairings_persist_before_restart(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.start(datetime.now(UTC))
        await self.tournament.join_players(4)

        insert_started = asyncio.Event()
        insert_continue = asyncio.Event()
        original_insert = self.tournament.db_insert_pairing

        async def delayed_insert(games):
            insert_started.set()
            await insert_continue.wait()
            await original_insert(games)

        self.tournament.db_insert_pairing = delayed_insert

        waiting_players = self.tournament.waiting_players()
        pairing_task = asyncio.create_task(
            self.tournament.create_new_pairings(list(waiting_players))
        )
        await insert_started.wait()
        self.assertFalse(pairing_task.done())

        insert_continue.set()
        await pairing_task

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        self.assertGreater(len(reloaded_tournament.ongoing_games), 0)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_gameplay_grace_join_time_persists_and_only_withdrawn_rejoin_resets_it(self):
        app_state = get_app_state(self.app)
        original_join = datetime(2026, 1, 1, tzinfo=UTC)
        for klass in (ArenaTestTournament, RRTestTournament, SwissTestTournament):
            with self.subTest(system=klass.system):
                tid = id8()
                self.tournament = klass(app_state, tid, before_start=10, with_clock=False)
                app_state.tournaments[tid] = self.tournament
                await upsert_tournament_to_db(self.tournament, app_state)
                player = User(app_state, username=f"{TEST_PREFIX}{id8()}", title="TEST")
                app_state.users[player.username] = player
                player.tournament_sockets[tid] = {None}
                await self.tournament.join(player)
                player_data = self.tournament.player_data_by_name(player.username)
                player_data.joined_at = original_join
                await self.tournament.db_update_player(player, "JOIN")

                await self.tournament.pause(player)
                await self.tournament.join(player)
                self.assertEqual(original_join, player_data.joined_at)
                _, restored = await self.reload_tournament(app_state.db_client, tid)
                try:
                    self.assertEqual(
                        original_join, restored.player_data_by_name(player.username).joined_at
                    )
                finally:
                    restored.clock_task.cancel()
                    await asyncio.gather(restored.clock_task, return_exceptions=True)

                await self.tournament.withdraw(player)
                await self.tournament.join(player)
                self.assertGreater(player_data.joined_at, original_join)
                doc = await app_state.db.tournament_player.find_one(
                    {"tid": tid, "uid": player.username}
                )
                self.assertEqual(
                    player_data.joined_at.replace(
                        microsecond=player_data.joined_at.microsecond // 1000 * 1000
                    ),
                    doc["joinedAt"],
                )

    async def test_legacy_tournament_membership_can_reload_without_join_time(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(app_state, tid, before_start=10, with_clock=False)
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)
        await self.tournament.join_players(1)
        player = next(iter(self.tournament.players))
        await app_state.db.tournament_player.update_one(
            {"tid": tid, "uid": player.username}, {"$unset": {"joinedAt": ""}}
        )
        _, restored = await self.reload_tournament(app_state.db_client, tid)
        try:
            self.assertEqual(
                restored.starts_at, restored.player_data_by_name(player.username).joined_at
            )
        finally:
            restored.clock_task.cancel()
            await asyncio.gather(restored.clock_task, return_exceptions=True)

    async def test_tournament_rejoin_persists_rating(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=10, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(1, rating=1500)
        player = list(self.tournament.players.keys())[0]
        player.perfs["chess"]["gl"]["r"] = 2000
        await self.tournament.join(player)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        player_data = next(iter(reloaded_tournament.players.values()))
        self.assertEqual(player_data.rating, 2000)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_tournament_current_round_persisted(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=0, rounds=1, minutes=self.SHORT_SWISS_MINUTES
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.clock_task

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertEqual(doc.get("cr"), 1)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertEqual(reloaded_tournament.current_round, 1)

    async def test_swiss_next_round_start_time_persisted_across_restart(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=2,
            round_interval=3600,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.save_current_round()

        round_finished_at = datetime.now(UTC)
        self.assertTrue(await self.tournament.maybe_schedule_next_fixed_round(round_finished_at))
        expected_start = round_finished_at + timedelta(hours=1)
        self.assertEqual(self.tournament.next_round_starts_at, expected_start)

        # BSON datetimes have millisecond precision. The in-memory timestamp
        # may retain additional microseconds until the process is restarted.
        expected_persisted_start = expected_start.replace(
            microsecond=(expected_start.microsecond // 1000) * 1000
        )
        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertEqual(doc.get("nextRoundStartsAt"), expected_persisted_start)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertEqual(reloaded_tournament.next_round_starts_at, expected_persisted_start)

        halfway = round_finished_at + timedelta(minutes=30)
        _, seconds_to_next_round = reloaded_tournament.round_status(halfway)
        self.assertAlmostEqual(seconds_to_next_round, 1800, delta=0.001)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

        reloaded_tournament.current_round = 2
        await reloaded_tournament.save_current_round()
        doc = await reloaded_tournament.app_state.db.tournament.find_one({"_id": tid})
        self.assertNotIn("nextRoundStartsAt", doc)

    async def test_finished_swiss_persists_early_finish_reason_and_normalized_rounds(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1

        waiting_round_1 = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_round_1)
        for game in games:
            game.result = "1-0"
            game.status = FLAG
            game.board.ply = 20
            await self.tournament.game_update(game)
        await asyncio.sleep(0)

        self.tournament.current_round = 2

        async def _raise_pairing_unavailable(_waiting_players, **_kwargs):
            raise PairingUnavailable("No valid pairing exists")

        with patch.object(
            self.tournament,
            "create_new_pairings",
            side_effect=_raise_pairing_unavailable,
        ):
            should_continue = await self.tournament.pair_fixed_round(datetime.now(UTC))

        self.assertFalse(should_continue)

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("status"), T_FINISHED)
        self.assertEqual(doc.get("rounds"), 1)
        self.assertEqual(doc.get("cr"), 1)
        self.assertEqual(doc.get("finishReason"), SWISS_FINISH_REASON_NO_LEGAL_PAIRING)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.rounds, 1)
        self.assertEqual(reloaded_tournament.current_round, 1)
        self.assertEqual(
            reloaded_tournament.finish_reason,
            SWISS_FINISH_REASON_NO_LEGAL_PAIRING,
        )

    async def test_rr_start_persists_arrangements_and_reload_restores_them(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("rounds"), 3)

        arrangement_docs = await app_state.db.tournament_arrangement.find({"tid": tid}).to_list(
            None
        )
        self.assertEqual(len(arrangement_docs), 6)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.rounds, 3)
        self.assertEqual(len(reloaded_tournament.arrangements), 6)
        self.assertEqual(reloaded_tournament.arrangement_payload()["totalGames"], 6)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_two_player_start_persists_single_arrangement(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))

        self.assertEqual(self.tournament.rounds, 1)
        self.assertEqual(len(self.tournament.arrangements), 1)

        arrangement_docs = await app_state.db.tournament_arrangement.find({"tid": tid}).to_list(
            None
        )
        self.assertEqual(len(arrangement_docs), 1)

    async def test_finished_rr_without_games_is_destroyed(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        await self.tournament.finish()

        self.assertNotIn(tid, app_state.tournaments)
        self.assertNotIn(tid, app_state.tourneysockets)
        self.assertIsNone(await app_state.db.tournament.find_one({"_id": tid}))
        self.assertEqual(
            await app_state.db.tournament_arrangement.count_documents({"tid": tid}),
            0,
        )
        self.assertEqual(
            await app_state.db.tournament_player.count_documents({"tid": tid}),
            0,
        )

    async def test_rr_reload_clears_stale_challenge_and_persists_repair(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        challenger = app_state.users[arrangement.white]
        self.assertIsNone(
            await self.tournament.create_arrangement_challenge(challenger, arrangement.id)
        )
        self.assertEqual(arrangement.status, ARR_STATUS_CHALLENGED)
        self.assertIsNotNone(arrangement.invite_id)
        stale_invite_id = arrangement.invite_id
        assert stale_invite_id is not None
        self.assertIn(stale_invite_id, app_state.invites)

        stored_before = await app_state.db.tournament_arrangement.find_one({"_id": arrangement.id})
        self.assertIsNotNone(stored_before)
        assert stored_before is not None
        self.assertEqual(stored_before.get("s"), ARR_STATUS_CHALLENGED)
        self.assertEqual(stored_before.get("iid"), stale_invite_id)
        self.assertEqual(stored_before.get("ch"), challenger.username)

        with patch(
            "tournament.rr.tournament.RRTournament.broadcast_arrangements",
            new_callable=AsyncMock,
        ) as broadcast_arrangements:
            reloaded_state, reloaded_tournament = await self.reload_tournament(
                app_state.db_client, tid
            )
        broadcast_arrangements.assert_awaited_once_with()
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertNotIn(stale_invite_id, reloaded_state.invites)
        reloaded_arrangement = reloaded_tournament.arrangement_by_id(arrangement.id)
        self.assertIsNotNone(reloaded_arrangement)
        assert reloaded_arrangement is not None
        self.assertEqual(reloaded_arrangement.status, ARR_STATUS_PENDING)
        self.assertIsNone(reloaded_arrangement.invite_id)
        self.assertIsNone(reloaded_arrangement.challenger)

        stored_after = await reloaded_state.db.tournament_arrangement.find_one(
            {"_id": arrangement.id}
        )
        self.assertIsNotNone(stored_after)
        assert stored_after is not None
        self.assertEqual(stored_after.get("s"), ARR_STATUS_PENDING)
        self.assertIsNone(stored_after.get("iid"))
        self.assertIsNone(stored_after.get("ch"))

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_reload_prefers_game_reconciliation_over_stale_challenge(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        challenger = app_state.users[arrangement.white]
        opponent = app_state.users[arrangement.black]
        self.assertIsNone(
            await self.tournament.create_arrangement_challenge(challenger, arrangement.id)
        )
        stale_invite_id = arrangement.invite_id
        assert stale_invite_id is not None

        accept_result = await self.tournament.accept_arrangement_challenge(opponent, arrangement.id)
        self.assertEqual(accept_result["type"], "new_game")
        game_id = accept_result["gameId"]

        # Simulate a crash window where game creation/pairing persistence won but
        # the arrangement document still contains the old challenge state.
        await app_state.db.tournament_arrangement.update_one(
            {"_id": arrangement.id},
            {
                "$set": {
                    "s": ARR_STATUS_CHALLENGED,
                    "gid": None,
                    "iid": stale_invite_id,
                    "ch": challenger.username,
                }
            },
        )

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        reloaded_arrangement = reloaded_tournament.arrangement_by_id(arrangement.id)
        self.assertIsNotNone(reloaded_arrangement)
        assert reloaded_arrangement is not None
        self.assertEqual(reloaded_arrangement.status, ARR_STATUS_STARTED)
        self.assertEqual(reloaded_arrangement.game_id, game_id)
        self.assertIsNone(reloaded_arrangement.invite_id)
        self.assertIsNone(reloaded_arrangement.challenger)

        stored_after = await reloaded_tournament.app_state.db.tournament_arrangement.find_one(
            {"_id": arrangement.id}
        )
        self.assertIsNotNone(stored_after)
        assert stored_after is not None
        self.assertEqual(stored_after.get("s"), ARR_STATUS_STARTED)
        self.assertEqual(stored_after.get("gid"), game_id)
        self.assertIsNone(stored_after.get("iid"))
        self.assertIsNone(stored_after.get("ch"))

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_reload_restores_started_arrangement_game(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        game = await self.tournament.start_arrangement_game(arrangement.id)
        self.assertEqual(game.tournamentArrangementId, arrangement.id)
        self.assertEqual(len(self.tournament.ongoing_games), 1)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        reloaded_arrangement = reloaded_tournament.arrangement_by_id(arrangement.id)
        self.assertIsNotNone(reloaded_arrangement)
        assert reloaded_arrangement is not None
        self.assertEqual(reloaded_arrangement.status, "started")
        self.assertEqual(reloaded_arrangement.game_id, game.id)
        self.assertEqual(len(reloaded_tournament.ongoing_games), 1)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_reload_restores_deadline_draining_game_and_scores_it(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        game = await self.tournament.start_arrangement_game(arrangement.id)

        past_start = datetime.now(UTC) - timedelta(minutes=2)
        self.tournament.starts_at = past_start
        self.tournament.minutes = 1
        self.tournament.ends_at = past_start + timedelta(minutes=1)
        await app_state.db.tournament.update_one(
            {"_id": tid},
            {"$set": {"startsAt": past_start, "minutes": 1}},
        )

        self.assertEqual(self.tournament.status, T_STARTED)
        self.assertEqual(arrangement.status, ARR_STATUS_STARTED)
        self.assertTrue(self.tournament.deadline_reached())

        # load_tournament() deliberately restores the production RR class. Keep
        # this lifecycle test on the TestTournament cadence so it verifies the
        # clock transition without waiting a real production second.
        with patch.object(RRTournament, "clock_interval", RRTestTournament.clock_interval):
            reloaded_app_state, reloaded_tournament = await self.reload_tournament(
                app_state.db_client, tid
            )
            self.assertIsNotNone(reloaded_tournament)
            assert reloaded_tournament is not None
            self.assertEqual(reloaded_tournament.status, T_STARTED)
            self.assertTrue(reloaded_tournament.deadline_reached())
            self.assertEqual(len(reloaded_tournament.ongoing_games), 1)
            reloaded_arrangement = reloaded_tournament.arrangement_by_id(arrangement.id)
            self.assertIsNotNone(reloaded_arrangement)
            assert reloaded_arrangement is not None
            self.assertEqual(reloaded_arrangement.status, ARR_STATUS_STARTED)

            # Let the restored RR clock observe the expired deadline. It must keep
            # draining the live game instead of finishing the tournament.
            await asyncio.sleep(reloaded_tournament.clock_interval + 0.01)
            self.assertEqual(reloaded_tournament.status, T_STARTED)
            self.assertEqual(len(reloaded_tournament.ongoing_games), 1)

            # reload_tournament() reconstructs only the tournament fixture, not the
            # full startup sequence that normally releases finished game callbacks.
            reloaded_app_state.tournaments_loaded.set()
            reloaded_game = reloaded_app_state.games[game.id]
            reloaded_game.board.ply = 20
            await reloaded_game.game_ended(reloaded_game.bplayer, "resign")
            if reloaded_tournament.clock_task is not None:
                await asyncio.wait_for(reloaded_tournament.clock_task, timeout=2)

        self.assertEqual(reloaded_tournament.status, T_FINISHED)
        self.assertEqual(reloaded_tournament.nb_games_finished, 1)
        self.assertEqual(reloaded_arrangement.status, ARR_STATUS_FINISHED)
        self.assertGreater(
            reloaded_tournament.leaderboard_score_by_username(reloaded_game.wplayer.username)
            // SCORE_SHIFT,
            0,
        )
        tournament_doc = await reloaded_app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(tournament_doc)
        assert tournament_doc is not None
        self.assertEqual(tournament_doc["status"], T_FINISHED)

    async def test_rr_reload_reconciles_finished_game_with_stale_started_arrangement(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        game = await self.tournament.start_arrangement_game(arrangement.id)

        game.board.ply = 20
        game.result = "1-0"
        game.status = FLAG
        await app_state.db.game.update_one(
            {"_id": game.id},
            {"$set": {"s": FLAG, "r": "a", "p": game.board.ply}},
        )

        with (
            patch.object(
                self.tournament,
                "db_update_arrangement",
                AsyncMock(side_effect=RuntimeError("simulated restart")),
            ),
            self.assertRaises(RuntimeError),
        ):
            await self.tournament.game_update(game)

        stale_arrangement_doc = await app_state.db.tournament_arrangement.find_one(
            {"_id": arrangement.id}
        )
        self.assertIsNotNone(stale_arrangement_doc)
        assert stale_arrangement_doc is not None
        self.assertEqual(stale_arrangement_doc.get("s"), "started")
        self.assertEqual(stale_arrangement_doc.get("gid"), game.id)

        pairing_doc = await app_state.db.tournament_pairing.find_one({"_id": game.id})
        self.assertIsNotNone(pairing_doc)
        assert pairing_doc is not None
        self.assertEqual(pairing_doc.get("r"), "a")

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        reloaded_arrangement = reloaded_tournament.arrangement_by_id(arrangement.id)
        self.assertIsNotNone(reloaded_arrangement)
        assert reloaded_arrangement is not None
        self.assertEqual(reloaded_arrangement.status, "finished")
        self.assertEqual(reloaded_arrangement.game_id, game.id)
        self.assertTrue(reloaded_tournament.all_arrangements_finished())

        repaired_arrangement_doc = (
            await reloaded_tournament.app_state.db.tournament_arrangement.find_one(
                {"_id": arrangement.id}
            )
        )
        self.assertIsNotNone(repaired_arrangement_doc)
        assert repaired_arrangement_doc is not None
        self.assertEqual(repaired_arrangement_doc.get("s"), "finished")
        self.assertEqual(repaired_arrangement_doc.get("gid"), game.id)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_annulled_result_stays_reopened_after_restart(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=4, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        game = await self.tournament.start_arrangement_game(arrangement.id)
        game.board.ply = 20
        await game.game_ended(game.bplayer, "resign")
        self.assertEqual(self.tournament.nb_games_finished, 1)

        self.assertIsNone(await self.tournament.annul_arrangement_game(arrangement.id, game.id))

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        reloaded_arrangement = reloaded_tournament.arrangement_by_id(arrangement.id)
        self.assertIsNotNone(reloaded_arrangement)
        assert reloaded_arrangement is not None
        self.assertEqual(reloaded_arrangement.status, ARR_STATUS_PENDING)
        self.assertIsNone(reloaded_arrangement.game_id)
        self.assertEqual(reloaded_arrangement.previous_game_ids, [game.id])
        self.assertEqual(reloaded_tournament.nb_games_finished, 0)
        for username in arrangement.players():
            player_data = reloaded_tournament.player_data_by_name(username)
            assert player_data is not None
            self.assertFalse(any(getattr(g, "id", None) == game.id for g in player_data.games))
            self.assertEqual(player_data.points, [])
            self.assertEqual(reloaded_tournament.leaderboard_score_by_username(username), 0)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_annul_marker_repairs_player_scores_after_mid_annul_restart(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=4, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        game = await self.tournament.start_arrangement_game(arrangement.id)
        game.board.ply = 20
        await game.game_ended(game.bplayer, "resign")

        # Simulate a crash immediately after annulment writes its durable pairing
        # marker, before either tournament_player row or the arrangement is reset.
        await app_state.db.tournament_pairing.update_one(
            {"_id": game.id, "tid": tid},
            {"$set": {"an": True}},
        )

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        reloaded_arrangement = reloaded_tournament.arrangement_by_id(arrangement.id)
        self.assertIsNotNone(reloaded_arrangement)
        assert reloaded_arrangement is not None
        self.assertEqual(reloaded_arrangement.status, ARR_STATUS_PENDING)
        self.assertIsNone(reloaded_arrangement.game_id)
        self.assertEqual(reloaded_arrangement.previous_game_ids, [game.id])
        self.assertEqual(reloaded_tournament.nb_games_finished, 0)

        for username in arrangement.players():
            player_data = reloaded_tournament.player_data_by_name(username)
            assert player_data is not None
            self.assertEqual(player_data.points, [])
            self.assertEqual(reloaded_tournament.leaderboard_score_by_username(username), 0)
            player_doc = await app_state.db.tournament_player.find_one(
                {"tid": tid, "uid": username}
            )
            self.assertIsNotNone(player_doc)
            assert player_doc is not None
            self.assertEqual(player_doc["p"], [])
            self.assertEqual(player_doc["s"], 0)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_rr_short_game_persists_even_if_tournament_id_is_missing(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = RRTestTournament(
            app_state, tid, before_start=10, rounds=0, rr_max_players=8, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        arrangement = self.tournament.arrangement_list()[0]
        game = await self.tournament.start_arrangement_game(arrangement.id)

        # Reproduce the observed RR challenge bug shape: the game still knows
        # its arrangement id, but has lost its explicit tournament id.
        game.tournamentId = None
        game.board.ply = 2
        game.update_status(FLAG, "0-1")
        await game.save_game()

        game_doc = await app_state.db.game.find_one({"_id": game.id})
        self.assertIsNotNone(game_doc)
        assert game_doc is not None
        self.assertEqual(game_doc.get("tid"), tid)
        self.assertEqual(game_doc.get("aid"), arrangement.id)

        arrangement_doc = await app_state.db.tournament_arrangement.find_one(
            {"_id": arrangement.id}
        )
        self.assertIsNotNone(arrangement_doc)
        assert arrangement_doc is not None
        self.assertEqual(arrangement_doc.get("gid"), game.id)
        self.assertEqual(arrangement_doc.get("s"), "finished")

    async def test_save_game_persists_final_tournament_state_before_game_update(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20

        seen_doc = {}

        async def inspect_saved_doc(saved_game):
            doc = await app_state.db.game.find_one({"_id": saved_game.id})
            seen_doc["status"] = doc["s"]
            seen_doc["result"] = doc["r"]
            seen_doc["ply"] = doc["p"]

        self.tournament.game_update = inspect_saved_doc

        await game.save_game()

        self.assertEqual(seen_doc, {"status": FLAG, "result": "a", "ply": 20})

    async def test_save_game_persists_final_state_before_rating_side_effects(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20

        async def fail_after_authoritative_write(_game_doc, *, users_only=False):
            self.assertFalse(users_only)
            doc = await app_state.db.game.find_one({"_id": game.id})
            self.assertIsNotNone(doc)
            assert doc is not None
            self.assertEqual(doc["s"], FLAG)
            self.assertEqual(doc["r"], "a")
            self.assertEqual(doc["p"], 20)
            self.assertEqual(doc.get("fx"), 1)
            self.assertIn("p0", doc)
            self.assertIn("p1", doc)
            raise RuntimeError("simulated crash before tournament side effects")

        with (
            patch.object(
                game,
                "complete_tournament_final_side_effects",
                side_effect=fail_after_authoritative_write,
            ),
            self.assertRaisesRegex(RuntimeError, "simulated crash"),
        ):
            await game.save_game()

        # The tournament update was never reached, so startup recovery must be
        # able to reconstruct the score from the already-finished game document.
        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        winner = reloaded_tournament.player_data_by_name(game.wplayer.username)
        loser = reloaded_tournament.player_data_by_name(game.bplayer.username)
        self.assertIsNotNone(winner)
        self.assertIsNotNone(loser)
        assert winner is not None
        assert loser is not None
        self.assertEqual(winner.points, [(2, 1)])
        self.assertEqual(loser.points, [(0, 1)])

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_finished_tournament_game_side_effects_recover_exactly_once(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)

        for username in ("restart_effect_white", "restart_effect_black"):
            perfs = make_test_perfs()
            player = User(app_state, username=username, perfs=perfs)
            app_state.users[username] = player
            await app_state.db.user.insert_one(
                {
                    "_id": username,
                    "title": "",
                    "perfs": perfs,
                    "count": dict(player.count),
                }
            )
            player.tournament_sockets[tid] = {None}
            await self.tournament.join(player)

        await self.tournament.start(datetime.now(UTC))
        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20

        async def crash_before_black_effect(*_args, **_kwargs):
            raise RuntimeError("simulated crash between player side effects")

        with (
            patch.object(
                game.bplayer,
                "apply_tournament_game_effect_once",
                side_effect=crash_before_black_effect,
            ),
            self.assertRaisesRegex(RuntimeError, "simulated crash"),
        ):
            await game.save_game()

        game_doc = await app_state.db.game.find_one({"_id": game.id})
        self.assertIsNotNone(game_doc)
        assert game_doc is not None
        self.assertEqual(game_doc.get("fx"), 1)
        self.assertIn("n", game_doc["p0"])
        self.assertIn("n", game_doc["p1"])

        white_doc = await app_state.db.user.find_one({"_id": game.wplayer.username})
        black_doc = await app_state.db.user.find_one({"_id": game.bplayer.username})
        self.assertIsNotNone(white_doc)
        self.assertIsNotNone(black_doc)
        assert white_doc is not None
        assert black_doc is not None
        self.assertEqual(white_doc["count"]["game"], 1)
        self.assertEqual(black_doc["count"]["game"], 0)
        self.assertIn(game.id, white_doc.get("tournamentGameEffectIds", []))
        self.assertNotIn(game.id, black_doc.get("tournamentGameEffectIds", []))

        # Drop the in-memory game/users to reproduce the startup path loading
        # authoritative state back from MongoDB before tournaments can resume.
        app_state.games.pop(game.id, None)
        for player in (game.wplayer, game.bplayer):
            if player.username in app_state.users:
                del app_state.users[player.username]

        await recover_pending_tournament_game_side_effects(app_state, users_only=True)

        white_doc = await app_state.db.user.find_one({"_id": game.wplayer.username})
        black_doc = await app_state.db.user.find_one({"_id": game.bplayer.username})
        assert white_doc is not None
        assert black_doc is not None
        self.assertEqual(white_doc["count"]["game"], 1)
        self.assertEqual(black_doc["count"]["game"], 1)
        self.assertEqual(white_doc["count"]["rated"], 1)
        self.assertEqual(black_doc["count"]["rated"], 1)
        self.assertEqual(
            white_doc["perfs"]["chess"],
            game_doc["p0"]["n"],
        )
        self.assertEqual(
            black_doc["perfs"]["chess"],
            game_doc["p1"]["n"],
        )

        # Re-running the user-only startup pass is harmless.
        await recover_pending_tournament_game_side_effects(app_state, users_only=True)
        white_doc_again = await app_state.db.user.find_one({"_id": game.wplayer.username})
        black_doc_again = await app_state.db.user.find_one({"_id": game.bplayer.username})
        assert white_doc_again is not None
        assert black_doc_again is not None
        self.assertEqual(white_doc_again["count"]["game"], 1)
        self.assertEqual(black_doc_again["count"]["game"], 1)

        await recover_pending_tournament_game_side_effects(app_state, users_only=False)
        completed_doc = await app_state.db.game.find_one({"_id": game.id})
        self.assertIsNotNone(completed_doc)
        assert completed_doc is not None
        self.assertEqual(completed_doc.get("fx"), 2)

        crosstable = await app_state.db.crosstable.find_one({"_id": game.ct_id})
        self.assertIsNotNone(crosstable)
        assert crosstable is not None
        self.assertEqual(sum(entry.startswith(game.id) for entry in crosstable["r"]), 1)

        # Once fx=2 the startup scan no longer sees the game.
        self.assertEqual(
            await recover_pending_tournament_game_side_effects(app_state, users_only=False),
            0,
        )

    async def test_swiss_no_show_ban_recovery_is_idempotent(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            variant="chess",
            before_start=0,
            rounds=2,
            with_clock=False,
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)

        # Use DB-backed usernames here: TEST_PREFIX tournament players are
        # intentionally reconstructed as synthetic in-memory users on reload,
        # which would bypass the persisted Swiss ban idempotency marker.
        username_prefix = f"SwissNoShow{id8()}"
        for suffix in ("A", "B"):
            player = User(
                app_state,
                username=f"{username_prefix}{suffix}",
                title="TEST",
                perfs=make_test_perfs(),
            )
            app_state.users[player.username] = player
            player.tournament_sockets[tid] = {None}
            await app_state.db.user.insert_one({"_id": player.username})
            await self.tournament.join(player)

        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]

        absent = game.wplayer
        present = game.bplayer

        async def crash_after_culprit_ban(_player, _game_id):
            raise RuntimeError("simulated crash during Swiss no-show persistence")

        with patch.object(self.tournament, "_clear_swiss_ban", new=crash_after_culprit_ban):
            # With zero moves White is the no-show culprit, so their ban is
            # persisted first. save_game() logs the injected failure while
            # clearing Black's ban state, leaving the same durable state as a
            # process death between the two user writes and before scoring.
            await game.game_ended(absent, "flag")

        absent_doc = await app_state.db.user.find_one({"_id": absent.username})
        self.assertIsNotNone(absent_doc)
        assert absent_doc is not None
        self.assertEqual(absent_doc.get("swissBanHours"), 24)
        self.assertEqual(absent_doc.get("swissBanGameId"), game.id)
        first_ban_until = absent_doc.get("swissBanUntil")
        self.assertIsNotNone(first_ban_until)

        present_doc = await app_state.db.user.find_one({"_id": present.username})
        self.assertIsNotNone(present_doc)
        assert present_doc is not None
        self.assertNotIn("swissBanGameId", present_doc)

        # Base tournament scoring never ran before the simulated process death.
        absent_tournament_doc = await app_state.db.tournament_player.find_one(
            {"tid": tid, "uid": absent.username}
        )
        self.assertIsNotNone(absent_tournament_doc)
        assert absent_tournament_doc is not None
        self.assertEqual(absent_tournament_doc.get("p"), [])

        reloaded_state, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        reloaded_absent = await reloaded_state.users.get(absent.username)
        reloaded_present = await reloaded_state.users.get(present.username)

        # Recovery replays Swiss no-show handling before applying the missing
        # tournament result. The culprit's per-game marker prevents 24h -> 36h,
        # while the interrupted opponent update is completed.
        self.assertEqual(reloaded_absent.swiss_ban_hours, 24)
        self.assertEqual(reloaded_absent.swiss_ban_until, first_ban_until)
        self.assertEqual(reloaded_absent.swiss_ban_game_id, game.id)
        self.assertIsNone(reloaded_present.swiss_ban_until)
        self.assertEqual(reloaded_present.swiss_ban_hours, 0)
        self.assertEqual(reloaded_present.swiss_ban_game_id, game.id)

        winner = reloaded_tournament.player_data_by_name(game.bplayer.username)
        loser = reloaded_tournament.player_data_by_name(game.wplayer.username)
        self.assertIsNotNone(winner)
        self.assertIsNotNone(loser)
        assert winner is not None
        assert loser is not None
        self.assertEqual(winner.points, [(2, 1)])
        self.assertEqual(loser.points, [(0, 1)])

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_recovers_scores_from_finished_game_doc(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)

        player_a = User(
            app_state, username=f"{TEST_PREFIX}A", title="TEST", perfs=make_test_perfs()
        )
        player_b = User(
            app_state, username=f"{TEST_PREFIX}B", title="TEST", perfs=make_test_perfs()
        )
        app_state.users[player_a.username] = player_a
        app_state.users[player_b.username] = player_b
        player_a.tournament_sockets[tid] = {None}
        player_b.tournament_sockets[tid] = {None}

        await self.tournament.join(player_a)
        await self.tournament.join(player_b)
        await self.tournament.start(datetime.now(UTC))

        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20

        async def skip_update(_game):
            return

        self.tournament.game_update = skip_update
        await game.save_game()

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        winner = reloaded_tournament.player_data_by_name(game.wplayer.username)
        loser = reloaded_tournament.player_data_by_name(game.bplayer.username)
        self.assertEqual(winner.points, [(2, 1)])
        self.assertEqual(loser.points, [(0, 1)])

        updated_pairing = await reloaded_tournament.app_state.db.tournament_pairing.find_one(
            {"_id": game.id}
        )
        self.assertEqual(updated_pairing["r"], "a")

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_recovers_partial_player_persistence_without_double_scoring(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)

        player_a = User(
            app_state, username=f"{TEST_PREFIX}A", title="TEST", perfs=make_test_perfs()
        )
        player_b = User(
            app_state, username=f"{TEST_PREFIX}B", title="TEST", perfs=make_test_perfs()
        )
        app_state.users[player_a.username] = player_a
        app_state.users[player_b.username] = player_b
        player_a.tournament_sockets[tid] = {None}
        player_b.tournament_sockets[tid] = {None}

        await self.tournament.join(player_a)
        await self.tournament.join(player_b)
        await self.tournament.start(datetime.now(UTC))

        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20

        async def persist_white_only(saved_game):
            white_data = self.tournament.player_data_by_name(saved_game.wplayer.username)
            assert white_data is not None
            self.tournament._apply_game_result_to_player(saved_game, white_data, is_white=True)
            await self.tournament.db_update_player(saved_game.wplayer, "GAME_END")
            # Simulate the pairing result becoming durable even though the black
            # player update was lost (for example because db_update_player logged
            # and swallowed a transient MongoDB failure). Recovery must retain the
            # persisted rating deltas as well as the score.
            await self.tournament.db_update_pairing(saved_game)
            raise RuntimeError("simulated mid-game_update crash")

        self.tournament.game_update = persist_white_only
        await game.save_game()

        expected_winner_rating = int(game.wrating.rstrip("?")) + int(game.wrdiff or 0)
        expected_loser_rating = int(game.brating.rstrip("?")) + int(game.brdiff or 0)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        winner = reloaded_tournament.player_data_by_name(game.wplayer.username)
        loser = reloaded_tournament.player_data_by_name(game.bplayer.username)
        self.assertEqual(winner.points, [(2, 1)])
        self.assertEqual(loser.points, [(0, 1)])
        self.assertEqual(winner.rating, expected_winner_rating)
        self.assertEqual(loser.rating, expected_loser_rating)

        updated_pairing = await reloaded_tournament.app_state.db.tournament_pairing.find_one(
            {"_id": game.id}
        )
        self.assertEqual(updated_pairing["r"], "a")
        self.assertEqual(int(updated_pairing["wrd"]), int(game.wrdiff or 0))
        self.assertEqual(int(updated_pairing["brd"]), int(game.brdiff or 0))

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_repairs_partially_persisted_swiss_late_join(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=5, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 2
        await self.tournament.save_current_round()

        late = User(app_state, username=f"{TEST_PREFIX}late_restart", perfs=make_test_perfs())
        app_state.users[late.username] = late
        late.tournament_sockets[tid] = {None}

        original_insert_bye = self.tournament.db_insert_bye_pairing
        inserted = 0

        async def crash_during_late_join_byes(*args, **kwargs):
            nonlocal inserted
            inserted += 1
            if inserted == 1:
                return await original_insert_bye(*args, **kwargs)
            raise RuntimeError("simulated restart during late-join bye persistence")

        with (
            patch.object(
                self.tournament,
                "db_insert_bye_pairing",
                side_effect=crash_during_late_join_byes,
            ),
            self.assertRaises(RuntimeError),
        ):
            await self.tournament.join(late)

        player_doc = await app_state.db.tournament_player.find_one(
            {"tid": tid, "uid": late.username}
        )
        self.assertIsNotNone(player_doc)
        assert player_doc is not None
        self.assertEqual(player_doc["jr"], 3)
        self.assertEqual(player_doc["p"], [[1, 0], [0, 0]])
        self.assertEqual(player_doc["s"], 1)

        partial_byes = await app_state.db.tournament_pairing.find(
            {"tid": tid, "s": BYEGAME, "u": [late.username, late.username]}
        ).to_list(length=None)
        self.assertEqual(len(partial_byes), 1)
        self.assertEqual(partial_byes[0]["rn"], 1)
        self.assertEqual(partial_byes[0]["bt"], "H")

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None

        reloaded_player = reloaded_tournament.player_data_by_name(late.username)
        self.assertIsNotNone(reloaded_player)
        assert reloaded_player is not None
        self.assertEqual(reloaded_player.joined_round, 3)
        self.assertEqual(reloaded_player.points[:2], [(1, 0), (0, 0)])
        self.assertEqual(
            [game.token for game in reloaded_player.games[:2] if isinstance(game, ByeGame)],
            ["H", "Z"],
        )
        self.assertEqual(
            [game.round for game in reloaded_player.games[:2] if isinstance(game, ByeGame)],
            [1, 2],
        )
        self.assertEqual(
            reloaded_tournament.leaderboard_score_by_username(late.username) // SCORE_SHIFT,
            1,
        )

        repaired_byes = await reloaded_tournament.app_state.db.tournament_pairing.find(
            {
                "tid": tid,
                "s": BYEGAME,
                "u": [late.username, late.username],
            }
        ).to_list(length=None)
        self.assertEqual(len(repaired_byes), 2)
        self.assertEqual(
            sorted((doc["rn"], doc["bt"]) for doc in repaired_byes),
            [(1, "H"), (2, "Z")],
        )

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_recovers_committed_swiss_round_with_stale_round_doc(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.set_pairing_in_progress_round(1)

        waiting_players = list(self.tournament.waiting_players())
        _, games = await Tournament.create_new_pairings(
            self.tournament,
            waiting_players,
            publish_pairings=False,
        )
        self.assertEqual(len(games), 1)

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("cr"), 0)
        self.assertEqual(doc.get("pairingInProgressRound"), 1)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.current_round, 1)
        self.assertEqual(len(reloaded_tournament.ongoing_games), 1)

        reloaded_doc = await reloaded_tournament.app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(reloaded_doc)
        assert reloaded_doc is not None
        self.assertEqual(reloaded_doc.get("cr"), 1)
        self.assertNotIn("pairingInProgressRound", reloaded_doc)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_consumes_manual_pairings_with_committed_swiss_round(self):
        app_state = get_app_state(self.app)
        tid = id8()
        manual_pairings = "manual_white manual_black"
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=2,
            with_clock=False,
            manual_pairings=manual_pairings,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        for name in ("manual_white", "manual_black"):
            user = User(app_state, username=name, perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)

        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.set_pairing_in_progress_round(1, manual_pairings=manual_pairings)

        waiting_players = list(self.tournament.waiting_players())
        pairing, games = await self.tournament.create_new_pairings(
            waiting_players,
            publish_pairings=False,
        )
        self.assertEqual(len(pairing), 1)
        self.assertEqual(len(games), 1)
        self.assertEqual(pairing[0][0].username, "manual_white")
        self.assertEqual(pairing[0][1].username, "manual_black")

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("cr"), 0)
        self.assertEqual(doc.get("pairingInProgressRound"), 1)
        self.assertEqual(doc.get("manualPairingsInProgress"), manual_pairings)
        self.assertEqual(doc.get("manualPairings"), manual_pairings)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.current_round, 1)
        self.assertEqual(reloaded_tournament.manual_pairings, "")
        self.assertIsNone(reloaded_tournament.manual_pairings_in_progress)

        reloaded_doc = await reloaded_tournament.app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(reloaded_doc)
        assert reloaded_doc is not None
        self.assertEqual(reloaded_doc.get("cr"), 1)
        self.assertEqual(reloaded_doc.get("manualPairings"), "")
        self.assertNotIn("pairingInProgressRound", reloaded_doc)
        self.assertNotIn("manualPairingsInProgress", reloaded_doc)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_preserves_manual_pairings_when_swiss_round_rolls_back(self):
        app_state = get_app_state(self.app)
        tid = id8()
        manual_pairings = "manual_white manual_black"
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=2,
            with_clock=False,
            manual_pairings=manual_pairings,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        for name in ("manual_white", "manual_black"):
            user = User(app_state, username=name, perfs=make_test_perfs())
            app_state.users[user.username] = user
            user.tournament_sockets[tid] = {None}
            await self.tournament.join(user)

        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.set_pairing_in_progress_round(1, manual_pairings=manual_pairings)

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("manualPairingsInProgress"), manual_pairings)
        self.assertEqual(doc.get("manualPairings"), manual_pairings)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.current_round, 0)
        self.assertEqual(reloaded_tournament.manual_pairings, manual_pairings)
        self.assertIsNone(reloaded_tournament.manual_pairings_in_progress)

        reloaded_doc = await reloaded_tournament.app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(reloaded_doc)
        assert reloaded_doc is not None
        self.assertEqual(reloaded_doc.get("manualPairings"), manual_pairings)
        self.assertNotIn("pairingInProgressRound", reloaded_doc)
        self.assertNotIn("manualPairingsInProgress", reloaded_doc)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_swiss_round_commit_does_not_clear_newer_manual_pairings(self):
        app_state = get_app_state(self.app)
        tid = id8()
        consumed_pairings = "manual_white manual_black"
        next_pairings = "next_white next_black"
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            before_start=10,
            rounds=3,
            with_clock=False,
            manual_pairings=consumed_pairings,
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        self.tournament.current_round = 1
        await self.tournament.set_pairing_in_progress_round(1, manual_pairings=consumed_pairings)

        self.tournament.manual_pairings = next_pairings
        await app_state.db.tournament.update_one(
            {"_id": tid},
            {"$set": {"manualPairings": next_pairings}},
        )
        await self.tournament.save_current_round()

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.get("cr"), 1)
        self.assertEqual(doc.get("manualPairings"), next_pairings)
        self.assertNotIn("pairingInProgressRound", doc)
        self.assertNotIn("manualPairingsInProgress", doc)
        self.assertEqual(self.tournament.manual_pairings, next_pairings)

    async def test_load_tournament_rolls_back_incomplete_swiss_round_with_orphan_games(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.set_pairing_in_progress_round(1)

        players = list(self.tournament.players.keys())
        await self.tournament.create_games([(players[0], players[1])])

        self.assertIsNotNone(await app_state.db.game.find_one({"tid": tid}))
        self.assertIsNone(await app_state.db.tournament_pairing.find_one({"tid": tid, "rn": 1}))

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.current_round, 0)
        self.assertEqual(len(reloaded_tournament.ongoing_games), 0)
        self.assertTrue(
            all(len(player_data.games) == 0 for player_data in reloaded_tournament.players.values())
        )
        self.assertTrue(
            all(
                len(player_data.points) == 0 for player_data in reloaded_tournament.players.values()
            )
        )

        reloaded_doc = await reloaded_tournament.app_state.db.tournament.find_one({"_id": tid})
        self.assertIsNotNone(reloaded_doc)
        assert reloaded_doc is not None
        self.assertEqual(reloaded_doc.get("cr"), 0)
        self.assertNotIn("pairingInProgressRound", reloaded_doc)
        self.assertIsNone(await reloaded_tournament.app_state.db.game.find_one({"tid": tid}))

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_recovers_complete_swiss_round_from_game_docs_without_pairings(
        self,
    ):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.set_pairing_in_progress_round(1)

        players = list(self.tournament.players.keys())
        await self.tournament.create_games([(players[0], players[1])])

        self.assertIsNotNone(await app_state.db.game.find_one({"tid": tid}))
        self.assertIsNone(await app_state.db.tournament_pairing.find_one({"tid": tid, "rn": 1}))

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None
        self.assertEqual(reloaded_tournament.current_round, 1)
        self.assertEqual(len(reloaded_tournament.ongoing_games), 1)

        repaired_pairing = await reloaded_tournament.app_state.db.tournament_pairing.find_one(
            {"tid": tid, "rn": 1}
        )
        self.assertIsNotNone(repaired_pairing)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_swiss_entry_conditions_persisted(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state,
            tid,
            before_start=0,
            rounds=5,
            with_clock=False,
            entry_min_rating=1500,
            entry_max_rating=2100,
            entry_min_rated_games=30,
            entry_min_account_age_days=14,
            forbidden_pairings="alice bob",
            manual_pairings="carol dave",
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        doc = await app_state.db.tournament.find_one({"_id": tid})
        self.assertEqual(doc.get("entryMinRating"), 1500)
        self.assertEqual(doc.get("entryMaxRating"), 2100)
        self.assertEqual(doc.get("entryMinRatedGames"), 30)
        self.assertEqual(doc.get("entryMinAccountAgeDays"), 14)
        self.assertIsNone(doc.get("entryTitledOnly"))
        self.assertEqual(doc.get("forbiddenPairings"), "alice bob")
        self.assertEqual(doc.get("manualPairings"), "carol dave")

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertEqual(reloaded_tournament.entry_min_rating, 1500)
        self.assertEqual(reloaded_tournament.entry_max_rating, 2100)
        self.assertEqual(reloaded_tournament.entry_min_rated_games, 30)
        self.assertEqual(reloaded_tournament.entry_min_account_age_days, 14)
        self.assertFalse(reloaded_tournament.entry_titled_only)
        self.assertEqual(reloaded_tournament.forbidden_pairings, "alice bob")
        self.assertEqual(reloaded_tournament.manual_pairings, "carol dave")

    async def test_db_update_pairing_upserts(self):
        from game import Game

        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        players = list(self.tournament.players.keys())

        game = Game(
            app_state,
            id8(),
            "chess",
            "",
            players[0],
            players[1],
            rated=RATED,
            tournamentId=tid,
        )
        game.result = "1-0"
        game.wberserk = True
        game.board.ply = 20

        await self.tournament.db_update_pairing(game)

        doc = await app_state.db.tournament_pairing.find_one({"_id": game.id})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["r"], "a")
        self.assertTrue(doc["wb"])
        self.assertEqual(doc["p"], 20)
        self.assertEqual(tuple(doc["u"]), (players[0].username, players[1].username))

    async def test_load_tournament_repairs_stale_pairing(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)

        player_a = User(
            app_state, username=f"{TEST_PREFIX}A", title="TEST", perfs=make_test_perfs()
        )
        player_b = User(
            app_state, username=f"{TEST_PREFIX}B", title="TEST", perfs=make_test_perfs()
        )
        app_state.users[player_a.username] = player_a
        app_state.users[player_b.username] = player_b
        player_a.tournament_sockets[tid] = {None}
        player_b.tournament_sockets[tid] = {None}

        await self.tournament.join(player_a)
        await self.tournament.join(player_b)
        await self.tournament.start(datetime.now(UTC))

        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]

        await app_state.db.game.update_one(
            {"_id": game.id},
            {"$set": {"s": FLAG, "r": "a"}},
        )

        pairing_doc = await app_state.db.tournament_pairing.find_one({"_id": game.id})
        self.assertEqual(pairing_doc["r"], "d")

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertEqual(len(reloaded_tournament.ongoing_games), 0)
        self.assertEqual(reloaded_tournament.nb_games_finished, 1)

        updated_pairing = await reloaded_tournament.app_state.db.tournament_pairing.find_one(
            {"_id": game.id}
        )
        self.assertEqual(updated_pairing["r"], "a")

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_swiss_bye_persisted_across_restart(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=0, rounds=1, minutes=self.SHORT_SWISS_MINUTES
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(3)
        await self.tournament.clock_task

        player_docs = await app_state.db.tournament_player.find({"tid": tid}).to_list(length=10)
        self.assertTrue(any("-" in doc["p"] for doc in player_docs))

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        bye_players = [
            player_data
            for player_data in reloaded_tournament.players.values()
            if "-" in player_data.points
        ]
        self.assertTrue(bye_players)
        for player_data in bye_players:
            self.assertEqual(len(player_data.games), len(player_data.points))
            self.assertTrue(
                any(isinstance(game, ByeGame) for game in player_data.games),
                "ByeGame missing after reload",
            )

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_swiss_bye_pairing_doc_persisted(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(3)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.save_current_round()

        waiting_players = list(self.tournament.waiting_players())
        await Tournament.create_new_pairings(self.tournament, waiting_players)

        bye_doc = await app_state.db.tournament_pairing.find_one({"tid": tid, "s": BYEGAME})
        self.assertIsNotNone(bye_doc)
        assert bye_doc is not None
        self.assertEqual(bye_doc["r"], "d")
        self.assertEqual(bye_doc["u"][0], bye_doc["u"][1])

    async def test_load_tournament_repairs_missing_swiss_bye_point_from_pairing_doc(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(3)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.save_current_round()

        waiting_players = list(self.tournament.waiting_players())
        await Tournament.create_new_pairings(self.tournament, waiting_players)

        bye_user = next(
            user.username for user, pdata in self.tournament.players.items() if "-" in pdata.points
        )
        await app_state.db.tournament_player.update_one(
            {"tid": tid, "uid": bye_user},
            {"$set": {"p": [], "s": 0}},
        )

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        repaired_bye_user = reloaded_tournament.get_player_by_name(bye_user)
        self.assertIsNotNone(repaired_bye_user)
        assert repaired_bye_user is not None
        bye_data = reloaded_tournament.players[repaired_bye_user]
        self.assertEqual(bye_data.points, ["-"])
        self.assertEqual(len(bye_data.games), 1)
        self.assertIsInstance(bye_data.games[0], ByeGame)

        repaired_doc = await reloaded_tournament.app_state.db.tournament_player.find_one(
            {"tid": tid, "uid": bye_user}
        )
        self.assertIsNotNone(repaired_doc)
        assert repaired_doc is not None
        self.assertEqual(repaired_doc["p"], ["-"])
        self.assertEqual(repaired_doc["s"], 2)

    async def test_load_tournament_repairs_swiss_points_from_pairings(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(2)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.save_current_round()

        waiting_players = list(self.tournament.waiting_players())
        _, games = await Tournament.create_new_pairings(self.tournament, waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20
        await self.tournament.game_update(game)

        winner = game.wplayer.username
        await app_state.db.tournament_player.update_one(
            {"tid": tid, "uid": winner},
            {"$set": {"p": [], "s": 0}},
        )

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        repaired_winner = reloaded_tournament.get_player_by_name(winner)
        self.assertIsNotNone(repaired_winner)
        assert repaired_winner is not None
        winner_data = reloaded_tournament.players[repaired_winner]
        self.assertEqual(len(winner_data.games), 1)
        self.assertEqual(winner_data.points[0][0], 2)

        repaired_doc = await reloaded_tournament.app_state.db.tournament_player.find_one(
            {"tid": tid, "uid": winner}
        )
        self.assertIsNotNone(repaired_doc)
        assert repaired_doc is not None
        self.assertEqual(repaired_doc["p"][0][0], 2)
        self.assertEqual(repaired_doc["s"], 2)

    async def test_swiss_unpaired_round_is_persisted_as_zero_point_entry(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=10, rounds=2, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.start(datetime.now(UTC))
        self.tournament.current_round = 1
        await self.tournament.save_current_round()

        absent = list(self.tournament.players.keys())[0]
        await self.tournament.pause(absent)

        waiting_players = list(self.tournament.waiting_players())
        await self.tournament.create_new_pairings(waiting_players)

        absent_data = self.tournament.players[absent]
        self.assertEqual(absent_data.points[-1], (0, 0))
        self.assertIsInstance(absent_data.games[-1], ByeGame)
        self.assertEqual(getattr(absent_data.games[-1], "token", None), "Z")
        self.assertEqual(getattr(absent_data.games[-1], "round", None), 1)

        zero_doc = await app_state.db.tournament_pairing.find_one(
            {"tid": tid, "u.0": absent.username, "u.1": absent.username, "bt": "Z", "rn": 1}
        )
        self.assertIsNotNone(zero_doc)

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        reloaded_absent = reloaded_tournament.get_player_by_name(absent.username)
        self.assertIsNotNone(reloaded_absent)
        assert reloaded_absent is not None
        reloaded_data = reloaded_tournament.players[reloaded_absent]
        self.assertTrue(any(isinstance(game, ByeGame) for game in reloaded_data.games))
        self.assertIn((0, 0), reloaded_data.points)

    async def test_load_tournament_recovers_missing_participant_doc_from_pairings(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)

        winner = User(app_state, username="recover_missing_doc_a", perfs=make_test_perfs())
        missing = User(app_state, username="recover_missing_doc_b", perfs=make_test_perfs())
        app_state.users[winner.username] = winner
        app_state.users[missing.username] = missing
        await app_state.db.user.insert_many(
            [
                {"_id": winner.username, "enabled": True, "security": {}},
                {"_id": missing.username, "enabled": True, "security": {}},
            ]
        )

        await self.tournament.join(winner)
        await self.tournament.join(missing)

        class _DummyWs:
            async def send_json(self, _msg):
                return None

            async def close(self):
                return None

        dummy_ws = _DummyWs()
        winner.tournament_sockets[tid] = {dummy_ws}
        missing.tournament_sockets[tid] = {dummy_ws}
        app_state.tourneysockets[tid][winner.username] = winner.tournament_sockets[tid]
        app_state.tourneysockets[tid][missing.username] = missing.tournament_sockets[tid]
        await self.tournament.start(datetime.now(UTC))

        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20
        await self.tournament.game_update(game)

        await app_state.db.tournament_player.delete_one({"tid": tid, "uid": missing.username})

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None

        recovered = reloaded_tournament.get_player_by_name(missing.username)
        winner_reloaded = reloaded_tournament.get_player_by_name(winner.username)
        self.assertIsNotNone(recovered)
        self.assertIsNotNone(winner_reloaded)
        assert recovered is not None
        assert winner_reloaded is not None

        self.assertEqual(reloaded_tournament.nb_games_finished, 1)
        self.assertIn(recovered, reloaded_tournament.leaderboard)
        recovered_entries = [
            player
            for player in reloaded_tournament.leaderboard
            if player.username == missing.username
        ]
        self.assertEqual(len(recovered_entries), 1)
        self.assertGreaterEqual(len(reloaded_tournament.players[winner_reloaded].games), 1)
        self.assertGreaterEqual(len(reloaded_tournament.players[recovered].games), 1)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_load_tournament_recovers_deleted_user_from_pairings(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTournament(
            app_state, tid, variant="chess", before_start=0, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        app_state.tourneysockets[tid] = {}
        await upsert_tournament_to_db(self.tournament, app_state)

        winner = User(app_state, username="recover_deleted_user_a", perfs=make_test_perfs())
        deleted = User(app_state, username="recover_deleted_user_b", perfs=make_test_perfs())
        app_state.users[winner.username] = winner
        app_state.users[deleted.username] = deleted
        await app_state.db.user.insert_many(
            [
                {"_id": winner.username, "enabled": True, "security": {}},
                {"_id": deleted.username, "enabled": True, "security": {}},
            ]
        )

        await self.tournament.join(winner)
        await self.tournament.join(deleted)

        class _DummyWs:
            async def send_json(self, _msg):
                return None

            async def close(self):
                return None

        dummy_ws = _DummyWs()
        winner.tournament_sockets[tid] = {dummy_ws}
        deleted.tournament_sockets[tid] = {dummy_ws}
        app_state.tourneysockets[tid][winner.username] = winner.tournament_sockets[tid]
        app_state.tourneysockets[tid][deleted.username] = deleted.tournament_sockets[tid]
        await self.tournament.start(datetime.now(UTC))

        waiting_players = list(self.tournament.waiting_players())
        _, games = await self.tournament.create_new_pairings(waiting_players)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20
        await self.tournament.game_update(game)

        await app_state.db.tournament_player.delete_one({"tid": tid, "uid": deleted.username})
        await app_state.db.user.delete_one({"_id": deleted.username})

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)
        self.assertIsNotNone(reloaded_tournament)
        assert reloaded_tournament is not None

        recovered = reloaded_tournament.get_player_by_name(deleted.username)
        winner_reloaded = reloaded_tournament.get_player_by_name(winner.username)
        self.assertIsNotNone(recovered)
        self.assertIsNotNone(winner_reloaded)
        assert recovered is not None
        assert winner_reloaded is not None

        self.assertEqual(recovered.username, deleted.username)
        self.assertEqual(reloaded_tournament.nb_games_finished, 1)
        self.assertIn(recovered, reloaded_tournament.leaderboard)
        recovered_entries = [
            player
            for player in reloaded_tournament.leaderboard
            if player.username == deleted.username
        ]
        self.assertEqual(len(recovered_entries), 1)
        self.assertGreaterEqual(len(reloaded_tournament.players[winner_reloaded].games), 1)
        self.assertGreaterEqual(len(reloaded_tournament.players[recovered].games), 1)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_ongoing_arena_lifecycle_persisted_across_restart(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = ArenaTestTournament(
            app_state, tid, variant="chess", before_start=10, minutes=10, with_clock=False
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        players = list(self.tournament.players.keys())
        withdrawn_player = players[-1]
        paused_player = players[-2]

        await self.tournament.withdraw(withdrawn_player)
        await self.tournament.start(datetime.now(UTC))
        await self.tournament.pause(paused_player)

        waiting_players = list(self.tournament.waiting_players())
        self.assertEqual(len(waiting_players), 2)

        _, games = await self.tournament.create_new_pairings(waiting_players)
        self.assertEqual(len(games), 1)
        game = games[0]
        game.result = "1-0"
        game.status = FLAG
        game.board.ply = 20
        await self.tournament.game_update(game)

        winner_username = game.wplayer.username
        loser_username = game.bplayer.username

        _, reloaded_tournament = await self.reload_tournament(app_state.db_client, tid)

        winner = reloaded_tournament.get_player_by_name(winner_username)
        loser = reloaded_tournament.get_player_by_name(loser_username)
        paused = reloaded_tournament.get_player_by_name(paused_player.username)
        withdrawn = reloaded_tournament.get_player_by_name(withdrawn_player.username)
        self.assertIsNotNone(winner)
        self.assertIsNotNone(loser)
        self.assertIsNotNone(paused)
        self.assertIsNotNone(withdrawn)
        assert winner is not None
        assert loser is not None
        assert paused is not None
        assert withdrawn is not None

        self.assertEqual(reloaded_tournament.nb_games_finished, 1)
        self.assertEqual(reloaded_tournament.players[winner].points[0][0], 2)
        self.assertEqual(reloaded_tournament.players[loser].points[0][0], 0)
        self.assertEqual(reloaded_tournament.get_rank_by_username(winner.username), 1)

        self.assertTrue(reloaded_tournament.players[paused].paused)
        self.assertFalse(reloaded_tournament.players[paused].withdrawn)
        self.assertIn(paused, reloaded_tournament.leaderboard)

        self.assertTrue(reloaded_tournament.players[withdrawn].withdrawn)
        self.assertNotIn(withdrawn, reloaded_tournament.leaderboard)
        self.assertIsNone(reloaded_tournament.get_rank_by_username(withdrawn.username))

        class _DummyWs:
            async def close(self):
                return None

        dummy_ws = _DummyWs()
        for player in reloaded_tournament.players:
            player.tournament_sockets[tid] = {dummy_ws}
            reloaded_tournament.app_state.tourneysockets[tid][player.username] = (
                player.tournament_sockets[tid]
            )

        reloaded_waiting = reloaded_tournament.waiting_players()
        self.assertIn(winner, reloaded_waiting)
        self.assertIn(loser, reloaded_waiting)
        self.assertNotIn(paused, reloaded_waiting)
        self.assertNotIn(withdrawn, reloaded_waiting)

        if reloaded_tournament.clock_task is not None:
            reloaded_tournament.clock_task.cancel()
            try:
                await reloaded_tournament.clock_task
            except asyncio.CancelledError:
                pass

    async def test_finished_tournament_evicted_after_keep_time(self):
        app_state = get_app_state(self.app)
        tid = id8()
        self.tournament = SwissTestTournament(
            app_state, tid, before_start=0, rounds=1, minutes=self.SHORT_SWISS_MINUTES
        )
        app_state.tournaments[tid] = self.tournament
        await upsert_tournament_to_db(self.tournament, app_state)

        await self.tournament.join_players(4)
        await self.tournament.clock_task

        pairing = await app_state.db.tournament_pairing.find_one({"tid": tid, "r": {"$ne": "d"}})
        self.assertIsNotNone(pairing)

        del app_state.tournaments[tid]
        app_state.tourneysockets.pop(tid, None)

        loaded = await load_tournament(app_state, tid)
        self.assertIsNotNone(loaded)
        self.assertGreater(loaded.status, T_STARTED)

        player_data = next(iter(loaded.players.values()))
        self.assertIsInstance(player_data, PlayerData)

        game_data = None
        for pdata in loaded.players.values():
            for game in pdata.games:
                if isinstance(game, GameData):
                    game_data = game
                    break
            if game_data is not None:
                break
        self.assertIsNotNone(game_data)

        # Simulate an already-expired cache entry instead of waiting for the
        # real keep interval. Scheduling behavior has focused coverage in
        # test_cache_cleanup; this test verifies persisted tournaments evict.
        app_state.tournament_cache_access[tid] = monotonic() - TOURNAMENT_KEEP_TIME - 1

        loaded = None
        player_data = None
        game_data = None

        await app_state.remove_tournament_from_cache(tid)
        gc.collect()

        self.assertNotIn(tid, app_state.tournaments)
