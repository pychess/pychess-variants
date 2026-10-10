import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import test_logger
from aiohttp.test_utils import AioHTTPTestCase
from fairy.fairy_board import FOG_FEN_CACHE_SIZE
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from server_metrics import _peak_rss_kib, memory_stats, process_memory_stats
from tournament.tournament import PLAYER_JSON_CACHE_SIZE
from user import User

from server import make_app

test_logger.init_test_logger()


class ServerMetricsMemoryStatsTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_full_queue_diagnostics_do_not_serialize_payloads(self):
        queue = asyncio.Queue[str](maxsize=4)
        queue.put_nowait("sensitive-payload")

        with patch("server_metrics.gc.get_objects", return_value=[queue]):
            _stats, _tasks, queues, _counts = await memory_stats()

        self.assertEqual(
            queues,
            [
                {
                    "id": id(queue),
                    "name": "Queue",
                    "size": 1,
                    "maxsize": 4,
                    "full": False,
                    "file": "-",
                    "source": "-",
                }
            ],
        )
        self.assertNotIn("sensitive-payload", str(queues))


class PeakRssUnitTestCase(unittest.TestCase):
    """``ru_maxrss`` is kibibytes everywhere except macOS, where it is bytes."""

    def test_linux_value_is_already_kibibytes(self):
        self.assertEqual(_peak_rss_kib(65_536, "linux"), 65_536)

    def test_macos_value_is_bytes(self):
        self.assertEqual(_peak_rss_kib(65_536 * 1024, "darwin"), 65_536)

    def test_bsd_value_is_already_kibibytes(self):
        # FreeBSD's getrusage(2) documents kilobytes, like Linux; only macOS
        # reports bytes. Converting here would under-report RSS 1024x.
        self.assertEqual(_peak_rss_kib(65_536, "freebsd"), 65_536)

    def test_process_memory_stats_converts_using_the_platform(self):
        """The call site has to forward sys.platform, not assume one unit."""
        with patch("server_metrics.resource") as resource_module:
            resource_module.getrusage.return_value.ru_maxrss = 65_536 * 1024

            with patch("server_metrics.sys.platform", "darwin"):
                darwin_stats = process_memory_stats()
            with patch("server_metrics.sys.platform", "linux"):
                linux_stats = process_memory_stats()

        self.assertEqual(darwin_stats["peak_rss_kib"], 65_536)
        self.assertEqual(darwin_stats["peak_rss_mib"], 64.0)
        self.assertEqual(linux_stats["peak_rss_kib"], 65_536 * 1024)


class ServerMetricsDiagnosticsTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    async def test_lightweight_summary_skips_heap_walk_and_reports_quota_memory(self):
        app_state = get_app_state(self.app)
        app_state.catalogued_variants["metric_probe"] = {
            "ini": "abc",
            "pieceSet": {"wP": {"svg": "piece", "size": 5}},
            "boardSvg": {"svg": "board", "size": 5},
        }

        with patch("server_metrics.memory_stats", side_effect=AssertionError("heap walk called")):
            response = await self.client.get(
                "/metrics?summary=True",
                headers={"Authorization": "Bearer test"},
            )

        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(payload["mode"], "summary")
        self.assertNotIn("object_details", payload)

        process_memory = payload["process_memory"]
        self.assertGreater(process_memory["rss_kib"], 0)
        self.assertGreaterEqual(process_memory["swap_kib"], 0)
        self.assertEqual(
            process_memory["rss_plus_swap_kib"],
            process_memory["rss_kib"] + process_memory["swap_kib"],
        )
        self.assertGreater(process_memory["allocated_blocks"], 0)

        state = payload["state"]
        self.assertGreater(state["active_tasks"], 0)
        self.assertGreaterEqual(state["pyffish_variants"], state["catalogued_variants"])
        self.assertGreaterEqual(state["tournaments"], state["finished_tournaments"])
        self.assertGreaterEqual(
            state["tournament_user_references"],
            state["finished_tournament_user_references"],
        )
        self.assertGreaterEqual(state["tournament_active_sockets"], 0)
        self.assertEqual(state["catalogued_ini_bytes"], 3)
        self.assertEqual(state["catalogued_piece_svg_bytes"], 5)
        self.assertEqual(state["catalogued_board_svg_bytes"], 5)
        self.assertEqual(state["catalogued_payload_bytes"], 13)

        queue = asyncio.Queue[str](maxsize=2)
        queue.put_nowait("first")
        queue.put_nowait("second")
        app_state.game_channels.add(queue)
        response = await self.client.get(
            "/metrics?summary=True",
            headers={"Authorization": "Bearer test"},
        )
        streams = (await response.json())["streams"]
        self.assertEqual(streams["game_sse"], 1)
        self.assertEqual(streams["game_sse_queued_messages"], 2)
        self.assertEqual(streams["game_sse_max_queue"], 2)
        self.assertEqual(streams["game_sse_full_queues"], 1)
        self.assertEqual(streams["sse_queued_messages"], 2)
        self.assertEqual(streams["sse_max_queue"], 2)
        self.assertEqual(streams["sse_full_queues"], 1)
        self.assertGreaterEqual(streams["bot_event_queued_messages"], 0)
        self.assertGreaterEqual(streams["bot_game_queued_messages"], 0)
        self.assertGreaterEqual(streams["bot_max_queue"], 0)
        self.assertGreaterEqual(streams["study_websockets"], 0)

    async def test_metrics_anon_summary_has_bucket_and_detached_diagnostics(self):
        app_state = get_app_state(self.app)

        anon_recent = User(app_state, anon=True)
        anon_recent.last_seen = datetime.now(UTC) - timedelta(minutes=5)
        app_state.users[anon_recent.username] = anon_recent

        anon_mid = User(app_state, anon=True)
        anon_mid.last_seen = datetime.now(UTC) - timedelta(minutes=30)
        app_state.users[anon_mid.username] = anon_mid

        anon_default = User(app_state, anon=True)
        app_state.users[anon_default.username] = anon_default

        # memory_stats() has focused coverage above. Avoid a real whole-heap
        # traversal here; this test is about assembling endpoint diagnostics.
        with patch("server_metrics.memory_stats", return_value=([], [], [], {})) as stats_mock:
            response = await self.client.get(
                "/metrics?inspect=True",
                headers={"Authorization": "Bearer test"},
            )
        self.assertEqual(stats_mock.call_args.args, (15, True))
        self.assertEqual(response.status, 200)
        payload = await response.json()

        anon_summary_rows = payload["object_details"]["anon_summary"]
        self.assertEqual(len(anon_summary_rows), 1)
        summary = anon_summary_rows[0]

        required_keys = (
            "anon_total",
            "anon_with_default_last_seen",
            "anon_idle_lt_10m",
            "anon_idle_10m_to_60m",
            "anon_idle_over_60m",
            "anon_with_pending_remove_task",
            "anon_pending_remove_idle_default",
            "anon_pending_remove_idle_lt_10m",
            "anon_pending_remove_idle_10m_to_60m",
            "anon_pending_remove_idle_over_60m",
            "anon_removable_now",
            "anon_removable_idle_default",
            "anon_removable_idle_lt_10m",
            "anon_removable_idle_10m_to_60m",
            "anon_removable_idle_over_60m",
            "cached_users",
            "user_objects_total",
            "detached_user_objects",
        )
        for key in required_keys:
            self.assertIn(key, summary)

        idle_bucket_total = (
            summary["anon_with_default_last_seen"]
            + summary["anon_idle_lt_10m"]
            + summary["anon_idle_10m_to_60m"]
            + summary["anon_idle_over_60m"]
        )
        self.assertEqual(idle_bucket_total, summary["anon_total"])

        pending_bucket_total = (
            summary["anon_pending_remove_idle_default"]
            + summary["anon_pending_remove_idle_lt_10m"]
            + summary["anon_pending_remove_idle_10m_to_60m"]
            + summary["anon_pending_remove_idle_over_60m"]
        )
        self.assertEqual(pending_bucket_total, summary["anon_with_pending_remove_task"])

        removable_bucket_total = (
            summary["anon_removable_idle_default"]
            + summary["anon_removable_idle_lt_10m"]
            + summary["anon_removable_idle_10m_to_60m"]
            + summary["anon_removable_idle_over_60m"]
        )
        self.assertEqual(removable_bucket_total, summary["anon_removable_now"])

        expected_detached = max(0, summary["user_objects_total"] - summary["cached_users"])
        self.assertEqual(summary["detached_user_objects"], expected_detached)

        cache_rows = {row["name"]: row for row in payload["object_details"]["caches"]}
        self.assertEqual(cache_rows["fog_fen"]["maxsize"], FOG_FEN_CACHE_SIZE)
        self.assertEqual(cache_rows["tournament_player_json"]["maxsize"], PLAYER_JSON_CACHE_SIZE)
        self.assertTrue(all(row["maxsize"] > 0 for row in cache_rows.values()))
        self.assertEqual(
            payload["object_counts"]["caches"],
            sum(row["currsize"] for row in cache_rows.values()),
        )

        state = payload["object_details"]["state"][0]
        for key in (
            "user_perf_entries",
            "user_puzzle_perf_entries",
            "tournaments",
            "simuls",
            "catalogued_variants",
            "fishnet_works",
            "fishnet_queue",
            "fishnet_payloads",
            "fishnet_payload_bytes",
            "public_profile_cache",
            "public_title_cache",
            "request_limit_buckets",
            "request_block_log",
        ):
            self.assertIn(key, state)

        registered = payload["object_details"]["registered_summary"][0]
        for key in (
            "registered_total",
            "registered_online",
            "registered_offline",
            "registered_never_connected",
            "registered_cache_only",
            "registered_cache_evictions",
            "registered_cache_tracked",
            "registered_notification_users",
            "registered_notification_entries",
        ):
            self.assertIn(key, registered)

        streams = payload["object_details"]["streams"][0]
        for key in (
            "lobby_websockets",
            "game_websockets",
            "tournament_websockets",
            "simul_websockets",
            "game_sse",
            "invite_sse",
            "notify_sse",
            "inbox_sse",
            "challenge_sse",
            "active_bot_game_streams",
            "sse_queued_messages",
            "sse_max_queue",
            "sse_full_queues",
            "invite_sse_queued_messages",
            "notify_sse_queued_messages",
            "inbox_sse_queued_messages",
            "challenge_sse_queued_messages",
            "bot_event_queued_messages",
            "bot_game_queued_messages",
            "bot_max_queue",
        ):
            self.assertIn(key, streams)

        process_memory = payload["object_details"]["process_memory"][0]
        self.assertGreater(process_memory["rss_kib"], 0)
        self.assertGreaterEqual(process_memory["swap_kib"], 0)
        self.assertEqual(
            process_memory["rss_plus_swap_kib"],
            process_memory["rss_kib"] + process_memory["swap_kib"],
        )
        self.assertGreater(process_memory["peak_rss_kib"], 0)
        self.assertEqual(payload["object_counts"]["process_memory"], process_memory["rss_kib"])


class CooperativeMetricsTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_heap_scan_yields_without_forcing_gc(self):
        from server_metrics import METRICS_BATCH_SIZE

        objects = [object() for _ in range(METRICS_BATCH_SIZE * 8)]
        with (
            patch("server_metrics.gc.get_objects", return_value=objects),
            patch("server_metrics.gc.collect", side_effect=AssertionError("forced GC")),
            patch("server_metrics.METRICS_SLICE_SECONDS", 0),
        ):
            scan = asyncio.create_task(memory_stats())
            ticks = 0
            while not scan.done():
                ticks += 1
                await asyncio.sleep(0)
            await scan
        self.assertGreater(ticks, 3)

    async def test_deep_size_preserves_shared_reference_and_cycle_conventions(self):
        import sys

        from server_metrics import get_deep_size

        item = ["shared"]
        root = [item, item]
        root.append(root)
        expected = sys.getsizeof(root) + sys.getsizeof(item) + sys.getsizeof("shared")
        self.assertEqual(await get_deep_size(root), expected)

    async def test_deep_size_survives_mutation_while_yielding(self):
        from server_metrics import get_deep_size

        root = {index: [index] for index in range(2048)}
        with patch("server_metrics.METRICS_SLICE_SECONDS", 0):
            scan = asyncio.create_task(get_deep_size(root))
            await asyncio.sleep(0)
            root.clear()
            root["new"] = []
            self.assertGreater(await scan, 0)


class FullMetricsCacheTestCase(AioHTTPTestCase):
    async def get_application(self):
        return make_app(db_client=AsyncMongoMockClient(tz_aware=True))

    async def tearDownAsync(self):
        await self.client.close()

    async def test_worker_encoding_preserves_legacy_bson_integers(self):
        from bson import Int64

        with patch("server_metrics._full_metrics", return_value={"base": Int64(3)}):
            response = await self.client.get("/metrics", headers={"Authorization": "Bearer test"})
        self.assertEqual(await response.json(), {"base": 3})

    async def test_concurrent_full_requests_share_work_and_summary_stays_available(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def collect(*args, **kwargs):
            started.set()
            await release.wait()
            return [], [], [], {}

        with patch("server_metrics.memory_stats", side_effect=collect) as collect_mock:
            requests = [
                asyncio.create_task(
                    self.client.get("/metrics", headers={"Authorization": "Bearer test"})
                )
                for _ in range(4)
            ]
            try:
                await asyncio.wait_for(started.wait(), 2)
                summary = await asyncio.wait_for(
                    self.client.get(
                        "/metrics?summary=True", headers={"Authorization": "Bearer test"}
                    ),
                    2,
                )
                self.assertEqual((await summary.json())["mode"], "summary")
                self.assertEqual(collect_mock.call_count, 1)
            finally:
                release.set()
            responses = await asyncio.gather(*requests)
            bodies = [await response.read() for response in responses]
            self.assertTrue(all(body == bodies[0] for body in bodies))
            self.assertEqual(responses[0].headers["Cache-Control"], "no-store")
            self.assertFalse((await responses[0].json())["heap_gc_collected"])
            repeat = await self.client.get("/metrics", headers={"Authorization": "Bearer test"})
            self.assertEqual(await repeat.read(), bodies[0])
            self.assertEqual(collect_mock.call_count, 1)

    async def test_cache_expiry_recollects(self):
        with patch("server_metrics.memory_stats", return_value=([], [], [], {})) as collect:
            await self.client.get("/metrics", headers={"Authorization": "Bearer test"})
            get_app_state(self.app).full_metrics_snapshot.expires_at = 0
            await self.client.get("/metrics", headers={"Authorization": "Bearer test"})
        self.assertEqual(collect.call_count, 2)

    async def test_inspection_upgrade_is_serialized_and_serves_normal_requests(self):
        from types import SimpleNamespace
        from typing import cast

        from aiohttp import web

        state = get_app_state(self.app)
        request = cast(web.Request, SimpleNamespace(app=self.app))
        started = asyncio.Event()
        release = asyncio.Event()
        modes = []
        active = 0
        max_active = 0

        async def collect(_state, _request, inspect):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            modes.append(inspect)
            if not inspect:
                started.set()
                await release.wait()
            active -= 1
            return {"inspected": inspect}

        with patch("server_metrics._full_metrics", side_effect=collect):
            normal = asyncio.create_task(state.full_metrics_snapshot.get(state, request, False))
            await started.wait()
            inspected = asyncio.create_task(state.full_metrics_snapshot.get(state, request, True))
            await asyncio.sleep(0)
            release.set()
            normal_body, inspected_body = await asyncio.gather(normal, inspected)
            cached = await state.full_metrics_snapshot.get(state, request, False)
        self.assertEqual(modes, [False, True])
        self.assertEqual(max_active, 1)
        self.assertIn(b"false", normal_body)
        self.assertIn(b"true", inspected_body)
        self.assertEqual(cached, inspected_body)

    async def test_cancelling_one_waiter_keeps_shared_work_owned_until_completion(self):
        from types import SimpleNamespace
        from typing import cast

        from aiohttp import web

        state = get_app_state(self.app)
        request = cast(web.Request, SimpleNamespace(app=self.app))
        started = asyncio.Event()
        release = asyncio.Event()

        async def collect(*args):
            started.set()
            await release.wait()
            return {"snapshot": True}

        with patch("server_metrics._full_metrics", side_effect=collect) as collect_mock:
            waiter = asyncio.create_task(state.full_metrics_snapshot.get(state, request, False))
            await started.wait()
            task = state.full_metrics_snapshot.task
            self.assertIn(task, state.background_tasks)
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            self.assertFalse(task.cancelled())
            release.set()
            await state.full_metrics_snapshot.get(state, request, False)
            await asyncio.sleep(0)
            self.assertEqual(collect_mock.call_count, 1)
        self.assertIsNone(state.full_metrics_snapshot.task)
        self.assertNotIn(task, state.background_tasks)

    async def test_failed_snapshot_can_be_retried(self):
        from types import SimpleNamespace
        from typing import cast

        from aiohttp import web

        state = get_app_state(self.app)
        request = cast(web.Request, SimpleNamespace(app=self.app))
        with patch(
            "server_metrics._full_metrics", side_effect=[RuntimeError("probe"), {"ok": True}]
        ):
            with self.assertRaises(RuntimeError):
                await state.full_metrics_snapshot.get(state, request, False)
            result = await state.full_metrics_snapshot.get(state, request, False)
        self.assertIn(b"true", result)

    async def test_authentication_is_checked_before_reading_cached_data(self):
        state = get_app_state(self.app)
        state.full_metrics_snapshot.body = b'{"private":true}'
        state.full_metrics_snapshot.expires_at = float("inf")
        response = await self.client.get("/metrics")
        self.assertEqual(response.status, 404)
