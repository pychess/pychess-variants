# Event-loop lag and Python 3.15 Tachyon profiling

PyChess uses an aiohttp event loop. Awaiting MongoDB can make one request slow
without delaying other users; synchronous operations (including native pyffish
calls) can instead postpone *every* task on that loop.

## Opt-in local development diagnostics

A timer checks scheduling delay every 50 ms. The monitor uses one
`loop.call_at()` callback, no recurring task, stack inspection, or garbage
collection. It reschedules from the actual wake-up time to avoid a flood of
missed ticks after a long pause. Each missed deadline measures **scheduler lag**,
not exact synchronous-operation duration or the identity of the blocking task.
OS scheduling or a paused process can produce lag too.

- The monitor is **disabled by default everywhere**, including production,
  development, and tests. Opt in locally with `PYCHESS_LOOP_LAG_ENABLED=1`.
  Without that variable (or with `=0`), no monitoring callbacks are scheduled.
- `/metrics?summary=True` (authenticated as usual) includes `event_loop_lag`:
  total checks, cumulative counts of delays >=20/50/100/250 ms, lifetime peak,
  last recorded lag and UTC observation time, and peak observation time. Counters reset on each server process restart.
- Delays >=100 ms generate a WARNING with peak lag and timestamp. Warnings are
  throttled to one per 60 seconds per process; the summary counters still record
  every threshold crossing. No game, username, FEN, move or message is logged.
- `monitor/record.py`, if used against your local development server, includes
  the stall counters in private JSONL snapshots, prints the 100 ms count and peak,
  and calculates **deltas of counts**.
  The lifetime peak is *not* a delta: compare its values directly.
- Monitoring is approximate: one check samples scheduling lateness, not every
  individual 20 ms event. When the server is idle, reported lag should be near
  zero; under local test load, compare intervals and check the corresponding Tachyon samples.

Leave production on Python 3.14 and keep this opt-in monitor disabled there.
This change does not modify `.python-version`, project dependencies, or Heroku
configuration. If collecting metrics, do not increase production `/metrics`
polling frequency below the documented 60-second minimum.

## Correlating with Tachyon on Python 3.15

Tachyon profiles an **existing Python 3.15 process** with an external sampler.
Run it in parallel with the lag monitor, before reproducing an issue. A warning
includes the peak stall's observed UTC time T and measured delay X ms:
inspect samples near the interval **T - X ms to T**. A profile begun *after* the warning cannot
recover the call stack of a past stall.

First start your development server using your already installed Python 3.15
virtual environment, **explicitly opting in to the lag monitor**:

```bash
PYCHESS_LOOP_LAG_ENABLED=1 .venv/bin/python server/server.py
```

If your Python 3.15 environment has another name, use its interpreter instead
of `.venv/bin/python`. Verify the selected interpreter with `.venv/bin/python --version`.
This local setting does not affect Heroku, and the monitor also works on 3.14.
Then, in another shell, find the server PID
(e.g., `pgrep -af 'python.*server/server.py'`). For correlating
individual stalls, use the **Gecko timeline** format, which preserves sample
timestamps. A flame graph alone aggregates samples and loses their position in
time. Record the capture start in UTC to help align the timeline with the logs:

```bash
date -u +"capture started: %Y-%m-%dT%H:%M:%SZ"
.venv/bin/python -m profiling.sampling attach --gecko \
  -d 120 -o /tmp/pychess-timeline.json PID
```

Load the resulting JSON in [Firefox Profiler](https://profiler.firefox.com/)
and inspect the timeline near the stall's observed time. It can show Python
stacks and CPU/GIL/native-code markers. Keep profiles private: they can contain
sensitive source locations and runtime context.

For cumulative hotspots or logical async call chains, use separate captures:

```bash
# Python CPU hotspots (async-aware and --mode cpu are incompatible)
.venv/bin/python -m profiling.sampling attach --mode cpu --flamegraph \
  -d 120 -o /tmp/pychess-cpu.html PID

# Logical asyncio call chains; default wall-clock sampling
.venv/bin/python -m profiling.sampling attach --async-aware --flamegraph \
  -d 120 -o /tmp/pychess-async.html PID

# Mark Python-to-C/C++ transitions, without --async-aware
.venv/bin/python -m profiling.sampling attach --native --flamegraph \
  -d 120 -o /tmp/pychess-native.html PID
```

You can also launch the server under the profiler (`profiling.sampling run`)
if attaching is not permitted. On Linux, attach needs ptrace/process-memory
read permission and may not work in Heroku's restricted environment; test
locally first. Avoid weakening host security or assuming Heroku supports attach.

`--async-aware` is incompatible with `--mode cpu`, `--mode gil`, and `--native`.
Native output marks transitions but does not profile Fairy-Stockfish's internal
C++ frames; use a native profiler if the C++ call is the actual bottleneck.
Tachyon measures time, not allocation size; continue using existing memory
metrics to understand RSS and swap. Sampling can miss rare short stalls; for
those, add a targeted `time.perf_counter()` measurement around the suspected
operation instead of keeping expensive tracing enabled permanently.

Reference: https://docs.python.org/3.15/library/profiling.sampling.html
