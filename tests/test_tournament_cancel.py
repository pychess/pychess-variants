import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import AioHTTPTestCase
from const import T_ABORTED, T_FINISHED, T_STARTED
from mongomock_motor import AsyncMongoMockClient
from newid import id8
from pychess_global_app_state_utils import get_app_state
from tournament.auto_play_tournament import ArenaTestTournament, SwissTestTournament
from tournament.tournament import upsert_tournament_to_db
from user import User

from server import make_app


class TournamentCancelRedirectTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_cancel_created_tournament_redirects_to_tournaments(self):
        app_state = get_app_state(self.app)
        director = User(app_state, username="td-user")
        app_state.users[director.username] = director
        self.set_session_user(director.username)

        tournament_id = id8()
        tournament = SwissTestTournament(app_state, tournament_id, created_by=director.username)
        app_state.tournaments[tournament_id] = tournament

        with patch("views.tournament.is_tournament_director", return_value=True):
            response = await self.client.post(
                f"/tournament/{tournament_id}/cancel",
                allow_redirects=False,
            )

        self.assertEqual(response.status, 302)
        self.assertEqual(response.headers["Location"], "/tournaments")
        self.assertEqual(app_state.tournaments[tournament_id].status, T_ABORTED)

    async def test_site_admin_can_open_another_users_tournament_settings(self):
        app_state = get_app_state(self.app)
        admin = User(app_state, username="site-admin")
        app_state.users[admin.username] = admin
        self.set_session_user(admin.username)

        tournament_id = id8()
        tournament = SwissTestTournament(app_state, tournament_id, created_by="another-user")
        app_state.tournaments[tournament_id] = tournament

        with patch("views.arena_new.ADMINS", (admin.username,)):
            response = await self.client.get(f"/tournaments/{tournament_id}/edit")

        self.assertEqual(response.status, 200)
        self.assertIn('id="tournament-abort"', await response.text())

    async def test_tournament_director_does_not_get_admin_settings_override(self):
        app_state = get_app_state(self.app)
        director = User(app_state, username="td-user")
        app_state.users[director.username] = director
        self.set_session_user(director.username)

        tournament_id = id8()
        tournament = SwissTestTournament(app_state, tournament_id, created_by="another-user")
        app_state.tournaments[tournament_id] = tournament

        with (
            patch("views.arena_new.ADMINS", ()),
            patch("views.arena_new.is_tournament_director", return_value=True),
        ):
            response = await self.client.get(
                f"/tournaments/{tournament_id}/edit",
                allow_redirects=False,
            )

        self.assertEqual(response.status, 404)

    async def test_site_admin_can_abort_started_tournament_from_settings(self):
        app_state = get_app_state(self.app)
        admin = User(app_state, username="site-admin")
        app_state.users[admin.username] = admin
        self.set_session_user(admin.username)

        tournament_id = id8()
        tournament = SimpleNamespace(id=tournament_id, status=T_STARTED, abort=AsyncMock())
        app_state.tournaments[tournament_id] = tournament

        with patch("views.tournaments.ADMINS", (admin.username,)):
            response = await self.client.post(
                f"/tournaments/{tournament_id}/abort",
                allow_redirects=False,
            )

        self.assertEqual(response.status, 302)
        self.assertEqual(response.headers["Location"], f"/tournament/{tournament_id}")
        tournament.abort.assert_awaited_once_with()

    async def test_site_admin_can_delete_finished_arena_without_pairings(self):
        app_state = get_app_state(self.app)
        admin = User(app_state, username="site-admin")
        app_state.users[admin.username] = admin
        self.set_session_user(admin.username)

        tournament_id = id8()
        tournament = ArenaTestTournament(
            app_state,
            tournament_id,
            created_by="spammer",
            with_clock=False,
        )
        app_state.tournaments[tournament_id] = tournament
        app_state.tourneysockets[tournament_id] = {}
        await upsert_tournament_to_db(tournament, app_state)

        player = User(app_state, username="spammer")
        app_state.users[player.username] = player
        player.tournament_sockets[tournament_id] = {None}
        self.assertIsNone(await tournament.join(player))
        tournament.status = T_FINISHED
        await tournament.save()
        await app_state.db.tournament_chat.insert_one(
            {
                "tid": tournament_id,
                "type": "lobbychat",
                "user": player.username,
                "message": "spam",
            }
        )

        with patch("views.arena_new.ADMINS", (admin.username,)):
            settings_response = await self.client.get(f"/tournaments/{tournament_id}/edit")
        self.assertEqual(settings_response.status, 200)
        self.assertIn('id="tournament-delete"', await settings_response.text())

        with patch("views.tournaments.ADMINS", (admin.username,)):
            response = await self.client.post(
                f"/tournaments/{tournament_id}/delete",
                allow_redirects=False,
            )

        self.assertEqual(response.status, 302)
        self.assertEqual(response.headers["Location"], "/tournaments")
        self.assertNotIn(tournament_id, app_state.tournaments)
        self.assertEqual(
            await app_state.db.tournament.count_documents({"_id": tournament_id}),
            0,
        )
        self.assertEqual(
            await app_state.db.tournament_player.count_documents({"tid": tournament_id}),
            0,
        )
        self.assertEqual(
            await app_state.db.tournament_chat.count_documents({"tid": tournament_id}),
            0,
        )

    async def test_site_admin_cannot_delete_arena_with_pairing_history(self):
        app_state = get_app_state(self.app)
        admin = User(app_state, username="site-admin")
        app_state.users[admin.username] = admin
        self.set_session_user(admin.username)

        tournament_id = id8()
        tournament = ArenaTestTournament(
            app_state,
            tournament_id,
            status=T_FINISHED,
            with_clock=False,
        )
        app_state.tournaments[tournament_id] = tournament
        app_state.tourneysockets[tournament_id] = {}
        await upsert_tournament_to_db(tournament, app_state)
        await app_state.db.tournament_pairing.insert_one({"_id": id8(), "tid": tournament_id})

        with patch("views.tournaments.ADMINS", (admin.username,)):
            response = await self.client.post(
                f"/tournaments/{tournament_id}/delete",
                allow_redirects=False,
            )

        self.assertEqual(response.status, 400)
        self.assertIn("without pairings", await response.text())
        self.assertIn(tournament_id, app_state.tournaments)
        self.assertEqual(
            await app_state.db.tournament.count_documents({"_id": tournament_id}),
            1,
        )

    async def test_tournament_director_cannot_use_admin_abort_action(self):
        app_state = get_app_state(self.app)
        director = User(app_state, username="td-user")
        app_state.users[director.username] = director
        self.set_session_user(director.username)

        tournament_id = id8()
        tournament = SimpleNamespace(id=tournament_id, status=T_STARTED, abort=AsyncMock())
        app_state.tournaments[tournament_id] = tournament

        with (
            patch("views.tournaments.ADMINS", ()),
            patch("views.tournaments.is_tournament_director", return_value=True),
        ):
            response = await self.client.post(
                f"/tournaments/{tournament_id}/abort",
                allow_redirects=False,
            )

        self.assertEqual(response.status, 403)
        tournament.abort.assert_not_awaited()

    async def test_tournament_page_exposes_director_permission_to_client(self):
        app_state = get_app_state(self.app)
        director = User(app_state, username="td-user")
        app_state.users[director.username] = director
        self.set_session_user(director.username)

        tournament_id = id8()
        tournament = SwissTestTournament(app_state, tournament_id, created_by="another-user")
        app_state.tournaments[tournament_id] = tournament

        with patch("views.tournament.is_tournament_director", return_value=True):
            response = await self.client.get(f"/tournament/{tournament_id}")

        self.assertEqual(response.status, 200)
        self.assertIn('data-tournamentdirector="True"', await response.text())
