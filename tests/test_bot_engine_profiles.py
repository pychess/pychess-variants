import json
from typing import Any, cast

from aiohttp.test_utils import AioHTTPTestCase
from bot_accounts import create_bot_token
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state

from server import make_app


class BotEngineProfilesTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=cast(Any, AsyncMongoMockClient(tz_aware=True)))

    async def setUpAsync(self):
        await super().setUpAsync()
        self.state = get_app_state(self.app)
        await self.state.db.user.insert_one(
            {"_id": "engine-demo", "title": "BOT", "enabled": True, "perfs": {}}
        )
        self.bot = await self.state.users.get("engine-demo")
        _, self.token = await create_bot_token(self.state, "engine-demo", "Test engine profile")

    async def tearDownAsync(self):
        await self.client.close()

    async def connect(self, engine=None):
        capabilities = {"version": 1, "variants": ["alice"]}
        if engine is not None:
            capabilities["engine"] = engine
        self.bot.event_queue.put_nowait(None)
        response = await self.client.get(
            "/api/stream/event",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-PyChess-Bot-Capabilities": json.dumps(capabilities),
            },
        )
        self.assertEqual(response.status, 200)
        await response.read()

    async def test_engine_identity_is_saved_and_shown_on_live_and_offline_profiles(self):
        identity = {
            "name": "Alice-Stockfish 1.0",
            "author": "Belzedar94 and the Stockfish developers (see AUTHORS file)",
        }
        await self.connect(identity)

        doc = await self.state.db.user.find_one({"_id": self.bot.username})
        self.assertEqual(identity, doc["botEngine"])
        live = await self.state.public_users.get_profile(self.bot.username)
        self.assertEqual(identity, live.bot_engine)
        response = await self.client.get("/@/engine-demo")
        html = await response.text()
        self.assertIn(identity["name"], html)
        self.assertIn(identity["author"], html)
        self.assertIn('class="player-engine"', html)

        del self.state.users[self.bot.username]
        self.state.public_users.invalidate(self.bot.username)
        offline = await self.state.public_users.get_profile(self.bot.username)
        self.assertEqual(identity, offline.bot_engine)
        response = await self.client.get("/@/engine-demo")
        self.assertIn(identity["name"], await response.text())

        reloaded = await self.state.users.get(self.bot.username)
        self.assertEqual(identity, reloaded.bot_engine)

    async def test_legacy_client_has_no_engine_row(self):
        await self.connect()
        response = await self.client.get("/@/engine-demo")
        self.assertNotIn('class="player-engine"', await response.text())
        self.assertIsNone(self.bot.bot_engine)

    async def test_legacy_reconnect_preserves_last_reported_identity(self):
        identity = {"name": "Alice-Stockfish 1.0"}
        await self.connect(identity)
        await self.connect()
        self.assertEqual(identity, self.bot.bot_engine)

    async def test_new_engine_replaces_previous_identity(self):
        await self.connect({"name": "Old engine", "author": "Old author"})
        await self.connect({"name": "New engine"})
        doc = await self.state.db.user.find_one({"_id": self.bot.username})
        self.assertEqual({"name": "New engine"}, doc["botEngine"])
        self.assertEqual({"name": "New engine"}, self.bot.bot_engine)

    async def test_invalid_optional_identity_does_not_prevent_connecting(self):
        for identity in ([], "engine", {"name": []}, {"name": " \n ", "author": "Author"}):
            with self.subTest(identity=identity):
                await self.connect(identity)
                self.assertIsNone(self.bot.bot_engine)

    async def test_identity_is_bounded_and_only_public_fields_are_stored(self):
        await self.connect(
            {"name": " N " + "x" * 200, "author": "A\n" + "y" * 400, "path": "/private/path"}
        )
        self.assertEqual(128, len(self.bot.bot_engine["name"]))
        self.assertEqual(256, len(self.bot.bot_engine["author"]))
        self.assertTrue(self.bot.bot_engine["name"].startswith("N "))
        self.assertTrue(self.bot.bot_engine["author"].startswith("A "))
        self.assertNotIn("path", self.bot.bot_engine)

    async def test_engine_strings_are_escaped_in_profile_html(self):
        identity = {"name": '<img src=x onerror="alert(1)">', "author": "<script>bad()</script>"}
        await self.connect(identity)
        response = await self.client.get("/@/engine-demo")
        html = await response.text()
        self.assertIn("&lt;img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn(identity["name"], html)
        self.assertNotIn(identity["author"], html)

    async def test_engine_metadata_is_not_rendered_on_human_profiles(self):
        await self.state.db.user.insert_one(
            {"_id": "human-demo", "title": "", "botEngine": {"name": "Not an engine BOT"}}
        )
        response = await self.client.get("/@/human-demo")
        html = await response.text()
        self.assertNotIn('class="player-engine"', html)
        self.assertNotIn("Not an engine BOT", html)
