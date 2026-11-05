# Crawler load simulation under a 512 MiB limit

Run this separately from `tests/client_stresstest.py`, which generates concurrent
gameplay. The crawler runner launches a disposable server on loopback, seeds an
in-memory database by default, and measures that server from a separate client
process. A separate mode restores an isolated copy of the local imported Mongo
database. Neither mode targets production or starts against the original import.

The default server scope has a **512 MiB hard memory limit, no swap, and one CPU**.
It uses Linux cgroup v2 through `systemd-run --user --scope`; the load generator
and its measurements are outside that scope. It verifies the applied memory
limit before generating load. Linux `/proc` is required.

Install the project development dependencies first (`uv sync --extra dev`).
From the repository root:

```bash
uv run python tests/crawler_stresstest.py
```

The defaults run a ten-second baseline, followed by two cycles of a sixty-second
flood and sixty-five-second recovery. The fixture contains 200 generated public
variants in addition to curated engine entries, 1,000 profile targets, and a
registered-player chess game with two opening moves played. Normal probes run
once per second during all phases.

Use a new output directory for every run; existing directories are rejected.
Without `--output`, the runner creates a private directory under `/tmp`.

```bash
uv run python tests/crawler_stresstest.py \
  --baseline-seconds 5 --attack-seconds 20 --recovery-seconds 65 \
  --cycles 2 --rps 50 --output /tmp/crawler-mixed
```

For concurrency protection, add simulated backend I/O latency. The delay is
after admission, and is explicitly recorded in the report. It affects browsing
probes too, so set the normal-page latency threshold accordingly:

```bash
uv run python tests/crawler_stresstest.py \
  --scenario browsing --backend-delay-ms 200 --max-probe-p95-ms 500 \
  --rps 200 --concurrency 96 --anonymous-cookie \
  --baseline-seconds 3 --attack-seconds 10 --recovery-seconds 65 --cycles 1 \
  --output /tmp/crawler-slow-backend
```

`--identity rotate` rotates synthetic router-observed IPs; `--identity single`
exercises a single client's per-IP limit. Only the loopback fixture trusts these
synthetic `X-Forwarded-For` values. `--anonymous-cookie` materializes one guest
through the normal websocket handshake before the run, and reuses that guest's
session for crawler requests. The default crawler retains no cookies.

Workload choices:

| `--scenario` | Traffic mix |
| --- | --- |
| `mixed` (default) | 60% HTML browsing, 20% profiles, 20% catalogue API queries |
| `browsing` | 80% HTML browsing, 20% profiles |
| `catalogue` | Full public catalogue fallback and named batches of up to 32 definitions |
| `assets` | JS/WASM downloads only; `--rps` sets their rate unless `--asset-rps` is supplied |

All scenarios vary query strings and user agents. Catalogue API queries remain
outside the HTML admission budget; including them avoids claiming protection
based only on endpoints expected to return 429.

## JS and WASM delivery

Production uses `STATIC_ROOT=https://cdn.jsdelivr.net/gh/pychess/pychess-variants@1.11.88/static`.
The fixture uses that value by default; override it with `--static-root` for another
deployment. The application bundle (`/static/pychess-variants.js`), rules WASM,
Stockfish JS/WASM, and realtime workers have explicit same-origin URLs and still
reach Heroku despite the CDN setting.

Build production assets before measuring downloads:

```bash
yarn prod
```

Development builds include inline source maps and are much larger. The production
build also creates Brotli/gzip variants, which affect actual transfer sizes. The
runner records each selected representation's size, content encoding, ETag, and
cache-control header rather than assuming the uncompressed file size was sent.

Add an independent asset stream to the existing crawler:

```bash
uv run python tests/crawler_stresstest.py \
  --rps 200 --asset-rps 20 --asset-cache mixed \
  --baseline-seconds 20 --attack-seconds 20 --recovery-seconds 65 --cycles 2
```

For slow readers, limit each connection's read rate. Keep the offered rate low
enough that `--asset-concurrency` can hold the outstanding downloads:

```bash
uv run python tests/crawler_stresstest.py \
  --rps 200 --asset-rps 4 --asset-kib-per-second 128 --asset-concurrency 32 \
  --baseline-seconds 20 --attack-seconds 20 --recovery-seconds 65 --cycles 2
```

Either command also accepts `--snapshot-database` to include restored production
state. For download-only isolation, use `--scenario assets --rps 20`. By default,
assets are disabled for the original crawler scenarios (`--asset-rps 0`).

Asset discovery reads the real analysis HTML to locate the main JS and rules WASM,
then includes the known runtime-loaded Stockfish, Alice WASM, and realtime-worker
files. External JS/WASM references are recorded and never fetched. CDN content
is neither downloaded nor redirected to the local server. This is a transfer
simulation of local assets, not a browser executing JS or recursively fetching
every page dependency. Requests go directly to the origin even if a browser
would already have cached a file; this also tests deliberately repeated origin
downloads.

`--asset-kind js|wasm|all` selects the file types. `--asset-encoding br|gzip|identity`
sets Accept-Encoding; the server can fall back to identity if a compressed file
does not exist. `--asset-cache cold` requests full bodies, `warm` sends conditional
ETags and requires 304, and `mixed` alternates full and conditional rounds through
all selected files. No full response bodies are retained. Automatic decompression
is disabled so reported bytes are encoded body bytes, excluding HTTP headers.

Slow clients use 16 KiB reads, bounded aiohttp buffering, and a small socket receive
buffer so sleeping between reads does not simply leave whole responses buffered
on the client. `--asset-timeout` (default 120 seconds) covers each complete download.
In-flight transfers drain before recovery starts; slow transfers can extend the
nominal attack phase, while player probes and telemetry continue running. The
report records offering and drain durations. The memory-stop event also interrupts
paced reads promptly.

Reports separate every file's time to response headers, full download latency,
200/304/error counts, and received bytes. Missing assets, truncated bodies, failed
cache revalidations, excessive client drops, or incomplete transfer accounting
fail the run. Kernel cgroup memory peaks are included in the quota check to catch
short-lived socket-buffer pressure between samples.

The generator offers requests at the requested rate independently of completion.
It bounds outstanding requests with `--concurrency`, records requests it cannot
offer in time, and fails if more than 1% are dropped by the client. It never
builds an unlimited queue waiting for a semaphore. Response bodies are drained
in chunks, and latency reservoirs are bounded to 4,096 samples per category and
phase. Counts and maxima cover all requests; percentiles above that sample count
are estimates from a deterministic reservoir.

## Running against imported production state

Ongoing games, registered players, catalogue definitions, and restored tasks use
part of the 512 MiB quota before any crawler arrives. Use the local Mongo import
to measure that baseline rather than estimating it from the synthetic fixture:

```bash
uv run python tests/crawler_snapshot.py
```

The helper reads `pychess-variants` on `127.0.0.1:27017` and copies every collection
and its indexes into a uniquely named `pychess-crawler-snapshot-*` database. It
prints the command for running the crawler against that snapshot:

```bash
uv run python tests/crawler_stresstest.py \
  --snapshot-database pychess-crawler-snapshot-<generated-id> \
  --baseline-seconds 30 --attack-seconds 60 --recovery-seconds 65 --cycles 2
```

Only scratch databases carrying the helper's marker are accepted. This matters
because application startup performs migrations and writes, and recovered game
clocks can finish games. The original local import is read only. Create a new
snapshot for each comparable cold-start run; the server rejects reused snapshots
that already contain its probe identities. Snapshots remain on disk for inspection
and must be removed manually when no longer needed. Allow enough disk space for
a second copy of the database and indexes. The copy is intended for an idle local
import; it is not a consistent backup of a database receiving writes.

The server uses the real Mongo driver and ordinary startup, waits for correspondence
restoration, then adds one small probe game. Crawler requests use real public
catalogue and enabled profile targets. The baseline therefore includes restored
games, users, and background tasks; it does not generate moves in all those games.
Readiness metadata includes restored-state counts. Target names and probe cookies
are kept in the private readiness file and omitted from the summary report.

`startup-samples.jsonl` measures the child from before application imports at
250 ms intervals. Startup memory contributes to the quota check even if the
server fails before accepting HTTP requests; such a failure writes a failed
`report.json`. `--startup-timeout` defaults to 300 seconds. Mongo runs outside the
server's memory scope, matching the separate production database service.

## Measurements and success criteria

`report.json` gives per-phase status counts, received bytes, and separate latency
statistics for accepted requests, 429s, and failures. Normal authenticated HTML,
game-page requests, and an ongoing game websocket's ping/pong round trips are
measured separately. Fast 429 responses therefore cannot hide slow player traffic.

`samples.jsonl` records process RSS, swap, peak RSS, cgroup memory/CPU counters,
event-loop delay, anonymous users, profiles, games, tasks, limiter entries, and
request buckets once per second. Collection does not force garbage collection
or query the expensive full `/metrics` endpoint. RSS/swap are sampled from the
parent even if the server event loop is blocked.

The default acceptance targets are:

- Peak memory below 80% of 512 MiB (**409.6 MiB**), retaining headroom for real
  gameplay. Startup peak RSS is included. Cgroup usage and process RSS/swap are
  both recorded; the larger sampled budget usage is checked.
- No more than 32 MiB growth between median late-baseline and late-recovery memory.
- Normal-user p95 latency and maximum event-loop delay below 250 ms, with at least
  three successful probes per attack phase. Redirects, 429s, and transport/server
  errors on normal-user probes fail the run.
- Anonymous browsing resumes after the full recovery window.
- No server death, telemetry failure, crawler 5xx/transport failure, or excessive
  generator under-delivery.

At 90% memory usage the runner stops crawler traffic immediately and continues
recovery observation. This cutoff belongs to the test client; it does not add a
memory admission limit to the production server. Interrupted asset transfers are
marked `Stopped`, not successful downloads. This is a failed run. The independent
kernel memory limit still applies. Exit status is 0 for passed checks and 1 for
failed checks.

`server.log` contains fixture-only server logs; logging defaults to WARNING and
can be changed with `--log-level`. The private readiness file contains only
disposable fixture cookies. Service credentials are removed from the child
environment, and Discord, push, Twitch and Fishnet integrations are disabled.

For a quick plumbing check, shorten the phases. Reports mark runs with recovery
shorter than 65 seconds as `full_recovery_window_observed: false`; those runs do
not establish that admission recovered. On systems without user cgroups,
`--no-constrain` explicitly disables the hard cap; reports mark this as
`memory_limit_enforced: false`. Such a run is not a 512 MiB constrained test.

## Interpretation

Compare successive attack/recovery cycles and inspect state counts alongside
RSS + swap. A cold cache can legitimately increase RSS; allocator retention can
keep that memory resident afterward. Neither proves a leak. Rising retained
memory across repeated cycles, growing anonymous identities, or unbounded task
counts warrant investigation even if the absolute quota check still passes.

The default fixture uses mongomock, includes its database memory in the server process,
and simulates one active game rather than a full population making moves. It
does not reproduce Heroku router behavior, Mongo network latency, shared CPU
contention, browser asset fetching, or a production-sized database. The optional
delay models I/O waiting, not a real Mongo query plan. The catalogue/profile
sizes, traffic rate, duration, and acceptance thresholds are configurable.

Use the existing gameplay runner for move-heavy capacity testing as well.
Local passes are regression evidence, not a guarantee against every Heroku crash;
representative production monitoring remains necessary after deployment.

## Imported-state measurement, 2026-11-04

A local import containing 5,158,437 game documents, 38,052 users, and 1,001 stored
catalogue documents restored 254 games (244 correspondence), 99 users, and 811
catalogue variants. The runner then added its probe game and two players.

With a 512 MiB hard cap, no swap, and one CPU, two thirty-second mixed crawls at
200 requests/second, each followed by sixty-five seconds of recovery, measured:

| Measurement | Result |
| --- | --- |
| Median baseline memory | 365.5 MiB |
| Peak after first burst | 387.9 MiB |
| Peak after second burst | 388.2 MiB |
| Remaining quota at peak | 123.8 MiB |
| Retained growth from late baseline to final recovery | 22.7 MiB |
| Offered crawler requests / client drops | 12,002 / 0 |
| Crawler responses: 200 / 429 | 2,830 / 9,172 |
| Worst attack-phase normal-probe p95 | 17.3 ms |
| Largest attack-phase event-loop delay | 53.2 ms |

**The overall run failed:** a 1,040 ms event-loop delay occurred during the baseline,
before crawler traffic. An earlier 50 requests/second run also saw a roughly
one-second baseline pause. The cause is not established by these measurements.
Reports retain this failure rather than relaxing the responsiveness threshold.

No crash was reproduced. The small difference between the two burst peaks is
encouraging short-run evidence, but does not establish long-term bounded memory
or capacity while all restored games are actively making moves. These measurements
also show why startup state must be included: roughly 71% of the quota was already
used before the crawler began.

## Asset measurements, 2026-11-04

Production assets were built with `yarn prod`. The main JS was 674,804 bytes in
Brotli form; rules/engine WASM files had no precompressed representation and were
served as identity. The original development build was restored after testing.

On an isolated Mongo snapshot, a twenty-second mixed crawler at 200 requests/second
plus four full JS/WASM downloads/second, read at 128 KiB/second per connection,
completed all 80 asset downloads with no generator drops. There were up to 18
outstanding downloads; transfers drained for another 11.5 seconds before the
sixty-five-second recovery began. Peak memory was 388.3 MiB, normal player-probe
p95 stayed below 17 ms, and attack-phase event-loop delay peaked at 55 ms. The
run failed only for an 867 ms event-loop delay in the pre-crawl baseline.

A separate two-burst run at twenty asset requests/second exercised 800 asset
requests, half full downloads and half conditional 304s, alongside crawling. It
peaked at 388.7 MiB. A local Mongo snapshot copy overlapped parts of that run, so
its timings should not be used as an isolated comparison with the slow-reader run.
Its only failure was the baseline event-loop delay.

A download-only adversarial case used the synthetic fixture, 32 JS requests/second,
identity encoding, and 128 KiB/second readers. With 75 outstanding transfers,
**cgroup memory reached 465.5 MiB while process RSS remained about 362 MiB**.
The client safety cutoff stopped new requests after about 11 seconds and closed
incomplete downloads. There was no OOM. The full recovery window returned memory
near baseline. This is a failed capacity test, not a successful full twenty-second
burst: 355 requests were offered before the cutoff and 75 were interrupted.

A short diagnostic repeat collected kernel memory breakdowns. At 74 outstanding
downloads it measured 132.9 MiB in `memory.stat.sock`, with process RSS still about
362 MiB and total cgroup usage about 465 MiB. Socket usage returned to zero after
the client closed the downloads. This confirms network-buffer pressure in the
local test rather than Python heap growth. That diagnostic used only a three-second
recovery; the preceding run supplied the full recovery observation.

Reproduce that case separately from normal browser traffic:

```bash
uv run python tests/crawler_stresstest.py \
  --scenario assets --rps 32 --asset-kind js --asset-encoding identity \
  --asset-kib-per-second 128 --asset-concurrency 160 --asset-timeout 45 \
  --baseline-seconds 5 --attack-seconds 20 --recovery-seconds 65 --cycles 1
```

Samples include `memory.stat` so network buffers (`sock`), anonymous memory, file
cache, and kernel allocations can be distinguished. Linux cgroup accounting
includes TCP buffers; Heroku's displayed total memory is RSS plus swap. Treat this
local hard-cap test as conservative capacity evidence rather than proof of an
identical Heroku R14 event. See the [Linux cgroup documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html)
and [Heroku metrics definitions](https://devcenter.heroku.com/articles/metrics).
