"""Low-cost, app-owned event-loop scheduling lag measurements.

This records scheduler delay, not the stack of the callback responsible for it.
Correlate UTC warning timestamps with a separate sampling profiler capture.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from aiohttp import web

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 0.05
STALL_THRESHOLD_MS = 20.0
LOG_THRESHOLD_MS = 100.0
LOG_INTERVAL_SECONDS = 60.0


class EventLoopLagMonitor:
    """Use one scheduled callback; do no heap walks and create no polling tasks."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.checks = 0
        self.stalls_20ms = 0
        self.stalls_50ms = 0
        self.stalls_100ms = 0
        self.stalls_250ms = 0
        self.max_lag_ms = 0.0
        self.max_lag_utc: str | None = None
        self.last_lag_ms = 0.0
        self.last_stall_utc: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._handle: asyncio.TimerHandle | None = None
        self._next_log_at = 0.0
        self._unlogged_stalls = 0
        self._unlogged_max_ms = 0.0
        self._unlogged_peak_utc: str | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if not self.enabled or self._handle is not None:
            return
        self._loop = loop
        self._schedule(loop.time())

    def _schedule(self, now: float) -> None:
        if self._loop is not None:
            expected = now + CHECK_INTERVAL_SECONDS
            self._handle = self._loop.call_at(expected, self._tick, expected)

    def _tick(self, expected: float) -> None:
        loop = self._loop
        if loop is None:
            return
        now = loop.time()
        self.record_lag(max(0.0, (now - expected) * 1000.0), now=now)
        # Flush pending warnings even if no further stalls occur after the limit.
        self._maybe_warn(now)
        # Do not schedule a flood of overdue callbacks after one long stall.
        self._schedule(now)

    def record_lag(self, lag_ms: float, *, now: float) -> None:
        """Record a sample (separate from scheduling for deterministic tests)."""
        self.checks += 1
        if lag_ms < STALL_THRESHOLD_MS:
            return

        self.stalls_20ms += 1
        if lag_ms >= 50.0:
            self.stalls_50ms += 1
        if lag_ms >= 100.0:
            self.stalls_100ms += 1
        if lag_ms >= 250.0:
            self.stalls_250ms += 1
        self.last_lag_ms = lag_ms
        self.last_stall_utc = datetime.now(UTC).isoformat()
        if lag_ms > self.max_lag_ms:
            self.max_lag_ms = lag_ms
            self.max_lag_utc = self.last_stall_utc

        # Only unusually long stalls cause logs. Aggregate them rather than
        # logging repeatedly while gameplay is already experiencing a delay.
        if lag_ms >= LOG_THRESHOLD_MS:
            self._unlogged_stalls += 1
            if lag_ms > self._unlogged_max_ms:
                self._unlogged_max_ms = lag_ms
                self._unlogged_peak_utc = self.last_stall_utc
            self._maybe_warn(now)

    def _maybe_warn(self, now: float) -> None:
        if not self._unlogged_stalls or now < self._next_log_at:
            return
        log.warning(
            "Event-loop scheduling lag: peak %.1f ms observed %s UTC, "
            "%d stalls >= %.0f ms since previous warning; "
            "sample interval %.0f ms",
            self._unlogged_max_ms,
            self._unlogged_peak_utc,
            self._unlogged_stalls,
            LOG_THRESHOLD_MS,
            CHECK_INTERVAL_SECONDS * 1000,
        )
        self._unlogged_stalls = 0
        self._unlogged_max_ms = 0.0
        self._unlogged_peak_utc = None
        self._next_log_at = now + LOG_INTERVAL_SECONDS

    def snapshot(self) -> dict[str, bool | int | float | str | None]:
        return {
            "enabled": self.enabled,
            "checks": self.checks,
            "stalls_20ms": self.stalls_20ms,
            "stalls_50ms": self.stalls_50ms,
            "stalls_100ms": self.stalls_100ms,
            "stalls_250ms": self.stalls_250ms,
            "max_lag_ms": round(self.max_lag_ms, 2),
            "max_lag_utc": self.max_lag_utc,
            "last_lag_ms": round(self.last_lag_ms, 2),
            "last_stall_utc": self.last_stall_utc,
        }

    def stop(self) -> None:
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        self._loop = None


loop_lag_monitor_key = web.AppKey("event_loop_lag_monitor", EventLoopLagMonitor)


async def loop_lag_context(app: web.Application) -> AsyncIterator[None]:
    monitor = app[loop_lag_monitor_key]
    monitor.start(asyncio.get_running_loop())
    try:
        yield
    finally:
        monitor.stop()
