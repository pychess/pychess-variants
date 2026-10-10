import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from aiohttp.test_utils import AioHTTPTestCase
from const import ARENA, T_CREATED
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class SessionMutationTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    async def asyncSetUp(self):
        await super().asyncSetUp()
        app_state = get_app_state(self.app)
        self.user = User(app_state, username="alice")
        app_state.users[self.user.username] = self.user
        session_data = {"session": {"user_name": "alice"}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})
        self.origin = str(self.client.make_url("/")).rstrip("/")

    async def test_mutations_reject_get_and_cross_site_post(self):
        for path in (
            "/tournament/abcd1234/cancel",
            "/tournament/abcd1234/pause",
            "/simul/abcd1234/cancel",
            "/notified",
        ):
            with self.subTest(path=path):
                response = await self.client.get(path, allow_redirects=False)
                # /notified also matches the eight-character game-page route.
                self.assertEqual(404 if path == "/notified" else 405, response.status)
                response = await self.client.post(
                    path,
                    headers={"Origin": "https://attacker.test", "Sec-Fetch-Site": "cross-site"},
                    allow_redirects=False,
                )
                self.assertEqual(403, response.status)

    async def test_same_origin_tournament_cancel_and_pause(self):
        tournament = SimpleNamespace(
            variant="chess",
            frequency="",
            team_id=None,
            system=ARENA,
            status=T_CREATED,
            abort=AsyncMock(),
            pause=AsyncMock(),
            get_player_by_name=Mock(return_value=self.user),
        )
        with (
            patch("views.tournament.load_tournament", AsyncMock(return_value=tournament)),
            patch("views.tournament.creator_can_manage_tournament", AsyncMock(return_value=True)),
        ):
            for action, destination in (
                ("cancel", "/tournaments"),
                ("pause", "/tournament/abcd1234"),
            ):
                response = await self.client.post(
                    f"/tournament/abcd1234/{action}",
                    headers={"Origin": self.origin},
                    allow_redirects=False,
                )
                self.assertEqual(302, response.status)
                self.assertEqual(destination, response.headers["Location"])
        tournament.abort.assert_awaited_once_with()
        tournament.pause.assert_awaited_once_with(self.user)

    async def test_same_origin_simul_cancel(self):
        simul = SimpleNamespace(
            id="abcd1234", created_by=self.user.username, status=T_CREATED, abort=AsyncMock()
        )
        with (
            patch("views.simul.get_simul_for_request", AsyncMock(return_value=simul)),
            patch("views.simul.delete_simul_from_db", AsyncMock()) as delete,
        ):
            response = await self.client.post(
                "/simul/abcd1234/cancel",
                headers={"Origin": self.origin},
                allow_redirects=False,
            )
        self.assertEqual(302, response.status)
        self.assertEqual("/simul", response.headers["Location"])
        simul.abort.assert_awaited_once_with()
        delete.assert_awaited_once()

    async def test_same_origin_notifications_acknowledgement(self):
        with patch.object(self.user, "notified", AsyncMock()) as notified:
            response = await self.client.post("/notified", headers={"Origin": self.origin})
        self.assertEqual(200, response.status)
        notified.assert_awaited_once_with()
