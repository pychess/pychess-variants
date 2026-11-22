"""Unit/loopback tests for the optional local Tachyon + mixed HTTP workload."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import client_stresstest as stress
from aiohttp import web

from scripts.profile_local_server import find_local_server_pids, is_test_user_server


class LocalProfilingConfigurationTests(unittest.TestCase):
    def test_cookie_file_stays_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session"
            path.write_text("AIOHTTP_SESSION=abcdefg\n", encoding="utf-8")
            path.chmod(0o600)
            self.assertEqual(stress.read_session_cookie(path), "abcdefg")
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "must be private"):
                stress.read_session_cookie(path)

    def test_pid_detection_matches_current_checkout_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "server").mkdir(parents=True)
            server = root / "server" / "server.py"
            server.touch()
            proc = Path(directory) / "proc"
            for pid, command in (
                (123, b"/usr/bin/python3.15\0server/server.py\0"),
                (124, b"/usr/bin/python3.15\0other/server.py\0"),
                (125, b"/usr/bin/python3.15\0/misc/server/server.py\0"),
            ):
                directory_for_pid = proc / str(pid)
                directory_for_pid.mkdir(parents=True)
                (directory_for_pid / "cmdline").write_bytes(command)
                (directory_for_pid / "cwd").symlink_to(root)
            self.assertEqual(find_local_server_pids(root, proc), [123])

    def test_server_test_mode_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            target = proc / "123"
            target.mkdir()
            (target / "cmdline").write_bytes(b"/usr/bin/python3.15\0server/server.py\0-a\0")
            self.assertTrue(is_test_user_server(123, proc))
            (target / "cmdline").write_bytes(b"/usr/bin/python3.15\0server/server.py\0")
            self.assertFalse(is_test_user_server(123, proc))

    def test_auto_started_server_receives_private_snapshot_path(self) -> None:
        from scripts.profile_local_server import main

        with tempfile.TemporaryDirectory() as directory:
            timeline = Path(directory) / "timeline.json"
            fake_server = Mock(pid=12345)
            server_start = Mock(return_value=fake_server)

            def fake_run(args, **_kwargs):
                # Only the profiler invocation occurs with --no-sudo.
                output = Path(args[args.index("-o") + 1])
                output.write_text('{"meta": {}}', encoding="utf-8")
                return SimpleNamespace(returncode=0)

            def fake_stop(_server):
                env = server_start.call_args.kwargs["env"]
                Path(env["PYCHESS_LOOP_LAG_SNAPSHOT_PATH"]).write_text(
                    '{"event_loop_lag": {}}', encoding="utf-8"
                )

            with (
                patch.dict("os.environ", {"MONGO_HOST": "mongodb://127.0.0.1:27017"}),
                patch(
                    "scripts.profile_local_server.ensure_local_mode",
                    return_value="http://127.0.0.1:8080",
                ),
                patch("scripts.profile_local_server.find_local_server_pids", return_value=[]),
                patch(
                    "scripts.profile_local_server.socket.create_connection",
                    side_effect=ConnectionRefusedError,
                ),
                patch("scripts.profile_local_server.subprocess.Popen", server_start),
                patch("scripts.profile_local_server.wait_until_ready"),
                patch("scripts.profile_local_server.assert_python315_process"),
                patch("scripts.profile_local_server.subprocess.run", side_effect=fake_run),
                patch("scripts.profile_local_server.stop_server", side_effect=fake_stop),
            ):
                code = main(["--no-sudo", "--duration", "1", "--output", str(timeline)])

            self.assertEqual(code, 0)
            env = server_start.call_args.kwargs["env"]
            self.assertEqual(env["PYCHESS_LOOP_LAG_ENABLED"], "1")
            self.assertEqual(
                env["PYCHESS_LOOP_LAG_SNAPSHOT_PATH"],
                str(Path(directory) / "event-loop-lag.json"),
            )
            self.assertTrue(timeline.is_file())
            self.assertTrue((Path(directory) / "event-loop-lag.json").is_file())

    def test_local_profile_rejects_production_uri(self) -> None:
        from scripts.profile_local_server import ensure_local_mode

        with (
            patch.dict("os.environ", {"URI": "https://www.pychess.org"}),
            self.assertRaises(SystemExit),
        ):
            ensure_local_mode()


class MixedHttpWorkloadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

        async def handler(request: web.Request) -> web.Response:
            self.calls.append(
                (request.path, request.query_string, request.cookies.get("AIOHTTP_SESSION"))
            )
            if request.path.endswith("/pgn"):
                return web.Response(text='[Event "test"]\n', content_type="text/pgn")
            return web.Response(text="ok")

        app = web.Application()
        app.router.add_get("/{tail:.*}", handler)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        sockets = site._server.sockets
        assert sockets is not None
        port = sockets[0].getsockname()[1]
        self.patch = patch.object(stress, "URI", f"http://127.0.0.1:{port}")
        self.patch.start()

    async def asyncTearDown(self) -> None:
        self.patch.stop()
        await self.runner.cleanup()

    async def test_authenticated_pgn_does_not_leak_cookie_to_public_requests(self) -> None:
        stats = await stress.run_http_workload(
            rps=30,
            duration=0.8,
            concurrency=3,
            pgn_cookie="test-secret",
            pgn_max_games=25,
        )
        self.assertGreater(stats.counts["games"], 0)
        self.assertEqual(stats.pgn_ok, 1)
        self.assertEqual(stats.pgn_empty, 0)
        pgn_calls = [call for call in self.calls if call[0].endswith("/pgn")]
        self.assertEqual(
            pgn_calls,
            [("/api/games/user/gbtami/pgn", "max=25", "test-secret")],
        )
        for path, _, cookie in self.calls:
            if not path.endswith("/pgn"):
                self.assertIsNone(cookie)

    async def test_test_user_can_export_own_pgn_from_game_session(self) -> None:
        exporter = stress.TestUserPgnExporter(max_games=25)
        async with stress.aiohttp.ClientSession(
            cookie_jar=stress.make_cookie_jar(),
            cookies={"AIOHTTP_SESSION": "test-session"},
        ) as session:
            await exporter.maybe_export(session, stress.TEST_PREFIX + "Example")
            await exporter.maybe_export(session, stress.TEST_PREFIX + "Another")
        self.assertTrue(exporter.attempted)
        self.assertEqual(exporter.username, stress.TEST_PREFIX + "Example")
        self.assertEqual(exporter.status, 200)
        self.assertGreater(exporter.bytes_received, 0)
        pgn_calls = [call for call in self.calls if call[0].endswith("/pgn")]
        self.assertEqual(
            pgn_calls,
            [(f"/api/games/user/{stress.TEST_PREFIX}Example/pgn", "max=25", "test-session")],
        )

    async def test_test_user_export_ignores_non_test_username(self) -> None:
        exporter = stress.TestUserPgnExporter(max_games=25)
        async with stress.aiohttp.ClientSession(cookie_jar=stress.make_cookie_jar()) as session:
            await exporter.maybe_export(session, "gbtami")
        self.assertFalse(exporter.attempted)
        self.assertEqual(self.calls, [])

    async def test_anonymous_workload_does_not_call_private_export(self) -> None:
        stats = await stress.run_http_workload(
            rps=10,
            duration=0.5,
            concurrency=2,
            pgn_cookie=None,
            pgn_max_games=10,
        )
        self.assertNotIn("pgn", stats.counts)
        self.assertTrue(self.calls)
        self.assertTrue(all("pgn" not in path for path, _, _ in self.calls))
