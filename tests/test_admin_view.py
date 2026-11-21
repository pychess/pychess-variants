import json
import time
from datetime import UTC, datetime
from unittest.mock import patch

from aiohttp.test_utils import AioHTTPTestCase
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from user import User

from server import make_app


class AdminViewTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True), simple_cookie_storage=True)

    async def tearDownAsync(self):
        await self.client.close()

    def set_session_user(self, username: str) -> None:
        session_data = {"session": {"user_name": username}, "created": int(time.time())}
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": json.dumps(session_data)})

    async def test_admin_pages_reject_non_admin(self):
        app_state = get_app_state(self.app)
        app_state.users["alice"] = User(app_state, username="alice")
        self.set_session_user("alice")

        with patch("views.admin.ADMINS", ["mod"]):
            overview = await self.client.get("/admin")
            users = await self.client.get("/admin/users")
            fair_play = await self.client.get("/admin/fair-play")

        self.assertEqual(overview.status, 403)
        self.assertEqual(users.status, 403)
        self.assertEqual(fair_play.status, 403)

    async def test_admin_overview_renders_shared_navigation(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        self.set_session_user("mod")

        with patch("views.admin.ADMINS", ["mod"]):
            response = await self.client.get("/admin")

        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn("Administration", body)
        self.assertIn('href="/reports?status=open"', body)
        self.assertIn('href="/mod/public-chat"', body)
        self.assertIn('href="/admin/users"', body)
        self.assertIn("admin.css", body)

    async def test_fair_play_requires_admin_and_filters_reports(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        await app_state.db.cheat_report.insert_many(
            [
                {
                    "kind": "external_overlay",
                    "gameId": "abcdefgh",
                    "suspect": "Alice",
                    "opponent": "Bob",
                    "variant": "chess",
                    "ply": 12,
                    "createdAt": datetime(2026, 10, 22, tzinfo=UTC),
                },
                {
                    "kind": "ceval_cross_tab",
                    "gameId": "ijklmnop",
                    "suspect": "Carol",
                    "opponent": "Dave",
                    "variant": "alice",
                    "ply": 16,
                    "createdAt": datetime(2026, 10, 21, tzinfo=UTC),
                },
                {
                    "kind": "other",
                    "gameId": "qrstuvwx",
                    "suspect": "Alice",
                    "createdAt": datetime(2026, 10, 20, tzinfo=UTC),
                },
            ]
        )
        self.set_session_user("mod")
        with patch("views.admin.ADMINS", ["mod"]):
            response = await self.client.get(
                "/admin/fair-play?kind=external_overlay&username=alice"
            )
        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn('href="/abcdefgh"', body)
        self.assertIn('href="/@/Alice"', body)
        self.assertNotIn('href="/ijklmnop"', body)
        self.assertNotIn('href="/qrstuvwx"', body)

    async def test_overlay_download_is_attachment_and_requires_admin(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        app_state.users["alice"] = User(app_state, username="alice")
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><polygon points="1,1"/></svg>'
        result = await app_state.db.cheat_report.insert_one(
            {"kind": "external_overlay", "gameId": "abcdefgh", "overlaySvg": svg}
        )
        url = f"/admin/fair-play/overlay/{result.inserted_id}"
        self.set_session_user("alice")
        with patch("views.admin.ADMINS", ["mod"]):
            denied = await self.client.get(url)
        self.assertEqual(denied.status, 403)

        # The previous request updates the session cookie for alice. Clear it
        # before switching identities to avoid duplicate scoped cookies.
        self.client.session.cookie_jar.clear()
        self.set_session_user("mod")
        with patch("views.admin.ADMINS", ["mod"]):
            page = await self.client.get("/admin/fair-play")
            response = await self.client.get(url)
        self.assertIn(url, await page.text())
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.read(), svg.encode())
        self.assertEqual(response.content_type, "application/octet-stream")
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Content-Security-Policy"], "sandbox")

    async def test_user_search_is_case_insensitive_and_renders_status(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        self.set_session_user("mod")

        created_at = datetime(2025, 2, 3, tzinfo=UTC)
        await app_state.db.user.insert_one(
            {
                "_id": "MixedCase",
                "username_lower": "mixedcase",
                "title": "FM",
                "enabled": False,
                "shadowban": True,
                "patron": True,
                "createdAt": created_at,
                "count": {"game": 12, "win": 7, "loss": 3, "draw": 2, "rated": 10},
                "security": {
                    "ipHashes": ["ip-one"],
                    "fpHashes": ["fp-one", "fp-two"],
                    "ipfpHashes": [],
                    "lastAutoCloseReason": "ban evasion",
                    "lastAutoCloseAt": created_at,
                },
            }
        )
        await app_state.db.mod_log.insert_one(
            {
                "_id": "log-one",
                "mod": "mod",
                "user": "MixedCase",
                "action": "chat_timeout",
                "details": "spamming the chat",
                "createdAt": created_at,
            }
        )

        with patch("views.admin.ADMINS", ["mod"]):
            response = await self.client.get(
                "/admin/users?username=%40mixedcase&done=reopen_account"
            )

        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn('href="/@/MixedCase"', body)
        self.assertIn("Closed", body)
        self.assertIn("Patron", body)
        self.assertIn("Shadowbanned", body)
        self.assertIn("12 total · 7 wins · 3 losses · 2 draws", body)
        self.assertIn("IP 1 · fingerprint 2 · combined 0", body)
        self.assertIn("ban evasion", body)
        self.assertIn("Reopen account completed.", body)
        self.assertIn("Chat timeout", body)
        self.assertIn("spamming the chat", body)
        self.assertIn("/api/admin/users/MixedCase/unpatron", body)
        self.assertIn("/api/admin/users/MixedCase/unshadowban", body)
        self.assertIn("/api/admin/users/MixedCase/reopen", body)
        self.assertIn("admin-action-dialog", body)

    async def test_protected_user_page_hides_action_buttons(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        await app_state.db.user.insert_one({"_id": "mod", "username_lower": "mod", "enabled": True})
        self.set_session_user("mod")

        with patch("views.admin.ADMINS", ["mod"]), patch("admin.ADMINS", ["mod"]):
            response = await self.client.get("/admin/users?username=mod")

        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn("This is a protected account", body)
        self.assertIn("/api/admin/users/mod/patron", body)
        self.assertNotIn("/api/admin/users/mod/timeout", body)
        self.assertNotIn("/api/admin/users/mod/shadowban", body)
        self.assertNotIn("/api/admin/users/mod/close", body)

    async def test_user_search_reports_invalid_and_missing_user(self):
        app_state = get_app_state(self.app)
        app_state.users["mod"] = User(app_state, username="mod")
        self.set_session_user("mod")

        with patch("views.admin.ADMINS", ["mod"]):
            invalid = await self.client.get("/admin/users?username=not%20valid")
            missing = await self.client.get("/admin/users?username=missing")

        self.assertEqual(invalid.status, 200)
        self.assertIn("Enter a valid username.", await invalid.text())
        self.assertEqual(missing.status, 200)
        self.assertIn("User not found.", await missing.text())


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2)
