from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

from aiohttp.test_utils import AioHTTPTestCase
from bot_accounts import ENGINE_TOKEN_SCOPES, create_bot_token, revoke_bot_token
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class ExternalEngineApiTest(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    async def create_owner(self, name="alice"):
        state = get_app_state(self.app)
        user = User(state, username=name)
        state.users[name] = user
        await state.db.user.insert_one({"_id": name, "username_lower": name, "enabled": True})
        token_id, token = await create_bot_token(
            state, name, "My computer", scopes=ENGINE_TOKEN_SCOPES
        )
        return token_id, token

    def session_user(self, name):
        self.client.session.cookie_jar.clear()
        self.client.session.cookie_jar.update_cookies(
            {
                "AIOHTTP_SESSION": json.dumps(
                    {
                        "session": {"user_name": name},
                        "created": int(time.time()),
                    }
                )
            }
        )

    @staticmethod
    def headers(token):
        return {"Authorization": "Bearer " + token}

    @staticmethod
    def registration(**updates):
        return {
            "protocolVersion": 1,
            "instanceId": "instance_" + "x" * 32,
            "address": "http://127.0.0.1:9670",
            "clientSecret": "local_" + "y" * 40,
            "engine": {
                "name": "Any UCI engine",
                "variants": ["chess"],
                "chess960": True,
                "customRules": False,
                "maxThreads": 2,
                "maxHash": 64,
                "maxMultiPv": 2,
            },
            **updates,
        }

    async def register(self, token, body=None):
        return await self.client.post(
            "/api/external-engine", headers=self.headers(token), json=body or self.registration()
        )

    async def test_regular_account_can_create_engine_token_without_bot_upgrade(self):
        state = get_app_state(self.app)
        await self.create_owner()
        self.session_user("alice")
        response = await self.client.post(
            "/account/engines/token/create", data={"description": "Laptop"}, allow_redirects=False
        )
        self.assertEqual(response.status, 302)
        page = await self.client.get("/account/engines")
        self.assertIn("New token", await page.text())
        self.assertNotIn("New token", await (await self.client.get("/account/engines")).text())
        doc = await state.db.bot_token.find_one({"description": "Laptop"})
        self.assertEqual(doc["scopes"], list(ENGINE_TOKEN_SCOPES))
        self.assertNotEqual((await state.db.user.find_one({"_id": "alice"})).get("title"), "BOT")
        self.client.session.cookie_jar.clear()
        self.assertEqual(
            (await self.client.get("/account/engines", allow_redirects=False)).status, 302
        )

    async def test_engine_scope_cannot_play_or_upgrade_bots_and_bot_scope_cannot_register(self):
        token_id, token = await self.create_owner()
        for path, method in (("/api/account", "get"), ("/api/bot/account/upgrade", "post")):
            response = await getattr(self.client, method)(path, headers=self.headers(token))
            self.assertEqual(response.status, 403)
        state = get_app_state(self.app)
        _, bot_token = await create_bot_token(state, "alice", "Bot")
        self.assertEqual((await self.register(bot_token)).status, 403)
        tested = await self.client.post("/api/token/test", data=token)
        self.assertEqual((await tested.json())[token]["scopes"], "engine:read,engine:write")
        self.assertEqual((await self.register(token)).status, 200)
        self.assertEqual(
            (await state.db.external_engine.find_one({"_id": token_id}))["user"], "alice"
        )

    async def test_discovery_is_owner_only_uncached_and_account_token_is_never_returned(self):
        _, token = await self.create_owner()
        _, other = await self.create_owner("bob")
        self.assertEqual((await self.register(token)).status, 200)
        self.assertEqual((await self.client.get("/api/external-engine")).status, 401)
        response = await self.client.get("/api/external-engine", headers=self.headers(other))
        self.assertEqual(await response.json(), [])
        self.session_user("alice")
        response = await self.client.get("/api/external-engine")
        data = await response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["engine"]["name"], "Any UCI engine")
        self.assertEqual(data[0]["token"], self.registration()["clientSecret"])
        # Bearer discovery is metadata-only, even for a combined read/write token.
        bearer_response = await self.client.get("/api/external-engine", headers=self.headers(token))
        bearer_data = await bearer_response.json()
        self.assertEqual(bearer_data[0]["engine"], data[0]["engine"])
        self.assertNotIn("token", bearer_data[0])
        self.assertNotIn(self.registration()["clientSecret"], json.dumps(bearer_data))
        self.assertNotIn(token, json.dumps(data))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(
            (
                await self.client.get(
                    "/api/external-engine", headers={"Origin": "https://evil.example"}
                )
            ).status,
            403,
        )

    async def test_read_only_token_lists_metadata_without_disclosing_secret(self):
        _, registration_token = await self.create_owner()
        self.assertEqual((await self.register(registration_token)).status, 200)
        state = get_app_state(self.app)
        _, read_token = await create_bot_token(
            state, "alice", "Read-only engine discovery", scopes=("engine:read",)
        )
        response = await self.client.get("/api/external-engine", headers=self.headers(read_token))
        self.assertEqual(response.status, 200)
        registrations = await response.json()
        self.assertEqual(len(registrations), 1)
        self.assertEqual(registrations[0]["engine"], self.registration()["engine"])
        self.assertNotIn("token", registrations[0])
        self.assertNotIn(self.registration()["clientSecret"], json.dumps(registrations))
        self.assertEqual((await self.register(read_token)).status, 403)

    async def test_legacy_bot_tokens_keep_their_original_scope(self):
        await self.create_owner()
        state = get_app_state(self.app)
        token_id, token = await create_bot_token(state, "alice", "Legacy")
        await state.db.bot_token.update_one({"_id": token_id}, {"$unset": {"scopes": ""}})
        self.assertEqual(
            (await self.client.get("/api/account", headers=self.headers(token))).status, 200
        )
        self.assertEqual((await self.register(token)).status, 403)

    async def test_restart_replaces_credentials_and_old_instance_cannot_renew_or_remove(self):
        token_id, token = await self.create_owner()
        self.assertEqual((await self.register(token)).status, 200)
        replacement = self.registration(
            instanceId="replacement_" + "z" * 32, clientSecret="new_" + "n" * 40
        )
        self.assertEqual((await self.register(token, replacement)).status, 200)
        path = "/api/external-engine/" + token_id
        old = {"instanceId": self.registration()["instanceId"]}
        self.assertEqual(
            (
                await self.client.post(path + "/heartbeat", headers=self.headers(token), json=old)
            ).status,
            409,
        )
        self.assertEqual(
            (await self.client.post(path + "/stop", headers=self.headers(token), json=old)).status,
            200,
        )
        response = await self.client.get("/api/external-engine", headers=self.headers(token))
        self.assertNotIn("token", (await response.json())[0])
        self.session_user("alice")
        session_response = await self.client.get("/api/external-engine")
        self.assertEqual((await session_response.json())[0]["token"], replacement["clientSecret"])

    async def test_revoked_disabled_and_expired_registrations_are_unavailable(self):
        token_id, token = await self.create_owner()
        state = get_app_state(self.app)
        await self.register(token)
        await state.db.external_engine.update_one(
            {"_id": token_id}, {"$set": {"expiresAt": datetime.now(UTC) - timedelta(seconds=1)}}
        )
        self.assertEqual(
            await (
                await self.client.get("/api/external-engine", headers=self.headers(token))
            ).json(),
            [],
        )
        await self.register(token)
        await revoke_bot_token(state, "alice", token_id)
        self.assertEqual((await self.register(token)).status, 403)
        self.assertIsNone(await state.db.external_engine.find_one({"_id": token_id}))
        _, valid = await create_bot_token(state, "alice", "Second", scopes=ENGINE_TOKEN_SCOPES)
        await state.db.user.update_one({"_id": "alice"}, {"$set": {"enabled": False}})
        self.assertEqual((await self.register(valid)).status, 403)

    async def test_browser_removal_is_owner_only_and_stops_renewal(self):
        token_id, token = await self.create_owner()
        await self.create_owner("bob")
        await self.register(token)
        path = "/api/external-engine/" + token_id
        self.session_user("bob")
        self.assertEqual((await self.client.post(path + "/delete")).status, 404)
        self.session_user("alice")
        self.assertEqual(
            (
                await self.client.post(path + "/delete", headers={"Origin": "https://evil.example"})
            ).status,
            403,
        )
        self.assertEqual((await self.client.post(path + "/delete")).status, 200)
        self.client.session.cookie_jar.clear()
        response = await self.client.post(
            path + "/heartbeat",
            headers=self.headers(token),
            json={"instanceId": self.registration()["instanceId"]},
        )
        self.assertEqual(response.status, 409)

    async def test_registration_rejects_remote_addresses_bad_capabilities_and_oversized_bodies(
        self,
    ):
        _, token = await self.create_owner()
        for address in (
            "http://localhost:9670",
            "https://127.0.0.1:9670",
            "http://evil.example",
            "http://127.0.0.1:0",
            "http://user@127.0.0.1:9670",
            "http://127.0.0.1:9670/path",
        ):
            self.assertEqual(
                (await self.register(token, self.registration(address=address))).status, 400
            )
        for engine in (
            None,
            {**self.registration()["engine"], "maxThreads": True},
            {**self.registration()["engine"], "adapters": {}},
        ):
            self.assertEqual(
                (await self.register(token, self.registration(engine=engine))).status, 400
            )
        self.assertEqual(
            (await self.register(token, self.registration(padding="x" * 100000))).status, 413
        )

    async def test_registration_preserves_one_engine_with_variant_restrictions(self):
        _, token = await self.create_owner()
        engine = {
            **self.registration()["engine"],
            "variants": ["chess", "alice"],
            "customRules": True,
            "variantRestrictions": {"alice": {"chess960": False, "customRules": False}},
        }
        self.assertEqual((await self.register(token, self.registration(engine=engine))).status, 200)
        registrations = await (
            await self.client.get("/api/external-engine", headers=self.headers(token))
        ).json()
        self.assertEqual(registrations[0]["engine"], engine)

    async def test_variant_restrictions_are_bounded_boolean_reductions(self):
        _, token = await self.create_owner()
        engine = {**self.registration()["engine"], "customRules": True}
        for restrictions in (
            None,
            [],
            {"unknown": {"chess960": False, "customRules": False}},
            {"chess": {"chess960": "false", "customRules": False}},
            {"chess": {"chess960": False}},
            {"chess": {"chess960": False, "customRules": False, "name": "Other engine"}},
            {"chess": {"chess960": False, "customRules": False, "maxThreads": 1}},
        ):
            with self.subTest(restrictions=restrictions):
                self.assertEqual(
                    (
                        await self.register(
                            token,
                            self.registration(
                                engine={**engine, "variantRestrictions": restrictions}
                            ),
                        )
                    ).status,
                    400,
                )
        for key in ("chess960", "customRules"):
            self.assertEqual(
                (
                    await self.register(
                        token,
                        self.registration(
                            engine={
                                **engine,
                                key: False,
                                "variantRestrictions": {
                                    "chess": {
                                        "chess960": key == "chess960",
                                        "customRules": key == "customRules",
                                    }
                                },
                            }
                        ),
                    )
                ).status,
                400,
            )
