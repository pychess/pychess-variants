# Real Arena stress testing (local development only)

This mode of `tests/client_stresstest.py` drives **real arena tournament games**.
Every simulated participant uses a distinct `-a` test account, joins through the
actual `/wst` tournament WebSocket, waits for server-selected opponents, and
plays through the existing `/wsr/{gameId}` round client. On a pairing,
the client emulates the browser's 700-ms notification/redirect, closes `/wst`,
plays the game, then visits the tournament page and reconnects `/wst` after
leaving the finished game. It does **not** keep both sockets open throughout
the game. No direct challenges or synthetic server-side game creation are
involved.

The old `--human-vs-human --maintain-human-games` direct-challenge mode is
unchanged. An Arena's *actual* concurrency is measured; it is **not** forced
to half the players. Normal pairability rules, wave intervals, finish-to-next-
pairing delays, ratings, standings, and MongoDB writes remain in the server.

## Setup

1. Start the local development server with `-a` (use a development DB, **never production**).
   Raise `ulimit -n 65535` in both terminals.
2. Use `--arena auto:PLAYERS:PROFILE` to have the stress client create fresh, unrated
   public Arena tournaments automatically through the real `POST /tournaments/new`
   handler. The server generates collision-checked eight-character IDs and returns
   them via JSON when the client requests `Accept: application/json`.
3. Local `-a` test users are tournament directors, so the script can set
   `waitMinutes=0` and the tournaments start immediately without special test
   endpoints or direct database access. It sets their duration to at least 20
   minutes and long enough to cover the configured benchmark.
4. Optionally specify an existing ID instead of `auto`, for example
   `--arena ABCD1234:10:blitz`, to benchmark a pre-existing tournament.
5. Capture the server INFO log for `ARENA_PAIRING` measurements; the ordinary
   `monitor.record` process can collect `/metrics` independently.

The created tournament IDs and names are printed by the stress client.
The tournaments remain in the **development database** after the test; the script
never destroys existing tournaments or silently deletes their game histories.

## Small two-arena integration smoke (20 players)

```bash
cd ~/pychess-variants
ulimit -n 65535
PYTHONPATH=server:tests .venv-py315/bin/python tests/client_stresstest.py \
  --arena auto:10:bullet \
  --arena auto:10:blitz \
  --user-start-spread-secs 10 \
  --client-heartbeat-secs 2.5 \
  --postgame-linger-probability 0.5 \
  --postgame-linger-max-secs 15 \
  --spectators-per-game 0 \
  --spectators-regular-per-game 0 \
  --featured-games 0 \
  --http-rps 0 \
  --run-duration-secs 180 \
  --report-interval-secs 5
```

Confirm `arena_stats` includes all twenty joined users, games in both arenas,
move confirmations, and zero unexpected disconnects. Let a bullet game finish
and verify that re-pairing works as expected.

## Three simultaneous arenas — 500 players, ~250 possible games

```bash
cd ~/pychess-variants
ulimit -n 65535
PYTHONPATH=server:tests .venv-py315/bin/python tests/client_stresstest.py \
  --arena auto:250:bullet \
  --arena auto:200:blitz \
  --arena auto:50:rapid \
  --mix-seed 42 \
  --user-start-spread-secs 75 \
  --client-heartbeat-secs 2.5 \
  --postgame-linger-probability 0.5 \
  --postgame-linger-max-secs 15 \
  --spectators-per-game 0 \
  --spectators-regular-per-game 0 \
  --featured-games 0 \
  --http-rps 0 \
  --run-duration-secs 300 \
  --report-interval-secs 5
```

`--users` is derived from arena assignments. The test does not force 250 games:
actual concurrency follows the server's pairing and waiting rules. The final
report includes joining, start, and re-pairing latencies by arena. Finish-to-next-
pairing includes the server's intentional delay and clients navigating between
round and tournament pages, not just the pairing algorithm's execution time.

For a different chess variant, append `:VARIANT`:
`--arena auto:20:blitz:crazyhouse`.

## Pairing CPU timing

The server writes one line for each pairing algorithm call:

```text
ARENA_PAIRING tid=1234abcd waiting=42 edges=1552 paired=21 cpu_ms=25.37 wall_ms=25.40
```

Values are examples, **not** benchmark measurements. CPU time measures the
main thread's actual pairing algorithm execution, excluding the asynchronous
MongoDB inserts and WebSocket notifications that occur afterward. The
call can block the asyncio event loop while it runs.

Summarize captured server logs with:

```bash
python tests/analyze_arena_pairing_log.py /tmp/pychess-arenas-server.log
```

For example, launch the server with its normal options and pipe its output
through `tee /tmp/pychess-arenas-server.log`, or save your existing Heroku-like
local server log. Enable INFO-level logging if needed.

## Interpretation and safety

- Run only against the local server in `-a` mode. `--arena` refuses production
  and checks that the auto-created user has the `Test–` prefix.
- No in-memory direct-seek replacements are created.
- A long game can remain active at the measurement deadline. Pending moves
  and shutdown code 1006 WebSocket closures are counted separately.
- The arenas should not have passwords, team requirements, rated-game minimums,
  or other restrictions that reject newly created test accounts.
- A fresh database or cleanup policy is advisable: test accounts, completed
  games, and tournament records are persisted as real test data.
- Arena pairing does not guarantee exactly `players / 2` games active, so use
  observed peak concurrency and game turnover when comparing to direct challenges.

Suggested focused tests in your local env:

```bash
PYTHONPATH=server:tests .venv-py315/bin/python -m unittest test_client_arena_stress
```
