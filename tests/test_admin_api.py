import json
import time
from datetime import UTC, datetime
from unittest.mock import patch

from admin import ban, unban
from aiohttp.test_utils import AioHTTPTestCase
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class AdminApiTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def insert_user(self, username: str, **fields) -> None:
        document = {
            "_id": username,
            "username_lower": username.lower(),
            "enabled": True,
            "shadowban": False,
        }
        document.update(fields)
        await get_app_state(self.app).db.user.insert_one(document)

    async def test_uncached_account_closure_permanently_revokes_cookie(self):
        app_state = get_app_state(self.app)
        await self.insert_user("target", security={"sessionVersion": 0})
        self.set_session_user("target")
        cookie = self.client.session.cookie_jar.filter_cookies(self.client.make_url("/"))[
            "AIOHTTP_SESSION"
        ].value
        self.assertNotIn("target", app_state.users)

        self.assertTrue(await ban(app_state, "target"))
        self.assertNotIn("target", app_state.users)
        doc = await app_state.db.user.find_one({"_id": "target"})
        self.assertEqual(1, doc["security"]["sessionVersion"])
        self.assertTrue(await unban(app_state, "target"))

        self.client.session.cookie_jar.clear()
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": cookie})
        response = await self.client.get("/account", allow_redirects=False)
        self.assertEqual(302, response.status)
        self.assertEqual("/login", response.headers["Location"])

    async def test_user_actions_require_admin(self):
        app_state = get_app_state(self.app)
        app_state.users["alice"] = User(app_state, username="alice")
        await self.insert_user("target")
        self.set_session_user("alice")

        with patch("admin_api.ADMINS", ["mod"]):
            response = await self.client.post("/api/admin/users/target/shadowban")

        self.assertEqual(response.status, 403)
        target = await app_state.db.user.find_one({"_id": "target"})
        self.assertFalse(target["shadowban"])
        self.assertEqual(0, await app_state.db.mod_log.count_documents({}))

    async def test_cross_site_admin_close_is_blocked_before_mutation(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        await self.insert_user("target")
        self.set_session_user("mod")

        with patch("admin_api.ADMINS", ["mod"]), patch("admin.ADMINS", ["mod"]):
            response = await self.client.post(
                "/api/admin/users/target/close",
                headers={
                    "Origin": "https://attacker.example",
                    "Sec-Fetch-Site": "cross-site",
                },
            )

        self.assertEqual(response.status, 403)
        target = await app_state.db.user.find_one({"_id": "target"})
        self.assertTrue(target["enabled"])
        self.assertEqual(0, await app_state.db.mod_log.count_documents({}))

    async def test_protected_accounts_cannot_be_moderated(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        await self.insert_user("othermod")
        await self.insert_user("Fairy-Stockfish")
        self.set_session_user("mod")

        with (
            patch("admin_api.ADMINS", ["mod", "othermod"]),
            patch("admin.ADMINS", ["mod", "othermod"]),
        ):
            other_admin = await self.client.post("/api/admin/users/othermod/close")
            system_user = await self.client.post("/api/admin/users/Fairy-Stockfish/close")

        self.assertEqual(other_admin.status, 403)
        self.assertEqual(system_user.status, 403)
        self.assertEqual(0, await app_state.db.mod_log.count_documents({}))

    async def test_patron_toggle_updates_db_cache_and_allows_protected_target(self):
        app_state = get_app_state(self.app)
        moderator = User(app_state, username="mod")
        target_user = User(app_state, username="othermod")
        app_state.users[moderator.username] = moderator
        app_state.users[target_user.username] = target_user
        await self.insert_user("othermod")
        self.set_session_user("mod")

        with (
            patch("admin_api.ADMINS", ["mod", "othermod"]),
            patch("admin.ADMINS", ["mod", "othermod"]),
        ):
            grant = await self.client.post("/api/admin/users/othermod/patron")
            duplicate = await self.client.post("/api/admin/users/othermod/patron")
            revoke = await self.client.post("/api/admin/users/othermod/unpatron")

        self.assertEqual(grant.status, 200)
        self.assertEqual(duplicate.status, 409)
        self.assertEqual(revoke.status, 200)
        target_doc = await app_state.db.user.find_one({"_id": "othermod"})
        self.assertFalse(target_doc["patron"])
        self.assertFalse(target_user.patron)
        logs = await app_state.db.mod_log.find({"user": "othermod"}).to_list(None)
        self.assertEqual(["grant_patron", "revoke_patron"], [entry["action"] for entry in logs])

    async def test_shadowban_toggle_updates_cache_and_mod_log(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        target_user = User(app_state, username="MixedCase")
        app_state.users[target_user.username] = target_user
        await self.insert_user("MixedCase")
        self.set_session_user("mod")

        with patch("admin_api.ADMINS", ["mod"]), patch("admin.ADMINS", ["mod"]):
            shadow = await self.client.post("/api/admin/users/mixedcase/shadowban")
            duplicate = await self.client.post("/api/admin/users/MixedCase/shadowban")
            unshadow = await self.client.post("/api/admin/users/MixedCase/unshadowban")

        self.assertEqual(shadow.status, 200)
        self.assertEqual(duplicate.status, 409)
        self.assertEqual(unshadow.status, 200)
        target_doc = await app_state.db.user.find_one({"_id": "MixedCase"})
        self.assertFalse(target_doc["shadowban"])
        self.assertFalse(target_user.shadowban)
        logs = await app_state.db.mod_log.find({"user": "MixedCase"}).to_list(None)
        self.assertEqual(["shadowban", "unshadowban"], [entry["action"] for entry in logs])
        self.assertTrue(all(entry["mod"] == "mod" for entry in logs))

    async def test_close_and_reopen_manage_ban_signals_and_mod_log(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        await self.insert_user(
            "target",
            security={
                "ipHashes": ["ip-one"],
                "fpHashes": ["fp-one"],
                "ipfpHashes": ["combined-one"],
            },
        )
        self.set_session_user("mod")

        with patch("admin_api.ADMINS", ["mod"]), patch("admin.ADMINS", ["mod"]):
            close = await self.client.post("/api/admin/users/target/close")
            duplicate = await self.client.post("/api/admin/users/target/close")

            closed = await app_state.db.user.find_one({"_id": "target"})
            active_signals = await app_state.db.security_ban_signal.count_documents({})

            reopen = await self.client.post("/api/admin/users/target/reopen")

        self.assertEqual(close.status, 200)
        self.assertEqual(duplicate.status, 409)
        self.assertFalse(closed["enabled"])
        self.assertEqual(3, active_signals)
        self.assertEqual(reopen.status, 200)
        reopened = await app_state.db.user.find_one({"_id": "target"})
        self.assertTrue(reopened["enabled"])
        self.assertEqual(0, await app_state.db.security_ban_signal.count_documents({}))
        logs = await app_state.db.mod_log.find({"user": "target"}).to_list(None)
        self.assertEqual(
            ["close_account", "reopen_account"],
            [entry["action"] for entry in logs],
        )

    async def test_timeout_works_for_offline_user_and_records_reason(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        await self.insert_user("target")
        self.set_session_user("mod")

        with patch("admin_api.ADMINS", ["mod"]), patch("admin.ADMINS", ["mod"]):
            offline = await self.client.post(
                "/api/admin/users/target/timeout", data={"reason": "spam"}
            )
            duplicate = await self.client.post(
                "/api/admin/users/target/timeout", data={"reason": "spam"}
            )

        self.assertEqual(offline.status, 200)
        self.assertEqual(duplicate.status, 409)
        target_doc = await app_state.db.user.find_one({"_id": "target"})
        self.assertGreater(target_doc["chatTimeoutUntil"], datetime.now(UTC))
        target = await app_state.users.get("target")
        self.assertGreater(target.silence, 0)
        log = await app_state.db.mod_log.find_one({"user": "target"})
        self.assertEqual("chat_timeout", log["action"])
        self.assertEqual("spamming the chat", log["details"])


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2)
