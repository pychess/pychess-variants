from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp.web_ws import WebSocketResponse
from const import SHIELD, T_FINISHED
from glicko2.glicko2 import new_default_perf_map
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from session_security import GAMEPLAY_EXPIRY_GRACE_KEY
from tournament.arena import ArenaTournament
from tournament.rr import RRTournament
from tournament.tournament import upsert_tournament_to_db
from tournament.wst import finally_logic, handle_join, handle_rr_set_time, handle_user_connected
from user import User
from variants import VARIANTS

from server import make_app

test_logger.init_test_logger()

PERFS = new_default_perf_map(VARIANTS)


class TournamentSocketCleanupTestCase(AioHTTPTestCase):
    async def startup(self, app):
        app_state = get_app_state(self.app)
        self.user = User(app_state, username="aplayer", perfs=PERFS)
        app_state.users[self.user.username] = self.user

    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        app.on_startup.append(self.startup)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def test_finally_logic_handles_missing_tournament(self):
        app_state = get_app_state(self.app)
        tournament_id = "missingTourney"
        ws = object()

        self.user.tournament_sockets[tournament_id] = {ws}
        app_state.tourneysockets[tournament_id] = {
            self.user.username: self.user.tournament_sockets[tournament_id]
        }

        # Simulate tournament already gone from cache/database.
        app_state.tournaments.pop(tournament_id, None)
        await app_state.db.tournament.delete_many({"_id": tournament_id})

        await finally_logic(app_state, ws, self.user)

        self.assertNotIn(tournament_id, self.user.tournament_sockets)
        self.assertNotIn(self.user.username, app_state.tourneysockets[tournament_id])

    async def test_rr_set_time_normalizes_offset_and_rejects_invalid_date(self):
        app_state = get_app_state(self.app)
        ws = SimpleNamespace(send_str=AsyncMock())
        tournament = SimpleNamespace(set_arrangement_time=AsyncMock(return_value=None))

        with patch("tournament.wst.load_rr_tournament", new=AsyncMock(return_value=tournament)):
            await handle_rr_set_time(
                app_state,
                ws,
                self.user,
                {
                    "type": "rr_set_time",
                    "tournamentId": "tid",
                    "arrangementId": "arr",
                    "date": "2026-08-22T16:30:00+02:00",
                },
            )

            tournament.set_arrangement_time.assert_awaited_once_with(
                self.user, "arr", datetime(2026, 8, 22, 14, 30, tzinfo=UTC)
            )
            tournament.set_arrangement_time.reset_mock()

            await handle_rr_set_time(
                app_state,
                ws,
                self.user,
                {
                    "type": "rr_set_time",
                    "tournamentId": "tid",
                    "arrangementId": "arr",
                    "date": "not-a-date",
                },
            )

        tournament.set_arrangement_time.assert_not_awaited()
        self.assertIn("Invalid round-robin schedule date", ws.send_str.call_args.args[0])

    async def test_bot_user_cannot_join_tournament(self):
        app_state = get_app_state(self.app)
        bot_user = User(app_state, bot=True, username="bot-tourney", perfs=PERFS)
        ws = SimpleNamespace(send_str=AsyncMock())
        tournament = SimpleNamespace(
            join=AsyncMock(return_value="BOT accounts cannot join tournaments.")
        )

        with patch("tournament.wst.load_tournament", new=AsyncMock(return_value=tournament)):
            await handle_join(app_state, ws, bot_user, {"type": "join", "tournamentId": "tid"})

        tournament.join.assert_awaited_once_with(bot_user, None)
        self.assertIn("BOT accounts cannot join tournaments", ws.send_str.call_args.args[0])

    async def test_expired_creator_reconnect_does_not_send_management_payload(self):
        app_state = get_app_state(self.app)
        tid = "tour1234"
        tournament = RRTournament(app_state, tid, before_start=10, with_clock=False)
        app_state.tournaments[tid] = tournament
        app_state.tourneysockets[tid] = {}
        ws = WebSocketResponse()
        ws.send_str = AsyncMock()
        ws.close = AsyncMock(return_value=True)
        ws[GAMEPLAY_EXPIRY_GRACE_KEY] = True
        with (
            patch("tournament.wst.creator_can_manage_tournament", AsyncMock(return_value=True)),
            patch.object(tournament, "rr_management_payload") as management,
        ):
            await handle_user_connected(
                app_state,
                ws,
                self.user,
                {
                    "type": "tournament_user_connected",
                    "tournamentId": tid,
                },
            )
        management.assert_not_called()
        self.assertIn('"creatorCanManage":false', ws.send_str.call_args_list[0].args[0])

    async def test_archived_shield_without_owner_sends_full_connection_payload(self):
        app_state = get_app_state(self.app)
        for variant, chess960 in (("shinobi", False), ("chess", False), ("chess", True)):
            with self.subTest(variant=variant, chess960=chess960):
                variant_name = variant + ("960" if chess960 else "")
                tid = "old-" + variant_name
                tournament = ArenaTournament(
                    app_state,
                    tid,
                    variant=variant,
                    chess960=chess960,
                    starts_at=datetime(2021, 12, 16, 16, tzinfo=UTC),
                    status=T_FINISHED,
                    frequency=SHIELD,
                    description="Archived Shield tournament",
                    with_clock=False,
                )
                await upsert_tournament_to_db(tournament, app_state)
                app_state.shield_owners.pop(variant_name, None)
                self.assertNotIn(tid, app_state.tournaments)

                async with self.client.ws_connect(
                    "/wst", headers={"Origin": str(self.client.make_url("/")).rstrip("/")}
                ) as ws:
                    await ws.send_json({"type": "tournament_user_connected", "tournamentId": tid})
                    connected = await ws.receive_json(timeout=2)
                    self.assertEqual(connected["type"], "tournament_user_connected")
                    self.assertEqual(connected["tstatus"], T_FINISHED)
                    self.assertEqual(connected["description"], tournament.description)
                    self.assertNotIn("defender_name", connected)
                    self.assertNotIn("defender_title", connected)
                    for expected_type in ("tstatus", "fullchat", "duels"):
                        message = await ws.receive_json(timeout=2)
                        self.assertEqual(message["type"], expected_type)

                self.assertEqual(app_state.tournaments[tid].variant, variant)
                self.assertNotIn(variant_name, app_state.shield_owners)

    async def test_shield_connection_includes_current_owner_for_variant(self):
        app_state = get_app_state(self.app)
        for chess960 in (False, True):
            with self.subTest(chess960=chess960):
                variant_name = "chess960" if chess960 else "chess"
                defender = User(app_state, username="owner-" + variant_name, title="GM")
                app_state.users[defender.username] = defender
                app_state.shield_owners[variant_name] = defender.username
                tid = "shield-" + variant_name
                tournament = ArenaTournament(
                    app_state,
                    tid,
                    variant="chess",
                    chess960=chess960,
                    frequency=SHIELD,
                    with_clock=False,
                )
                app_state.tournaments[tid] = tournament
                app_state.tourneysockets[tid] = {}
                ws = WebSocketResponse()
                ws.send_str = AsyncMock()
                ws.close = AsyncMock(return_value=True)
                with patch("tournament.wst.ws_send_json", new=AsyncMock()) as send:
                    await handle_user_connected(
                        app_state,
                        ws,
                        self.user,
                        {"type": "tournament_user_connected", "tournamentId": tid},
                    )

                connected = send.call_args_list[0].args[1]
                self.assertEqual(connected["defender_name"], defender.username)
                self.assertEqual(connected["defender_title"], defender.title)
