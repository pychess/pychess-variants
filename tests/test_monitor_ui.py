from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from textual.widgets import DataTable, Label

from monitor.metrics_client import monitor_view
from monitor.monitor import MemoryMonitorApp

SUMMARY = {
    "mode": "summary",
    "timestamp": "2026-10-07T12:00:00Z",
    "process_memory": {"rss_kib": 4096, "swap_kib": 0},
    "state": {"users": 3, "games": 2, "active_tasks": 4, "lobby_connections": 1},
    "registered": {"registered_total": 3},
    "anonymous": {"anon_total": 0},
    "streams": {"lobby_websockets": 2},
    "caches": [{"name": "example", "currsize": 5}],
}
FULL = {
    "mode": "full",
    "timestamp": "2026-10-07T12:01:00Z",
    "object_details": {
        **monitor_view(SUMMARY)["object_details"],
        "users": [{"username": "probe"}],
        "anon_summary": [{"anon_total": 0, "anon_removable_now": 0}],
    },
    "object_counts": {"users": 3},
    "object_sizes": {"users": 1.5},
    "top_allocations": [{"type": "User", "count": 3, "size_bytes": 100, "size_human": "100 bytes"}],
}


class MonitorViewTestCase(unittest.TestCase):
    def test_summary_displays_counters_without_inventing_heap_rows_or_sizes(self):
        view = monitor_view(SUMMARY)
        self.assertEqual(view["object_counts"]["users"], 3)
        self.assertEqual(view["object_counts"]["tasks"], 4)
        self.assertEqual(view["object_counts"]["caches"], 5)
        self.assertEqual(view["object_counts"]["connections"], 1)
        self.assertEqual(view["object_details"]["users"], [])
        self.assertEqual(view["object_details"]["process_memory"], [SUMMARY["process_memory"]])
        self.assertEqual(view["object_sizes"], {"process_memory": 4096})
        self.assertEqual(view["top_allocations"], [])
        self.assertNotIn("object_details", SUMMARY)
        self.assertIs(monitor_view(FULL), FULL)


class MonitorUITestCase(unittest.IsolatedAsyncioTestCase):
    async def test_polling_is_summary_only_and_details_are_manual(self):
        with (
            patch.dict("os.environ", {"PYCHESS_MONITOR_INTERVAL_SECONDS": "600"}),
            patch(
                "monitor.monitor.fetch_metrics",
                new=AsyncMock(side_effect=[SUMMARY, FULL, FULL, SUMMARY]),
            ) as fetch,
        ):
            app = MemoryMonitorApp()
            async with app.run_test(size=(160, 60)) as pilot:
                self.assertTrue(fetch.call_args.kwargs["summary_only"])
                self.assertIn("Summary", str(app.query_one("#metrics_status", Label).render()))
                self.assertEqual(app.query_one("#users_table", DataTable).row_count, 0)
                await pilot.press("d")
                self.assertFalse(fetch.call_args.kwargs["summary_only"])
                self.assertFalse(fetch.call_args.kwargs["inspect_tasks"])
                self.assertEqual(app.query_one("#users_table", DataTable).row_count, 1)
                self.assertIn(
                    "Anon Removable Now", [label for label, _ in app.column_configs["anon_summary"]]
                )
                await pilot.press("i")
                self.assertTrue(fetch.call_args.kwargs["inspect_tasks"])
                app.monitoring = False
                await app.update_metrics()
                self.assertEqual(fetch.await_count, 3)
                app.monitoring = True
                await app.update_metrics()
                self.assertTrue(fetch.call_args.kwargs["summary_only"])
                self.assertEqual(app.query_one("#users_table", DataTable).row_count, 0)
                self.assertEqual(app.top_allocations, [])
                self.assertIn(
                    "not measured", str(app.query_one("#users_mem_label", Label).render())
                )
