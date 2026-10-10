from aiohttp.test_utils import AioHTTPTestCase
from const import ANON_PREFIX, HTTP_ANON_USER
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class PlayersPageAnonymousDisplayTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    async def test_stateless_anonymous_context_is_not_listed_by_name(self):
        response = await self.client.get("/players")

        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertNotIn(f"/@/{HTTP_ANON_USER}", html)

    async def test_patron_wing_is_rendered_on_leaderboards_and_profile(self):
        app_state = get_app_state(self.app)
        patron = User(app_state, username="winged-user", patron=True)
        app_state.users[patron.username] = patron
        app_state.highscore["chess"][f"{patron.username}|"] = 2100

        response = await self.client.get("/players")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('/@/winged-user"', html)
        self.assertIn("offline icon icon-patron-wing", html)

        response = await self.client.get("/players/chess")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('/@/winged-user"', html)
        self.assertIn("offline icon icon-patron-wing", html)

        response = await self.client.get("/@/winged-user")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn("profile-user-status offline icon icon-patron-wing", html)
        self.assertIn('href="/patron"', html)

    async def test_materialized_anonymous_user_is_not_listed_by_name(self):
        app_state = get_app_state(self.app)
        before = set(app_state.users)

        ws = await self.client.ws_connect(
            "/wsl", headers={"Origin": str(self.client.make_url("/")).rstrip("/")}
        )
        try:
            created = [
                name
                for name in app_state.users
                if name not in before and name.startswith(ANON_PREFIX)
            ]
            self.assertEqual(1, len(created))

            response = await self.client.get("/players")
            self.assertEqual(response.status, 200)
            html = await response.text()
            self.assertNotIn(f"/@/{created[0]}", html)
        finally:
            await ws.close()
