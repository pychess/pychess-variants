from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import patch

from event_loop_lag import EventLoopLagMonitor


class EventLoopLagMonitorTests(unittest.TestCase):
    def test_thresholds_aggregated_logs_and_snapshot(self):
        monitor = EventLoopLagMonitor(enabled=True)
        with patch("event_loop_lag.log.warning") as warning:
            monitor.record_lag(12.0, now=1.0)
            monitor.record_lag(24.5, now=2.0)
            monitor.record_lag(55.0, now=3.0)
            monitor.record_lag(120.0, now=4.0)
            monitor.record_lag(260.0, now=5.0)
            # The next timer tick flushes pending warnings after the cooldown,
            # even if it sees only an ordinary (short) delay.
            monitor._maybe_warn(now=65.0)
            monitor.record_lag(180.0, now=66.0)

        snapshot = monitor.snapshot()
        self.assertEqual(snapshot["checks"], 6)
        self.assertEqual(snapshot["stalls_20ms"], 5)
        self.assertEqual(snapshot["stalls_50ms"], 4)
        self.assertEqual(snapshot["stalls_100ms"], 3)
        self.assertEqual(snapshot["stalls_250ms"], 1)
        self.assertEqual(snapshot["max_lag_ms"], 260.0)
        self.assertIsNotNone(snapshot["max_lag_utc"])
        self.assertEqual(snapshot["last_lag_ms"], 180.0)
        self.assertIsNotNone(snapshot["last_stall_utc"])
        self.assertEqual(warning.call_count, 2)  # at most once per 60 seconds
        self.assertEqual(warning.call_args.args[1], 260.0)
        self.assertEqual(warning.call_args.args[3:5], (1, 100.0))

    def test_monitor_disabled_by_default(self):
        monitor = EventLoopLagMonitor()
        self.assertFalse(monitor.enabled)
        with patch("asyncio.get_event_loop") as get_loop:
            monitor.start(get_loop())
        self.assertEqual(monitor.snapshot()["checks"], 0)
        monitor.stop()


class EventLoopLagSchedulingTests(unittest.IsolatedAsyncioTestCase):
    async def test_synchronous_block_registers_lag_and_stop_cancels_timer(self):
        monitor = EventLoopLagMonitor(enabled=True)
        with (
            patch("event_loop_lag.CHECK_INTERVAL_SECONDS", 0.005),
            patch("event_loop_lag.log.warning"),
        ):
            monitor.start(asyncio.get_running_loop())
            await asyncio.sleep(0.02)
            # Intentionally block only this test's event loop, not production.
            time.sleep(0.12)  # noqa: ASYNC251
            await asyncio.sleep(0.02)
            monitor.stop()
            old_checks = monitor.checks
            await asyncio.sleep(0.02)

        self.assertGreater(monitor.stalls_50ms, 0)
        self.assertEqual(monitor.checks, old_checks)
