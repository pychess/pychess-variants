from unittest.mock import Mock, patch

import aiohttp_session
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, make_mocked_request
from aiohttp_session import SimpleCookieStorage
from csrf import (
    ALLOW_ORIGINLESS_LOOPBACK_KEY,
    CSRF_FORM_FIELD,
    CSRF_HEADER,
    _is_loopback_request,
    csrf_exempt,
    csrf_protection_middleware,
    ensure_csrf_token,
)


class CsrfProtectionTestCase(AioHTTPTestCase):
    async def get_application(self):
        app = web.Application()
        aiohttp_session.setup(app, SimpleCookieStorage())
        app.middlewares.append(csrf_protection_middleware)

        async def establish_session(request: web.Request) -> web.Response:
            session = await aiohttp_session.get_session(request)
            session_key = request.rel_url.query.get("key", "user_name")
            session[session_key] = "alice"
            return web.json_response({"csrf": ensure_csrf_token(session)})

        async def mutate(_request: web.Request) -> web.Response:
            return web.json_response({"mutated": True})

        @csrf_exempt
        async def machine_mutate(_request: web.Request) -> web.Response:
            return web.json_response({"mutated": True})

        app.router.add_get("/session", establish_session)
        app.router.add_post("/mutate", mutate)
        app.router.add_post("/machine", machine_mutate)
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def _csrf_token(self) -> str:
        response = await self.client.get("/session")
        self.assertEqual(200, response.status)
        payload = await response.json()
        return str(payload["csrf"])

    async def test_cross_site_post_is_rejected_even_with_session_cookie(self):
        await self._csrf_token()

        response = await self.client.post(
            "/mutate",
            headers={
                "Origin": "https://attacker.test",
                "Sec-Fetch-Site": "cross-site",
            },
        )

        self.assertEqual(403, response.status)

    async def test_same_origin_post_is_allowed(self):
        await self._csrf_token()
        origin = str(self.client.make_url("/")).rstrip("/")

        response = await self.client.post(
            "/mutate",
            headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"},
        )

        self.assertEqual(200, response.status)

    async def test_sessions_without_username_require_csrf_protection(self):
        for key in ("oauth_id", "oauth_flows", "token", "closed_account_user"):
            with self.subTest(key=key):
                self.client.session.cookie_jar.clear()
                session_response = await self.client.get("/session", params={"key": key})
                token = (await session_response.json())["csrf"]
                origin = str(self.client.make_url("/")).rstrip("/")

                for headers in (
                    {"Origin": "https://attacker.test", "Sec-Fetch-Site": "same-site"},
                    {"Origin": origin, "Sec-Fetch-Site": "cross-site", CSRF_HEADER: token},
                    {},
                ):
                    rejected = await self.client.post("/mutate", headers=headers)
                    self.assertEqual(403, rejected.status)

                same_origin = await self.client.post("/mutate", headers={"Origin": origin})
                self.assertEqual(200, same_origin.status)
                token_response = await self.client.post("/mutate", headers={CSRF_HEADER: token})
                self.assertEqual(200, token_response.status)

    async def test_stateless_post_is_still_allowed(self):
        response = await self.client.post("/mutate")
        self.assertEqual(200, response.status)

    async def test_localhost_host_does_not_disable_token_validation(self):
        token = await self._csrf_token()
        for host in ("localhost", "127.0.0.1", "[::1]"):
            with self.subTest(host=host):
                rejected = await self.client.post("/mutate", headers={"Host": host})
                accepted = await self.client.post(
                    "/mutate", headers={"Host": host, CSRF_HEADER: token}
                )
                self.assertEqual(403, rejected.status)
                self.assertEqual(200, accepted.status)

    async def test_development_exception_requires_local_host_and_peer(self):
        app = web.Application()
        app[ALLOW_ORIGINLESS_LOOPBACK_KEY] = True
        for host, peer, allowed in (
            ("localhost", "127.0.0.1", True),
            ("[::1]:8080", "::1", True),
            ("localhost", "203.0.113.10", False),
            ("www.pychess.org", "127.0.0.1", False),
        ):
            with self.subTest(host=host, peer=peer):
                transport = Mock()
                transport.get_extra_info.side_effect = lambda name, default=None, peer=peer: (
                    (peer, 1234) if name == "peername" else default
                )
                request = make_mocked_request(
                    "POST", "/mutate", headers={"Host": host}, app=app, transport=transport
                )
                self.assertEqual(allowed, _is_loopback_request(request))

    async def test_missing_origin_requires_session_token_off_loopback(self):
        token = await self._csrf_token()

        with patch("csrf._is_loopback_request", return_value=False):
            rejected = await self.client.post("/mutate")
            accepted = await self.client.post("/mutate", headers={CSRF_HEADER: token})

        self.assertEqual(403, rejected.status)
        self.assertEqual(200, accepted.status)

    async def test_form_token_is_accepted_when_origin_headers_are_missing(self):
        token = await self._csrf_token()

        with patch("csrf._is_loopback_request", return_value=False):
            response = await self.client.post("/mutate", data={CSRF_FORM_FIELD: token})

        self.assertEqual(200, response.status)

    async def test_explicit_machine_route_exemption_bypasses_browser_csrf_guard(self):
        await self._csrf_token()

        response = await self.client.post(
            "/machine",
            headers={
                "Origin": "https://attacker.test",
                "Sec-Fetch-Site": "cross-site",
            },
        )

        self.assertEqual(200, response.status)
