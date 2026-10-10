import json
import time
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import AioHTTPTestCase
from csrf import ALLOW_ORIGINLESS_LOOPBACK_KEY
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class AccountDeletionSecurityTestCase(AioHTTPTestCase):
    async def get_application(self):
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)
        app[ALLOW_ORIGINLESS_LOOPBACK_KEY] = False
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.app_state = get_app_state(self.app)
        for username in ("alice", "mod", "othermod"):
            self.app_state.users[username] = User(self.app_state, username=username)
            await self.app_state.db.user.insert_one({"_id": username, "enabled": True})
        self.origin = str(self.client.make_url("/")).rstrip("/")
        self.enterContext(patch("admin_api.ADMINS", ["mod", "othermod"]))
        self.enterContext(patch("admin.ADMINS", ["mod", "othermod"]))
        self.set_session("alice")

    def set_session(self, username, **extra):
        self.client.session.cookie_jar.clear()
        self.client.session.cookie_jar.update_cookies(
            {
                "AIOHTTP_SESSION": json.dumps(
                    {"session": {"user_name": username, **extra}, "created": int(time.time())}
                )
            }
        )

    async def admin_delete(self, target="alice", **overrides):
        form = {"confirm_username": target, "understand": "on", "verified_request": "on"}
        form.update(overrides)
        return await self.client.post(
            f"/api/admin/users/{target}/delete",
            data=form,
            headers={"Origin": self.origin},
            allow_redirects=False,
        )

    async def test_self_service_page_and_post_never_authorize_erasure(self):
        for extra in (
            {},
            {"account_deletion_reauth": {"username": "alice", "verified_at": int(time.time())}},
        ):
            self.set_session("alice", **extra)
            page = await self.client.get("/account/delete")
            body = await page.text()
            self.assertIn("Contact site admins", body)
            self.assertNotIn('action="/account/delete"', body)
            self.assertNotIn('action="/account/delete/verify"', body)
            with patch("account_api._scrub_delete_owned_data", AsyncMock()) as scrub:
                response = await self.client.post(
                    "/account/delete",
                    data={"confirm_username": "alice", "understand": "on"},
                    headers={"Origin": self.origin},
                    allow_redirects=False,
                )
            self.assertEqual(403, response.status)
            scrub.assert_not_awaited()
            self.assertTrue((await self.app_state.db.user.find_one({"_id": "alice"}))["enabled"])

    async def test_old_verification_route_is_removed(self):
        response = await self.client.post("/account/delete/verify", headers={"Origin": self.origin})
        self.assertEqual(404, response.status)

    async def test_admin_erasure_requires_admin_and_explicit_verified_request(self):
        self.assertEqual(403, (await self.admin_delete()).status)
        self.set_session("mod")
        for changes in ({"confirm_username": "bob"}, {"understand": ""}, {"verified_request": ""}):
            with self.subTest(changes=changes):
                self.assertEqual(400, (await self.admin_delete(**changes)).status)
        self.assertTrue((await self.app_state.db.user.find_one({"_id": "alice"}))["enabled"])
        self.assertEqual(0, await self.app_state.db.mod_log.count_documents({}))

    async def test_admin_erasure_is_csrf_protected_and_post_only(self):
        self.set_session("mod")
        for headers in ({"Origin": "https://attacker.test"}, {}):
            response = await self.client.post("/api/admin/users/alice/delete", headers=headers)
            self.assertEqual(403, response.status)
        response = await self.client.get("/api/admin/users/alice/delete", allow_redirects=False)
        self.assertEqual(405, response.status)
        self.assertTrue((await self.app_state.db.user.find_one({"_id": "alice"}))["enabled"])

    async def test_admin_erasure_protects_admin_accounts_and_missing_targets(self):
        self.set_session("mod")
        self.assertEqual(403, (await self.admin_delete("othermod")).status)
        await self.app_state.db.user.insert_one({"_id": "Fairy-Stockfish", "enabled": True})
        self.assertEqual(403, (await self.admin_delete("Fairy-Stockfish")).status)
        self.assertEqual(404, (await self.admin_delete("missing")).status)

    async def test_verified_erasure_revokes_target_not_admin_and_is_audited(self):
        self.set_session("mod")
        with patch("account_api._scrub_delete_owned_data", AsyncMock()) as scrub:
            response = await self.admin_delete()
        self.assertEqual(200, response.status)
        scrub.assert_awaited_once()
        self.assertFalse(self.app_state.users["alice"].enabled)
        self.assertEqual(1, self.app_state.users["alice"].auth_version)
        self.assertTrue(self.app_state.users["mod"].enabled)
        self.assertEqual(0, self.app_state.users["mod"].auth_version)
        self.assertEqual(200, (await self.client.get("/account")).status)
        logs = await self.app_state.db.mod_log.find({"user": "alice"}).to_list(None)
        self.assertEqual(
            ["account_erasure_requested", "delete_account"], [entry["action"] for entry in logs]
        )
        self.assertTrue(all(entry["mod"] == "mod" for entry in logs))
        self.assertEqual(409, (await self.admin_delete()).status)

    async def test_admin_session_revoked_during_body_read_cannot_erase(self):
        self.set_session("mod")

        async def read_and_revoke(_request):
            self.app_state.users["mod"].auth_version += 1
            return {"confirm_username": "alice", "understand": "on", "verified_request": "on"}

        with patch("admin_api.read_post_data", side_effect=read_and_revoke):
            response = await self.admin_delete()
        self.assertEqual(401, response.status)
        self.assertTrue((await self.app_state.db.user.find_one({"_id": "alice"}))["enabled"])
