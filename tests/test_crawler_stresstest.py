from __future__ import annotations

import asyncio
import gzip
import io
import socket
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web
from aiohttp.test_utils import TestServer
from crawler_assets import (
    PRODUCTION_STATIC_ROOT,
    AssetLoad,
    PageAssets,
    local_asset_path,
    slow_socket,
)
from crawler_snapshot import MARKER, PREFIX, validate_snapshot
from crawler_stresstest import (
    SAMPLE_LIMIT,
    Latencies,
    Requests,
    Run,
    cgroup_stats,
    fixture_environment,
    make_output_directory,
    parse_args,
    process_memory,
)


class CrawlerStressTestCase(unittest.TestCase):
    def make_run(self):
        args = parse_args(["--cycles", "1", "--recovery-seconds", "65"])
        run = Run(args, Path("/unused-crawler-output"))
        run.fixture = {"cookie": "private-cookie", "probe_key": "private-probe-key"}
        state = {
            key: 0
            for key in (
                "users",
                "anonymous_users",
                "public_profiles",
                "games",
                "tasks",
                "limiter_keys",
                "html_inflight",
                "profile_inflight",
                "event_loop_lag_ms",
            )
        }
        run.samples = [
            {"phase": "baseline", "budget_usage_mib": 100, "peak_rss_mib": 100, "server": state},
            {"phase": "recovery-1", "budget_usage_mib": 102, "peak_rss_mib": 110, "server": state},
        ]
        run.phase = "attack-1"
        for kind in ("authenticated_html", "game", "websocket"):
            for _ in range(3):
                run.requests(kind).record(200, 10)
        run.phase = "recovery-1"
        run.requests("anonymous_html").record(200, 10)
        return run

    def test_latency_reservoir_is_bounded_but_preserves_actual_count_and_maximum(self):
        values = Latencies()
        for value in range(10_000):
            values.add(value)
        summary = values.summary()
        self.assertEqual(len(values.samples), SAMPLE_LIMIT)
        self.assertEqual(summary["count"], 10_000)
        self.assertEqual(summary["max_ms"], 9999)
        self.assertGreater(summary["p95_ms"], 9000)

    def test_output_directory_is_private_and_existing_paths_are_not_modified(self):
        with tempfile.TemporaryDirectory() as parent:
            output = make_output_directory(str(Path(parent) / "results"))
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            (output / "sentinel").write_text("previous run")
            with self.assertRaises(FileExistsError):
                make_output_directory(str(output))
            self.assertEqual((output / "sentinel").read_text(), "previous run")

    def test_fast_rejections_do_not_hide_success_or_failure_latency(self):
        requests = Requests()
        requests.record(200, 120)
        requests.record(429, 1)
        requests.record("TimeoutError", 3000)
        summary = requests.summary()
        self.assertEqual(summary["accepted"]["p95_ms"], 120)
        self.assertEqual(summary["rejected"]["p95_ms"], 1)
        self.assertEqual(summary["failed"]["count"], 1)

    def test_invalid_or_unbounded_numeric_arguments_are_rejected(self):
        for option, value in (
            ("--rps", "nan"),
            ("--timeout", "inf"),
            ("--cycles", "0"),
            ("--profiles", "0"),
            ("--backend-delay-ms", "-1"),
            ("--max-memory-percent", "95"),
            ("--asset-rps", "nan"),
            ("--asset-kib-per-second", "-1"),
            ("--asset-concurrency", "0"),
            ("--asset-timeout", "inf"),
        ):
            with (
                self.subTest(option=option),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                parse_args([option, value])

    def test_fixture_environment_removes_service_credentials_and_enables_router_simulation(self):
        with patch.dict("os.environ", {"DISCORD_TOKEN": "canary", "FISHNET_KEYS": "canary"}):
            env = fixture_environment()
        self.assertNotIn("DISCORD_TOKEN", env)
        self.assertEqual(env["FISHNET_KEYS"], "{}")
        self.assertEqual(env["CLIENT_IP_MODE"], "heroku")
        self.assertEqual(env["PROD"], "true")
        self.assertEqual(env["STATIC_ROOT"], PRODUCTION_STATIC_ROOT)
        self.assertEqual(fixture_environment("/static")["STATIC_ROOT"], "/static")

    def test_asset_only_rate_defaults_to_requested_rate(self):
        self.assertEqual(parse_args(["--scenario", "assets", "--rps", "7"]).asset_rps, 7)
        self.assertEqual(parse_args([]).asset_rps, 0)

    def test_asset_discovery_keeps_local_js_and_wasm_but_excludes_cdn_and_other_origins(self):
        base = "http://127.0.0.1:1234"
        page = PageAssets()
        page.feed(
            '<script src="/static/pychess-variants.js?v=1"></script>'
            '<link rel="preload" as="fetch" href="/static/ffish.wasm?v=1">'
            '<script src="https://cdn.example/static/cardgame.js"></script>'
        )
        self.assertEqual(
            [local_asset_path(base, value) for value in page.urls],
            [
                "/static/pychess-variants.js?v=1",
                "/static/ffish.wasm?v=1",
                None,
            ],
        )
        for url in ("//localhost:1234/static/main.js", "/@/someone", "/static/image.png"):
            self.assertIsNone(local_asset_path(base, url))

    def test_slow_reader_bounds_the_kernel_receive_buffer(self):
        with slow_socket((socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))) as sock:
            # Linux doubles SO_RCVBUF for bookkeeping.
            self.assertLessEqual(sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF), 32768)

    def test_proc_memory_accounts_for_swap_and_startup_peak(self):
        with patch(
            "crawler_stresstest.Path.read_text",
            return_value=("VmRSS:\t102400 kB\nVmSwap:\t10240 kB\nVmHWM:\t204800 kB\n"),
        ):
            result = process_memory(123)
        self.assertEqual(result["rss_plus_swap_mib"], 110)
        self.assertEqual(result["peak_rss_mib"], 200)

    def test_successful_report_redacts_fixture_credentials(self):
        run = self.make_run()
        run.fixture.update(profile_names=["private-user"], catalogue_names=["private-variant"])
        report = run.report()
        self.assertEqual(report["fixture"], {})

    def test_startup_samples_contribute_to_memory_failure_without_requiring_http_telemetry(self):
        run = self.make_run()
        run.startup_samples = [{"budget_usage_mib": 450, "peak_rss_mib": 450}]
        report = run.report()
        self.assertFalse(report["passed"])
        self.assertEqual(report["startup_peak_mib"], 450)
        self.assertTrue(any("memory" in reason for reason in report["failures"]))
        self.assertFalse(any("telemetry" in reason for reason in report["failures"]))

    def test_database_workload_uses_snapshot_targets_and_escapes_path_segments(self):
        run = self.make_run()
        run.fixture.update(profile_names=["A/B"], catalogue_names=["realvariant"])
        self.assertEqual(run.attack_path(5), "/@/A%2FB?crawl=5")
        self.assertEqual(run.attack_path(17), "/variants/realvariant?crawl=17")
        self.assertEqual(run.attack_path(6), "/api/catalogued-variants?name=realvariant")

    def test_successful_report_includes_recovery_growth(self):
        report = self.make_run().report()
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["post_recovery_growth_mib"], 2)
        self.assertEqual(report["fixture"], {})

    def test_report_fails_for_memory_headroom_startup_peak_and_missing_telemetry(self):
        run = self.make_run()
        run.samples[-1]["peak_rss_mib"] = 450
        run.samples[-1].pop("server")
        report = run.report()
        self.assertFalse(report["passed"])
        self.assertTrue(any("memory" in reason for reason in report["failures"]))
        self.assertTrue(any("telemetry" in reason for reason in report["failures"]))

    def test_short_cgroup_memory_peaks_between_samples_count_against_quota(self):
        run = self.make_run()
        run.samples[-1]["cgroup"] = {"memory.peak": 450 * 1024**2}
        report = run.report()
        self.assertEqual(report["peak_budget_usage_mib"], 450)
        self.assertEqual(report["peak_rss_mib"], 110)
        self.assertFalse(report["passed"])
        run.args.constrain = False
        self.assertTrue(run.report()["passed"])

    def test_cgroup_memory_breakdown_includes_network_transmission_buffers(self):
        def read(path, *args, **kwargs):
            if str(path) == "/proc/123/cgroup":
                return "0::/crawler-test\n"
            if path.name == "memory.stat":
                return "sock 2097152\nanon 1048576\n"
            if path.name in {"memory.events", "cpu.stat"}:
                return "counter 0\n"
            return "10\n"

        with (
            patch("crawler_stresstest.Path.read_text", autospec=True, side_effect=read),
            patch("crawler_stresstest.Path.exists", return_value=True),
        ):
            stats = cgroup_stats(123)
        self.assertEqual(stats["memory.stat"]["sock"], 2 * 1024**2)

    def test_normal_user_redirects_or_rate_limits_are_failures(self):
        for status in (302, 429):
            with self.subTest(status=status):
                run = self.make_run()
                run.phase = "attack-1"
                run.requests("game").record(status, 1)
                self.assertFalse(run.report()["passed"])

    def test_event_loop_stalls_and_slow_normal_probes_are_failures(self):
        run = self.make_run()
        run.samples[-1]["server"]["event_loop_lag_ms"] = 1000
        run.phase = "attack-1"
        for _ in range(3):
            run.requests("websocket").record(200, 1000)
        report = run.report()
        self.assertFalse(report["passed"])
        self.assertTrue(any("event-loop delay" in reason for reason in report["failures"]))
        self.assertTrue(any("p95" in reason for reason in report["failures"]))

    def test_sustained_growth_underdelivered_load_and_failed_recovery_are_failures(self):
        run = self.make_run()
        run.samples[-1]["budget_usage_mib"] = 150
        run.phase = "attack-1"
        run.requests("crawler").offered = 100
        run.requests("crawler").client_dropped = 10
        run.phase = "recovery-1"
        run.requests("anonymous_html").record(429, 1)
        report = run.report()
        self.assertFalse(report["passed"])
        self.assertTrue(any("growth" in reason for reason in report["failures"]))
        self.assertTrue(any("generator dropped" in reason for reason in report["failures"]))
        self.assertTrue(any("did not recover" in reason for reason in report["failures"]))

    def test_asset_404s_incomplete_bodies_and_generator_drops_fail_the_report(self):
        for status in (404, "BodySizeMismatch", "TimeoutError"):
            run = self.make_run()
            run.phase = "attack-1"
            run.requests("asset:pychess-variants.js").record(status, 1)
            self.assertFalse(run.report()["passed"])
        run = self.make_run()
        run.phase = "attack-1"
        run.requests("asset_load").offered = 100
        run.requests("asset_load").client_dropped = 2
        self.assertFalse(run.report()["passed"])

    def test_valid_asset_downloads_and_conditional_304s_pass(self):
        run = self.make_run()
        run.phase = "attack-1"
        for status in (200, 304):
            run.requests("asset:pychess-variants.js").record(status, 10)
        self.assertTrue(run.report()["passed"])


class CrawlerPacingTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_asset_preflight_handles_chunked_html_and_never_follows_external_urls(self):
        async def page(request):
            if "X-Forwarded-For" not in request.headers:
                return web.Response(status=400)
            response = web.StreamResponse(headers={"Content-Type": "text/html"})
            await response.prepare(request)
            await response.write(b'<script src="/static/pychess-variants.js?v=abc"></script>')
            await asyncio.sleep(0.01)
            await response.write(
                b'<link rel="preload" href="/static/ffish.wasm?v=abc">'
                b'<script src="https://cdn.invalid/external.js"></script>'
            )
            return response

        async def asset(request):
            if "X-Forwarded-For" not in request.headers:
                return web.Response(status=400)
            content_type = (
                "application/wasm" if request.path.endswith(".wasm") else "text/javascript"
            )
            return web.Response(
                body=b"asset", content_type=content_type, headers={"ETag": '"asset"'}
            )

        app = web.Application()
        app.router.add_get("/analysis/chess", page)
        app.router.add_get("/static/{name}", asset)
        async with TestServer(app) as server:
            run = Run(parse_args(["--asset-cache", "warm"]), Path("/unused"))
            run.fixture = {"url": str(server.make_url("/")).rstrip("/")}
            await run.assets.prepare()
        self.assertEqual(len(run.assets.files), 8)
        self.assertEqual(run.assets.external, ["https://cdn.invalid/external.js"])
        worker = next(a for a in run.assets.files if a["name"] == "header-realtime-worker.js")
        self.assertEqual(worker["path"], "/static/header-realtime-worker.js?v=abc")

    async def test_missing_asset_is_a_preflight_failure(self):
        async def page(_request):
            return web.Response(
                text='<script src="/static/pychess-variants.js"></script>'
                '<link rel="preload" href="/static/ffish.wasm">'
            )

        app = web.Application()
        app.router.add_get("/analysis/chess", page)
        async with TestServer(app) as server:
            run = Run(parse_args([]), Path("/unused"))
            run.fixture = {"url": str(server.make_url("/")).rstrip("/")}
            with self.assertRaisesRegex(RuntimeError, "returned 404"):
                await run.assets.prepare()

    async def test_asset_transfer_counts_compressed_wire_bytes_and_conditional_hits(self):
        compressed = gzip.compress(b"compressed javascript payload" * 100)

        async def asset(request):
            if request.headers.get("If-None-Match") == '"asset-etag"':
                return web.Response(status=304, headers={"ETag": '"asset-etag"'})
            return web.Response(body=compressed, headers={"Content-Encoding": "gzip"})

        app = web.Application()
        app.router.add_get("/static/pychess-variants.js", asset)
        async with TestServer(app) as server:
            run = Run(parse_args(["--asset-encoding", "gzip"]), Path("/unused"))
            run.fixture = {"url": str(server.make_url("/")).rstrip("/")}
            target = {
                "name": "pychess-variants.js",
                "path": "/static/pychess-variants.js",
                "wire_bytes": len(compressed),
                "etag": '"asset-etag"',
            }
            load = AssetLoad(run)
            load.files = [target]
            import aiohttp

            async with aiohttp.ClientSession(auto_decompress=False) as session:
                stats = run.requests("asset:pychess-variants.js")
                await load.transfer(session, target, 1, stats)
                self.assertEqual(stats.received_bytes, len(compressed))
                run.args.asset_cache = "warm"
                await load.transfer(session, target, 2, stats)
            self.assertEqual(stats.statuses, {"200": 1, "304": 1})
            self.assertEqual(stats.received_bytes, len(compressed))
            self.assertEqual(stats.headers.count, 2)

    async def test_slow_asset_body_reads_are_paced_and_bounded_by_concurrency(self):
        async def asset(_request):
            return web.Response(body=b"x" * 65536)

        app = web.Application()
        app.router.add_get("/static/test.js", asset)
        async with TestServer(app) as server:
            args = parse_args(
                ["--asset-rps", "50", "--asset-concurrency", "2", "--asset-kib-per-second", "256"]
            )
            run = Run(args, Path("/unused"))
            run.fixture = {"url": str(server.make_url("/")).rstrip("/")}
            run.assets.files = [
                {
                    "name": "test.js",
                    "path": "/static/test.js",
                    "wire_bytes": 65536,
                    "etag": '"etag"',
                }
            ]
            await run.assets.flood(0.1)
            stats = run.requests("asset:test.js")
            self.assertEqual(run.assets.peak_inflight, 2)
            self.assertGreater(run.requests("asset_load").client_dropped, 0)
            self.assertEqual(stats.statuses, {"200": 2})
            self.assertGreaterEqual(stats.accepted.summary()["p50_ms"], 240)

    async def test_slow_transfers_stop_promptly_when_memory_stop_event_is_set(self):
        async def asset(_request):
            return web.Response(body=b"x" * 65536)

        app = web.Application()
        app.router.add_get("/static/test.js", asset)
        async with TestServer(app) as server:
            run = Run(parse_args(["--asset-kib-per-second", "1"]), Path("/unused"))
            run.fixture = {"url": str(server.make_url("/")).rstrip("/")}
            target = {"path": "/static/test.js", "wire_bytes": 65536, "etag": '"etag"'}
            import aiohttp

            async with aiohttp.ClientSession(auto_decompress=False) as session:
                stats = run.requests("asset:test.js")
                task = asyncio.create_task(run.assets.transfer(session, target, 1, stats))
                await asyncio.sleep(0.03)
                run.stop_load.set()
                await asyncio.wait_for(task, timeout=0.2)
            self.assertEqual(stats.statuses, {"Stopped": 1})
            self.assertEqual(run.assets.inflight, 0)

    async def test_snapshot_requires_scratch_name_and_marker_before_server_startup(self):
        client = MagicMock()
        collection = client.__getitem__.return_value.config
        collection.find_one = AsyncMock(return_value=None)
        for name in ("pychess-variants", "other-database"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                await validate_snapshot(client, name)
        client.__getitem__.assert_not_called()
        name = PREFIX + "example"
        with self.assertRaises(ValueError):
            await validate_snapshot(client, name)
        collection.find_one.return_value = MARKER
        await validate_snapshot(client, name)
        collection.find_one.assert_awaited_with(MARKER)

    async def test_open_loop_overload_is_counted_without_unbounded_client_tasks(self):

        inflight = 0
        peak = 0

        async def slow(_request):
            nonlocal inflight, peak
            inflight += 1
            peak = max(peak, inflight)
            try:
                await asyncio.sleep(0.05)
                return web.Response(text="done")
            finally:
                inflight -= 1

        app = web.Application()
        app.router.add_get("/api/catalogued-variants", slow)
        async with TestServer(app) as server:
            args = parse_args(["--concurrency", "2", "--rps", "200", "--scenario", "catalogue"])
            run = Run(args, Path("/unused-crawler-output"))
            run.fixture = {"url": str(server.make_url("/")).rstrip("/")}
            run.phase = "attack-1"
            await run.flood(0.2)
        stats = run.stats["attack-1"]["crawler"]
        self.assertEqual(peak, 2)
        self.assertGreater(stats.client_dropped, 0)
        self.assertEqual(stats.offered, stats.client_dropped + sum(stats.statuses.values()))


if __name__ == "__main__":
    unittest.main()
