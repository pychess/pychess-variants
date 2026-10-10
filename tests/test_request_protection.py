import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp.test_utils import AioHTTPTestCase
from const import ANON_PREFIX, HTTP_ANON_USER
from glicko2.glicko2 import new_default_perf
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from request_protection import RequestProtectionState, RouteRateLimit
from typedefs import request_protection_state_key

from server import make_app


class RequestProtectionTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    async def test_known_scanner_path_returns_not_found(self):
        resp = await self.client.request("GET", "/wp-content/plugins/hellopress/wp_filemanager")
        self.assertEqual(resp.status, 404)

    async def test_anonymous_page_view_stays_stateless(self):
        app_state = get_app_state(self.app)
        before = set(app_state.users)

        resp = await self.client.get("/about")

        self.assertEqual(resp.status, 200)
        self.assertEqual(before, set(app_state.users))
        self.assertIn(HTTP_ANON_USER, app_state.users)
        self.assertFalse(
            any(name.startswith(ANON_PREFIX) for name in app_state.users if name not in before)
        )
        self.assertNotIn("AIOHTTP_SESSION", resp.cookies)

    async def test_stateless_anonymous_page_uses_session_preferences(self):
        app_state = get_app_state(self.app)
        before = set(app_state.users)

        response = await self.client.post(
            "/pref/theme",
            data={"theme": "light"},
        )
        self.assertEqual(response.status, 204)

        response = await self.client.post(
            "/pref/game-category",
            data={"game_category": "shogi"},
            headers={"Origin": str(self.client.make_url("/")).rstrip("/")},
            allow_redirects=False,
        )
        self.assertEqual(response.status, 302)

        response = await self.client.get("/about")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('data-theme="light"', html)
        self.assertIn('data-game-category="shogi"', html)

        self.assertEqual(before, set(app_state.users))
        shared_anon = app_state.users[HTTP_ANON_USER]
        self.assertEqual(shared_anon.theme, "dark")
        self.assertEqual(shared_anon.game_category, "all")

    async def test_stateless_anonymous_profile_uses_session_category_filter(self):
        app_state = get_app_state(self.app)
        chess_perf = new_default_perf()
        chess_perf["nb"] = 2
        shogi_perf = new_default_perf()
        shogi_perf["nb"] = 3
        await app_state.db.user.insert_one(
            {
                "_id": "CategoryProfile",
                "perfs": {"chess": chess_perf, "shogi": shogi_perf},
            }
        )

        response = await self.client.post(
            "/pref/game-category",
            data={"game_category": "shogi"},
            headers={"Origin": str(self.client.make_url("/")).rstrip("/")},
            allow_redirects=False,
        )
        self.assertEqual(response.status, 302)

        response = await self.client.get("/@/CategoryProfile")
        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn("/@/CategoryProfile/perf/shogi", html)
        self.assertNotIn("/@/CategoryProfile/perf/chess", html)

    async def test_anonymous_profile_target_renders_without_profile_counters(self):
        response = await self.client.get("/@/Anon–profile1234")

        self.assertEqual(response.status, 200)
        html = await response.text()
        self.assertIn('data-profile-restricted="True"', html)

    async def test_websocket_guest_inherits_session_preferences(self):
        app_state = get_app_state(self.app)

        response = await self.client.post(
            "/pref/theme",
            data={"theme": "light"},
        )
        self.assertEqual(response.status, 204)
        response = await self.client.post(
            "/pref/game-category",
            data={"game_category": "shogi"},
            headers={"Origin": str(self.client.make_url("/")).rstrip("/")},
            allow_redirects=False,
        )
        self.assertEqual(response.status, 302)

        before = set(app_state.users)
        ws = await self.client.ws_connect(
            "/wsl", headers={"Origin": str(self.client.make_url("/")).rstrip("/")}
        )
        try:
            created = [
                app_state.users[name]
                for name in app_state.users
                if name not in before and name.startswith(ANON_PREFIX)
            ]
            self.assertEqual(1, len(created))
            self.assertEqual(created[0].theme, "light")
            self.assertEqual(created[0].game_category, "shogi")
        finally:
            await ws.close()

    async def test_websocket_materializes_and_persists_anonymous_identity(self):
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
            cookies = self.client.session.cookie_jar.filter_cookies(self.client.make_url("/"))
            self.assertIn("AIOHTTP_SESSION", cookies)
        finally:
            await ws.close()

    async def test_plain_http_websocket_probe_does_not_create_guest(self):
        app_state = get_app_state(self.app)
        before = set(app_state.users)

        resp = await self.client.get("/wsl", allow_redirects=False)

        self.assertEqual(resp.status, 302)
        self.assertEqual(before, set(app_state.users))

    async def test_malformed_websocket_upgrade_does_not_create_guest(self):
        app_state = get_app_state(self.app)
        before = set(app_state.users)

        resp = await self.client.get(
            "/wsl",
            headers={
                "Connection": "Upgrade",
                "Upgrade": "websocket",
                "Origin": str(self.client.make_url("/")).rstrip("/"),
            },
            allow_redirects=False,
        )

        self.assertIn(resp.status, {302, 400})
        self.assertEqual(before, set(app_state.users))

    async def test_anonymous_profiles_share_a_global_budget_across_ips(self):
        state = self.app[request_protection_state_key]
        state._ANON_PROFILE_GLOBAL_LIMIT = RouteRateLimit(
            "anon_profile_global_test", max_requests=3, window_seconds=60.0
        )

        statuses = []
        for index in range(4):
            resp = await self.client.get(
                "/@/NoSuchDistributedCrawlerTarget",
                headers={"X-Forwarded-For": f"192.0.2.{index}"},
            )
            statuses.append(resp.status)

        self.assertEqual([404, 404, 404, 429], statuses)

    async def test_profile_trace_logs_request_fingerprint_and_protection_decisions(self):
        app_state = get_app_state(self.app)
        await app_state.db.user.insert_one({"_id": "TraceProfile", "title": ""})

        with (
            patch("middlewares._should_trace_request", return_value=True),
            self.assertLogs("middlewares", level="WARNING") as captured,
        ):
            response = await self.client.get(
                "/@/TraceProfile",
                headers={"User-Agent": "ProfileCrawler/1.0"},
            )

        self.assertEqual(response.status, 200)
        message = "\n".join(captured.output)
        self.assertIn("ua='ProfileCrawler/1.0'", message)
        self.assertIn("ref='-'", message)
        self.assertIn("http=1.1", message)
        self.assertIn("session_cookie=False", message)
        self.assertIn("new_session=False", message)
        self.assertIn("profile_restricted=True", message)
        self.assertIn("rl_bucket=profile,anon_profile_global", message)

    async def test_new_anonymous_session_is_visible_in_request_trace(self):
        with (
            patch("middlewares._should_trace_request", return_value=True),
            self.assertLogs("middlewares", level="WARNING") as captured,
        ):
            response = await self.client.post(
                "/invite/accept/LogSess1",
                headers={"User-Agent": "AnonymousAction/1.0"},
            )

        self.assertEqual(response.status, 200)
        message = "\n".join(captured.output)
        self.assertIn("session_cookie=False", message)
        self.assertIn("new_session=True", message)
        self.assertIn("rl_bucket=game_view,new_anon_identity", message)

    async def test_profile_route_is_rate_limited(self):
        statuses: list[int] = []
        test_limit = RouteRateLimit("profile", max_requests=3, window_seconds=30.0)

        # Exercise the same boundary behavior with a tiny test-only budget
        # instead of making 40+ HTTP requests to reach the live threshold.
        with patch.object(RequestProtectionState, "_PROFILE_LIMIT", test_limit):
            for _ in range(4):
                resp = await self.client.request("GET", "/@/NoSuchUserRateLimitProbe")
                statuses.append(resp.status)

        self.assertEqual([404, 404, 404, 429], statuses)

    async def test_inbox_threads_route_is_not_in_profile_rate_limit_bucket(self):
        statuses: list[int] = []
        test_limit = RouteRateLimit("profile", max_requests=3, window_seconds=30.0)

        with patch.object(RequestProtectionState, "_PROFILE_LIMIT", test_limit):
            for _ in range(4):
                resp = await self.client.request("GET", "/api/inbox/threads")
                statuses.append(resp.status)

        self.assertNotIn(429, statuses)

    async def test_unknown_blog_id_does_not_return_server_error(self):
        resp = await self.client.request("GET", "/blogs/null")
        self.assertNotEqual(resp.status, 500)

    async def test_known_variant_without_doc_does_not_return_server_error(self):
        for variant in ("makbug", "supply"):
            resp = await self.client.request("GET", f"/variants/{variant}")
            self.assertNotEqual(resp.status, 500)

    async def test_unknown_round_socket_game_returns_not_found(self):
        resp = await self.client.request("GET", "/wsr/AAAAAAAA")
        self.assertEqual(resp.status, 404)

    async def test_stale_invite_id_does_not_return_server_error(self):
        game_id = "8FEG1Sxq"
        app_state = get_app_state(self.app)
        app_state.invites[game_id] = SimpleNamespace(id="missing_seek")

        resp = await self.client.request("GET", f"/invite/{game_id}")
        self.assertNotEqual(resp.status, 500)

    async def test_cancel_invite_with_stale_seek_redirects_without_server_error(self):
        game_id = "BQ4PCvAl"
        app_state = get_app_state(self.app)
        app_state.invites[game_id] = SimpleNamespace(id="missing_seek")

        resp = await self.client.request("POST", f"/invite/cancel/{game_id}", allow_redirects=False)
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.headers["Location"], "/")
        self.assertNotIn(game_id, app_state.invites)

    async def test_missing_invite_id_shows_expired_invite_state(self):
        game_id = "AbCd1234"
        resp = await self.client.request("GET", f"/invite/{game_id}")
        self.assertEqual(resp.status, 200)
        html = await resp.text()
        self.assertIn('data-inviter="expired"', html)

    async def test_missing_invite_accept_shows_expired_invite_state(self):
        game_id = "QwEr5678"
        resp = await self.client.request("POST", f"/invite/accept/{game_id}")
        self.assertEqual(resp.status, 200)
        html = await resp.text()
        self.assertIn('data-inviter="expired"', html)

    async def test_video_tags_are_url_encoded_in_html(self):
        resp = await self.client.request("GET", "/video")
        self.assertEqual(resp.status, 200)
        html = await resp.text()
        self.assertIn("/video?tags=Hu%20Ronghua", html)
        self.assertNotIn('/video?tags=Hu Ronghua"', html)

    async def test_translation_select_rejects_foreign_referer_redirect(self):
        resp = await self.client.request(
            "POST",
            "/translation/select",
            data={"lang": "hu"},
            headers={"REFERER": "https://evil.example/phish"},
            allow_redirects=False,
        )
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.headers["Location"], "/")

    async def test_game_category_rejects_protocol_relative_referer_redirect(self):
        resp = await self.client.request(
            "POST",
            "/pref/game-category",
            data={"game_category": "chess"},
            headers={"REFERER": "//evil.example/phish"},
            allow_redirects=False,
        )
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.headers["Location"], "/")

    async def test_names_autocomplete_escapes_regex_metacharacters(self):
        app_state = get_app_state(self.app)
        await app_state.db.user.insert_many(
            [
                {"_id": "AlphaBeta", "title": "GM"},
                {"_id": "alpha_one", "title": ""},
                {"_id": "alpine", "title": "IM"},
            ]
        )

        response = await self.client.get("/api/names?p=alph")
        self.assertEqual(response.status, 200)
        self.assertEqual(
            await response.json(),
            [["AlphaBeta", "GM"], ["alpha_one", ""]],
        )

        response = await self.client.get("/api/names?p=alph%5C")
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), [])

    async def test_user_status_requires_ids(self):
        response = await self.client.get("/api/users/status")

        self.assertEqual(response.status, 400)


class RequestProtectionStateTestCase(unittest.TestCase):
    def test_study_embed_uses_game_view_rate_limit(self):
        limit = RequestProtectionState().classify("/study/embed/StUdY001/ChAp0001")
        self.assertIsNotNone(limit)
        self.assertEqual("game_view", limit.name)

    def test_anonymous_profile_concurrency_is_bounded_and_released(self):
        state = RequestProtectionState()
        state._ANON_PROFILE_MAX_INFLIGHT = 1
        state._ANON_PROFILE_GLOBAL_LIMIT = RouteRateLimit(
            "anon_profile_concurrency_test", max_requests=10, window_seconds=60.0
        )

        self.assertEqual((True, None), state.enter_anonymous_profile())
        self.assertEqual((False, "concurrency"), state.enter_anonymous_profile())
        state.leave_anonymous_profile()
        self.assertEqual((True, None), state.enter_anonymous_profile())

    def test_new_anonymous_identity_creation_has_a_global_budget(self):
        state = RequestProtectionState()
        state._local_dev_mode = False
        state._NEW_ANON_IDENTITY_LIMIT = RouteRateLimit(
            "new_anon_identity_test", max_requests=2, window_seconds=60.0
        )

        self.assertTrue(state.allow_new_anonymous_identity())
        self.assertTrue(state.allow_new_anonymous_identity())
        self.assertFalse(state.allow_new_anonymous_identity())

    def test_block_log_is_bounded_under_unique_scanner_flood(self):
        state = RequestProtectionState()
        state._BLOCK_LOG_MAX_KEYS = 10

        with patch("request_protection.monotonic", return_value=100.0):
            for index in range(30):
                self.assertTrue(state.should_log_block(f"scanner:192.0.2.{index}"))

        self.assertLessEqual(len(state._last_block_log), state._BLOCK_LOG_MAX_KEYS)

    def test_block_log_discards_expired_entries(self):
        state = RequestProtectionState()
        state._last_block_log = {"old": 1.0}

        with patch("request_protection.monotonic", return_value=100.0):
            self.assertTrue(state.should_log_block("new"))

        self.assertNotIn("old", state._last_block_log)
        self.assertIn("new", state._last_block_log)


if __name__ == "__main__":
    unittest.main()
