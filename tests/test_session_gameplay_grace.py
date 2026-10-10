import asyncio
import json
import time
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp_session
from aiohttp import WSMsgType, WSServerHandshakeError, web
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from const import ARENA, RR, STARTED, SWISS, T_FINISHED, T_STARTED
from cryptography.fernet import Fernet
from session_security import (
    session_expiry_timeout,
    session_matches_user,
    session_security_middleware,
)
from settings import MAX_AGE, SESSION_COOKIE_MAX_AGE, SESSION_GAMEPLAY_GRACE
from typedefs import pychess_global_app_state_key
from websocket_utils import process_ws, ws_send_json
from ws_structs import ROUND_TYPED_DECODERS


class SessionGameplayGraceTestCase(AioHTTPTestCase):
    async def get_application(self):
        self.now = int(time.time())
        self.clock_patch = patch("session_security.datetime")
        self.clock = self.clock_patch.start()
        self.clock.now.return_value.timestamp.return_value = self.now
        self.addCleanup(self.clock_patch.stop)
        self.state = SimpleNamespace(games={}, tournaments={}, shutdown=False)
        self.user = SimpleNamespace(
            username="alice",
            enabled=True,
            anon=False,
            auth_version=0,
            app_state=self.state,
            authenticated_sockets=set(),
        )
        self.state.users = SimpleNamespace(get=AsyncMock(return_value=self.user))
        self.fernet = Fernet(Fernet.generate_key())
        self.storage = EncryptedCookieStorage(self.fernet, max_age=SESSION_COOKIE_MAX_AGE)
        app = web.Application()
        app[pychess_global_app_state_key] = self.state
        aiohttp_session.setup(app, self.storage)
        app.middlewares.append(session_security_middleware)
        self.dispatched = []

        async def page(request):
            session = await aiohttp_session.get_session(request)
            return web.json_response({"user": session.get("user_name")})

        async def socket(request):
            session = await aiohttp_session.get_session(request)

            async def dispatch(_state, _user, ws, data):
                self.dispatched.append(data)
                if hasattr(self, "dispatch_started"):
                    self.dispatch_started.set()
                    await self.dispatch_release.wait()
                    self.dispatch_completed.set()
                await ws_send_json(ws, data)

            return await process_ws(
                session,
                request,
                self.user,
                None,
                dispatch,
                typed_decoders=ROUND_TYPED_DECODERS if request.path.startswith("/wsr/") else None,
            )

        app.router.add_get("/wsr/{gameId}", socket)
        app.router.add_get("/wst", socket)
        app.router.add_get("/wsl", socket)
        app.router.add_get("/wsstudy/{studyId}", socket)
        app.router.add_get("/tournament/{tournamentId}", page)
        app.router.add_get("/tournament/{tournamentId}/cancel", page)
        app.router.add_get("/account", page)
        app.router.add_get("/inbox/subscribe", page)
        app.router.add_get("/api/users/status", page)
        app.router.add_get("/oauth/discord", page)
        app.router.add_post("/tournament/{tournamentId}/pause", page)
        app.router.add_post("/logout", page)
        app.router.add_post("/pref/theme", page)
        app.router.add_get("/{gameId}", page)
        return app

    def set_cookie(self, *, authenticated_at=None, issued_at=None, auth_version=0):
        authenticated_at = self.now - MAX_AGE if authenticated_at is None else authenticated_at
        issued_at = self.now if issued_at is None else issued_at
        self.client.session.cookie_jar.clear()
        data = {
            "created": issued_at,
            "session": {
                "user_name": "alice",
                "authenticated_at": authenticated_at,
                "auth_version": auth_version,
            },
        }
        encrypted = self.fernet.encrypt_at_time(json.dumps(data).encode(), issued_at).decode()
        self.client.session.cookie_jar.update_cookies({"AIOHTTP_SESSION": encrypted})

    def add_game(
        self,
        *,
        game_id="game1234",
        date=None,
        corr=False,
        status=STARTED,
        players=None,
        tournament_id=None,
    ):
        game = SimpleNamespace(
            id=game_id,
            date=datetime.fromtimestamp(self.now - 10 if date is None else date, UTC),
            corr=corr,
            status=status,
            non_bot_players=(self.user,) if players is None else players,
            tournamentId=tournament_id,
        )
        self.state.games[game_id] = game
        return game

    def add_tournament(
        self,
        *,
        system=ARENA,
        tournament_id="tour1234",
        status=T_STARTED,
        starts_at=None,
        joined_at=None,
        withdrawn=False,
        participant=True,
    ):
        player = (
            SimpleNamespace(
                joined_at=datetime.fromtimestamp(
                    self.now - 20 if joined_at is None else joined_at, UTC
                ),
                withdrawn=withdrawn,
                paused=False,
            )
            if participant
            else None
        )
        tournament = SimpleNamespace(
            id=tournament_id,
            system=system,
            status=status,
            starts_at=datetime.fromtimestamp(
                self.now - 10 if starts_at is None else starts_at, UTC
            ),
            player_data_by_name=lambda username: player if username == "alice" else None,
        )
        self.state.tournaments[tournament_id] = tournament
        return tournament, player

    async def assert_ping(self, ws):
        await ws.send_str("/n")
        response = await ws.receive(timeout=1)
        self.assertEqual((WSMsgType.TEXT, "/n"), (response.type, response.data))

    async def assert_closed(self, ws):
        response = await ws.receive(timeout=2)
        self.assertIn(response.type, (WSMsgType.CLOSE, WSMsgType.CLOSED))

    async def test_existing_live_game_survives_expiry_and_reconnects(self):
        game = self.add_game()
        self.set_cookie(authenticated_at=self.now - MAX_AGE + 1)
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            await self.assert_ping(ws)
            self.clock.now.return_value.timestamp.return_value = self.now + 2
            await self.assert_ping(ws)
            await ws.send_json(
                {
                    "type": "move",
                    "gameId": game.id,
                    "move": "e2e4",
                    "clocks": [1000, 1000],
                    "ply": 1,
                }
            )
            self.assertEqual("move", (await ws.receive_json(timeout=1))["type"])
        finally:
            await ws.close()
        # Use the same browser cookie, with no new OAuth login.
        page = await self.client.get("/game1234")
        self.assertEqual({"user": "alice"}, await page.json())
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            await self.assert_ping(ws)
            game.status = 1
            await ws.send_str("/n")
            await self.assert_closed(ws)
        finally:
            await ws.close()

    async def test_idle_game_socket_defers_expiry_and_closes_when_game_finishes(self):
        game = self.add_game()
        self.set_cookie()
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            # Let the deadline watcher run, without relying on incoming pings.
            await asyncio.sleep(0.02)
            self.assertFalse(ws.closed)
            game.status = 1
            await self.assert_closed(ws)
        finally:
            await ws.close()

    async def test_all_three_tournament_systems_keep_between_rounds_and_later_games(self):
        for system in (ARENA, RR, SWISS):
            with self.subTest(system=system):
                self.state.games.clear()
                tournament, _ = self.add_tournament(system=system)
                self.set_cookie()
                self.assertEqual(200, (await self.client.get("/tournament/tour1234")).status)
                ws = await self.client.ws_connect("/wst")
                try:
                    for message_type in (
                        "tournament_user_connected",
                        "join",
                        "pause",
                        "rr_challenge",
                    ):
                        await ws.send_json({"type": message_type, "tournamentId": tournament.id})
                        self.assertEqual(message_type, (await ws.receive_json(timeout=1))["type"])
                finally:
                    await ws.close()
                game = self.add_game(date=self.now + 1, tournament_id=tournament.id)
                ws = await self.client.ws_connect("/wsr/game1234")
                try:
                    await self.assert_ping(ws)
                    tournament.status = T_FINISHED
                    # Arena may finish while its last game is still running.
                    await self.assert_ping(ws)
                    game.status = 1
                    await ws.send_str("/n")
                    await self.assert_closed(ws)
                finally:
                    await ws.close()

    async def test_finished_event_stops_idle_tournament_socket(self):
        tournament, _ = self.add_tournament()
        self.set_cookie()
        ws = await self.client.ws_connect("/wst")
        try:
            await self.assert_ping(ws)
            tournament.status = T_FINISHED
            await self.assert_closed(ws)
        finally:
            await ws.close()

    async def test_rr_presence_polling_and_self_pause_still_work_during_grace(self):
        self.add_tournament(system=RR)
        self.set_cookie()
        self.assertEqual(200, (await self.client.get("/api/users/status?ids=alice,bob")).status)
        self.assertEqual(200, (await self.client.post("/tournament/tour1234/pause")).status)
        self.assertEqual(401, (await self.client.post("/tournament/other123/pause")).status)

    async def test_withdrawal_does_not_disconnect_an_already_running_later_round(self):
        tournament, player = self.add_tournament(system=SWISS)
        game = self.add_game(date=self.now + 1, tournament_id=tournament.id)
        self.set_cookie()
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            player.withdrawn = True
            await self.assert_ping(ws)
            game.status = 1
            await ws.send_str("/n")
            await self.assert_closed(ws)
        finally:
            await ws.close()

    async def test_spectators_correspondence_finished_and_new_games_get_no_grace(self):
        for kwargs in (
            {"corr": True},
            {"status": 1},
            {"players": ()},
            {"date": self.now + 1},
        ):
            with self.subTest(kwargs=kwargs):
                self.state.games.clear()
                self.add_game(**kwargs)
                self.set_cookie()
                with self.assertRaises(WSServerHandshakeError) as error:
                    await self.client.ws_connect("/wsr/game1234")
                self.assertEqual(401, error.exception.status)

    async def test_late_joiners_withdrawn_spectators_and_future_events_get_no_grace(self):
        for kwargs in (
            {"participant": False},
            {"withdrawn": True},
            {"joined_at": self.now + 1},
            {"starts_at": self.now + 1},
            {"status": T_FINISHED},
        ):
            with self.subTest(kwargs=kwargs):
                self.state.tournaments.clear()
                self.add_tournament(**kwargs)
                self.set_cookie()
                with self.assertRaises(WSServerHandshakeError) as error:
                    await self.client.ws_connect("/wst")
                self.assertEqual(401, error.exception.status)

    async def test_private_requests_cannot_clear_game_reconnect_cookie_or_get_authority(self):
        self.add_game()
        self.set_cookie()
        for method, path in (
            ("get", "/account"),
            ("get", "/inbox/subscribe"),
            ("post", "/pref/theme"),
        ):
            response = await getattr(self.client, method)(path)
            self.assertEqual(401, response.status)
            self.assertNotIn("AIOHTTP_SESSION", response.cookies)
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            await self.assert_ping(ws)
        finally:
            await ws.close()
        self.assertEqual(200, (await self.client.get("/oauth/discord")).status)
        self.assertEqual(200, (await self.client.post("/logout")).status)

    async def test_grace_cannot_open_other_sockets_or_mutate_event_controls(self):
        self.add_tournament()
        self.set_cookie()
        for path in ("/wsl", "/wsstudy/stud1234"):
            with self.assertRaises(WSServerHandshakeError) as error:
                await self.client.ws_connect(path)
            self.assertEqual(401, error.exception.status)
        self.assertEqual(401, (await self.client.get("/tournament/tour1234/cancel")).status)

    async def test_grace_cannot_dispatch_management_other_events_or_chat_commands(self):
        self.add_tournament()
        self.add_game()
        for path, message in (
            ("/wst", {"type": "get_rr_management", "tournamentId": "tour1234"}),
            ("/wst", {"type": "start_next_round", "tournamentId": "tour1234"}),
            ("/wst", {"type": "join", "tournamentId": "other123"}),
            ("/wst", {"type": "lobbychat", "tournamentId": "tour1234", "message": "/silence bob"}),
            ("/wsr/game1234", {"type": "rematch", "gameId": "game1234"}),
            ("/wsr/game1234", {"type": "move", "gameId": "other123"}),
            ("/wsr/game1234", {"type": "delete", "gameId": "game1234"}),
        ):
            with self.subTest(message=message):
                self.set_cookie()
                ws = await self.client.ws_connect(path)
                try:
                    await ws.send_json(message)
                    await self.assert_closed(ws)
                finally:
                    await ws.close()
        self.assertEqual([], self.dispatched)

    async def test_revocation_and_bans_override_grace(self):
        self.add_game()
        self.add_tournament()
        for field, value in (("auth_version", 1), ("enabled", False)):
            with self.subTest(field=field):
                self.user.auth_version = 0
                self.user.enabled = True
                self.set_cookie()
                ws = await self.client.ws_connect("/wsr/game1234")
                try:
                    await self.assert_ping(ws)
                    setattr(self.user, field, value)
                    await ws.send_str("/n")
                    await self.assert_closed(ws)
                finally:
                    await ws.close()
                with self.assertRaises(WSServerHandshakeError) as error:
                    await self.client.ws_connect("/wsr/game1234")
                self.assertEqual(401, error.exception.status)

    async def test_invalid_and_future_timestamps_never_get_grace(self):
        self.add_game()
        self.add_tournament()
        for timestamp in (True, "invalid", self.now + 60):
            with self.subTest(timestamp=timestamp):
                self.set_cookie(authenticated_at=timestamp)
                with self.assertRaises(WSServerHandshakeError) as error:
                    await self.client.ws_connect("/wsr/game1234")
                self.assertEqual(401, error.exception.status)

    async def test_expiry_closes_socket_without_cancelling_in_flight_move(self):
        self.dispatch_started = asyncio.Event()
        self.dispatch_release = asyncio.Event()
        self.dispatch_completed = asyncio.Event()
        game = self.add_game()
        self.set_cookie()
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            await ws.send_json({"type": "move", "gameId": game.id})
            await asyncio.wait_for(self.dispatch_started.wait(), timeout=1)
            game.status = 1
            await self.assert_closed(ws)
            self.dispatch_release.set()
            await asyncio.wait_for(self.dispatch_completed.wait(), timeout=1)
        finally:
            self.dispatch_release.set()
            await ws.close()

    async def test_transport_retains_old_cookie_and_handshake_does_not_renew_login(self):
        self.add_game()
        self.set_cookie(authenticated_at=self.now - MAX_AGE - 1, issued_at=self.now - MAX_AGE - 1)
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            await self.assert_ping(ws)
            cookie = self.client.session.cookie_jar.filter_cookies(self.client.make_url("/"))[
                "AIOHTTP_SESSION"
            ]
            data = json.loads(self.fernet.decrypt(cookie.value.encode()))
            self.assertEqual(self.now - MAX_AGE - 1, data["session"]["authenticated_at"])
            handshake_cookie = SimpleCookie()
            handshake_cookie.load(ws._response.headers["Set-Cookie"])
            self.assertEqual(
                str(SESSION_COOKIE_MAX_AGE), handshake_cookie["AIOHTTP_SESSION"]["max-age"]
            )
        finally:
            await ws.close()

    async def test_grace_is_bounded_and_does_not_extend_private_sse(self):
        self.add_game()
        self.set_cookie()
        ws = await self.client.ws_connect("/wsr/game1234")
        try:
            await self.assert_ping(ws)
            from aiohttp_session import Session

            session = Session(
                None,
                new=False,
                data={
                    "created": self.now,
                    "session": {
                        "user_name": "alice",
                        "authenticated_at": self.now - MAX_AGE,
                    },
                },
            )
            self.assertFalse(session_matches_user(session, self.user))
            with self.assertRaises(web.HTTPUnauthorized):
                session_expiry_timeout(session, self.user)
            self.clock.now.return_value.timestamp.return_value = self.now + SESSION_GAMEPLAY_GRACE
            await ws.send_str("/n")
            await self.assert_closed(ws)
        finally:
            await ws.close()
