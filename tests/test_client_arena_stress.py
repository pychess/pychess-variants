"""Focused no-network coverage for the local arena stress-test client."""

import asyncio
import json
import unittest
from unittest.mock import patch

from aiohttp import WSMsgType, web

from client_stresstest import (
    RunStats,
    TestUser as StressTestUser,
    create_local_arenas,
    parse_arena_spec,
)


class ArenaSpecTests(unittest.TestCase):
    def test_valid_arena_profiles(self):
        spec = parse_arena_spec("Abcd1234:250:bullet")
        self.assertEqual(spec.tournament_id, "Abcd1234")
        self.assertEqual(spec.players, 250)
        self.assertEqual(spec.profile.name, "bullet")
        self.assertEqual(spec.variant, "chess")
        self.assertEqual(parse_arena_spec("abcd1234:50:rapid:shogi").variant, "shogi")
        self.assertEqual(parse_arena_spec("auto:50:rapid").tournament_id, "auto")

    def test_invalid_arena_spec(self):
        for raw in (
            "short:250:bullet",
            "abcdefgh:0:bullet",
            "abcdefgh:1:bullet",
            "abcdefgh:nope:bullet",
            "abcdefgh:20:hyperbullet",
            "abcdefgh:20:bullet:bad/variant",
            "abcdefgh:20",
        ):
            with self.subTest(raw=raw), self.assertRaises(Exception):
                parse_arena_spec(raw)


class ArenaAutoCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_real_tournaments_with_server_generated_ids(self):
        names = []
        forms = []

        async def home(_request):
            return web.Response(text='<div data-username="Test–KnightCannon"></div>')

        async def create(request):
            self.assertEqual(request.headers["Origin"], request.scheme + "://" + request.host)
            self.assertEqual(request.headers["Accept"], "application/json")
            form = dict(await request.post())
            forms.append(form)
            names.append(form["name"])
            return web.json_response({"tournamentId": f"Tst{len(forms):05d}"})

        app = web.Application()
        app.router.add_get("/", home)
        app.router.add_post("/tournaments/new", create)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        origin = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        specs = [parse_arena_spec("auto:10:bullet"), parse_arena_spec("auto:20:blitz")]
        try:
            with patch("client_stresstest.URI", origin):
                result = await create_local_arenas(specs, 180)
        finally:
            await runner.cleanup()
        self.assertEqual([s.tournament_id for s in result], ["Tst00001", "Tst00002"])
        self.assertEqual([s.players for s in result], [10, 20])
        self.assertEqual([f["clockTime"] for f in forms], ["1", "5"])
        self.assertTrue(all(f["waitMinutes"] == "0" for f in forms))
        self.assertTrue(all(f["minutes"] == "20" for f in forms))
        self.assertEqual(len(set(names)), 2)

    async def test_explicit_ids_do_not_create_any_tournaments(self):
        spec = parse_arena_spec("ABCD1234:10:bullet")
        self.assertEqual(await create_local_arenas([spec], 180), [spec])


class ArenaProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_finish_round_does_not_log_out_of_tournament(self):
        spec = parse_arena_spec("Abcd1234:10:bullet")
        user = StressTestUser(
            arena_spec=spec,
            postgame_linger_probability=0,
            run_stats=RunStats(),
        )
        user.username = "Test–KnightCannon"

        class FakeWS:
            def __init__(self):
                self.messages = []

            async def send_json(self, payload):
                self.messages.append(payload)

        round_ws = FakeWS()
        tournament_ws = FakeWS()
        await user._leave_finished_game(round_ws, tournament_ws)
        self.assertEqual(round_ws.messages, [{"type": "logout"}])
        self.assertEqual(tournament_ws.messages, [])

    async def test_tournament_wst_join_and_pairing_protocol(self):
        """Join, receive a pairing, leave WST for the round, and return."""
        messages = []
        connections = 0
        active_tournament_sockets = 0
        page_views = 0

        async def home(_request):
            return web.Response(text='<div data-username="Test–KnightCannon"></div>')

        async def tournament(_request):
            nonlocal page_views
            page_views += 1
            return web.Response(text="Arena tournament page")

        async def socket_handler(request):
            nonlocal connections, active_tournament_sockets
            connections += 1
            active_tournament_sockets += 1
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            try:
                async for msg in ws:
                    if msg.type != WSMsgType.TEXT or msg.data == "/n":
                        continue
                    data = json.loads(msg.data)
                    messages.append(data["type"])
                    if data["type"] == "tournament_user_connected":
                        if connections == 1:
                            await ws.send_json(
                                {
                                    "type": "tournament_user_connected",
                                    "tsystem": 0,
                                    "tstatus": 1,
                                    "ustatus": "spectator",
                                }
                            )
                        else:
                            await ws.send_json(
                                {
                                    "type": "tournament_user_connected",
                                    "tsystem": 0,
                                    "tstatus": 3,
                                    "ustatus": "joined",
                                }
                            )
                    elif data["type"] == "join":
                        await ws.send_json(
                            {
                                "type": "ustatus",
                                "username": "Test–KnightCannon",
                                "ustatus": "joined",
                            }
                        )
                        await ws.send_json(
                            {
                                "type": "new_game",
                                "gameId": "game1234",
                                "wplayer": "Test–KnightCannon",
                                "bplayer": "Test–OtherPlayer",
                            }
                        )
            finally:
                active_tournament_sockets -= 1
            return ws

        app = web.Application()
        app.router.add_get("/", home)
        app.router.add_get("/tournament/{id}", tournament)
        app.router.add_get("/wst", socket_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        sock = site._server.sockets[0]
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        spec = parse_arena_spec("Abcd1234:10:bullet")
        stats = RunStats()
        user = StressTestUser(arena_spec=spec, run_stats=stats)
        # An actual round integration test runs against the real server.
        # Here we verify that the WST socket is closed before entering a round.
        captured_games = []

        def start_round(*args):
            captured_games.append((args[2], active_tournament_sockets))

        user._start_round_task = start_round
        try:
            with (
                patch("client_stresstest.URI", origin),
                patch("client_stresstest.TOURNAMENT_URL", f"{origin.replace('http', 'ws')}/wst"),
            ):
                await asyncio.wait_for(user.go_to_arena(), timeout=5)
        finally:
            await runner.cleanup()
        self.assertEqual(messages, ["tournament_user_connected", "join", "tournament_user_connected"])
        self.assertEqual(captured_games, [("game1234", 0)])
        self.assertEqual(page_views, 2)
        self.assertEqual(connections, 2)
        result = stats.arena_summary([spec])[spec.tournament_id]
        self.assertEqual(result["joined_players"], 1)
        self.assertEqual(result["games_started"], 1)

    async def test_notifications_and_repair_latency(self):
        spec = parse_arena_spec("Abcd1234:10:blitz")
        stats = RunStats()
        stats.record_arena_joined(spec.tournament_id, "alice")
        stats.record_arena_joined(spec.tournament_id, "bob")
        stats.record_arena_notification(
            spec.tournament_id,
            "game0001",
            joined_at=0.1,
            last_game_end_at=None,
        )
        await asyncio.sleep(0)
        stats.record_arena_notification(
            spec.tournament_id,
            "game0001",
            joined_at=0.1,
            last_game_end_at=None,
        )
        stats.record_arena_game_end(spec.tournament_id)
        stats.record_arena_game_end(spec.tournament_id)
        result = stats.arena_summary([spec])[spec.tournament_id]
        self.assertEqual(result["joined_players"], 2)
        self.assertEqual(result["games_started"], 1)
        self.assertEqual(result["player_game_ends_observed"], 2)
        self.assertEqual(result["notification_skew_ms"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
