# Heroku memory lifecycle and debugging

This guide records the memory-management lessons learned from production
incidents in PyChess. Use it when adding long-lived server state, reviewing
cleanup code, investigating Heroku R14 errors, or validating a memory fix after
deployment.

## The core rule: make objects unreachable

Python can collect an unused object only after every strong reference to it is
gone. In this server, the most important roots are long-lived objects such as
`PychessGlobalAppState`, its dictionaries and sets, cached `User`, `Game`,
`Tournament`, and `Simul` objects, and live asyncio tasks.

Calling `gc.collect()` does not help while any of those roots still reaches the
object. A task can retain its coroutine frame, local variables, bound methods,
callbacks, and everything reachable through them. A queue can retain every
pending payload. A websocket map can retain its user, which can retain games,
tasks, and other socket maps.

Cleanup is therefore an ownership operation:

1. Stop new work from being produced.
2. Cancel and await owned tasks or clocks.
3. Remove task references and completion callbacks.
4. Remove queues, sockets, and both sides of every relationship.
5. Remove secondary or reverse-index entries.
6. Delete the top-level cache entry last.

Cancellation alone is incomplete. Await the task so its `finally` block runs,
then remove the reference to the completed task. Cleanup paths should be
idempotent because timeouts, disconnects, game endings, and scheduled eviction
can race.

Collection also does not guarantee an immediate RSS decrease. CPython and the C
allocator may retain freed arenas for reuse. The production goal is bounded
`RSS + swap` across representative traffic, not a drop after every eviction.

## Places that have retained memory before

### Game clocks and cache removal tasks

A clock task executes a coroutine that reaches its clock and game, while the
game reaches the clock and its task. Finished or database-loaded games used to
leave some of these relationships alive.

Current cleanup follows these rules:

- Every finished game's delayed removal is scheduled once and kept in
  `game_remove_tasks`.
- The done callback removes the task from that registry and observes failures.
- Immediate eviction cancels and awaits any delayed removal task.
- Game eviction cancels and awaits clocks before removing the game.
- Clock cancellation clears `clock_task`, breaking the strong task reference.
- Eviction removes fishnet work, BOT game queues, `game_in_progress` pointers,
  and idle anonymous users before the game becomes unreachable.
- A finished game can be evicted immediately after its last player or spectator
  disconnects, unless useful analysis work still exists.

Do not add a bare `asyncio.create_task(remove_later(game))`. The coroutine frame
retains `game` for its entire sleep, duplicate removers can race, and failures
can go unobserved. Use the app-state scheduling and ownership helpers.

### Background tasks

Background tasks need strong ownership while running and prompt release when
finished. PyChess keeps app-owned tasks in `background_tasks` and user-owned
tasks in `User.background_tasks`; done callbacks discard them and inspect
exceptions.

For a new task:

- Choose the narrowest correct owner.
- Give the task a descriptive name.
- Retain it through `create_background_task()` or `track_background_task()`.
- Remove it in a done callback.
- Cancel and await it when its owner is evicted or during server shutdown.
- Avoid callbacks or closure variables that capture a full `User`, `Game`, or
  `Tournament` when an immutable ID is sufficient.

This pattern prevents two opposite failures: a fire-and-forget task disappearing
while still needed, and a finished or sleeping task remaining reachable forever.

Per-user sleeping tasks deserve extra care. A bound coroutine such as
`user.remove()` retains `user` while sleeping. Anonymous-user cleanup therefore
also runs opportunistically when the last cached game is evicted, and cancels
the user's other timers before removing the user cache entry.

### Websockets and spectator references

Socket ownership exists in several places: per-user lobby/game/tournament/simul
maps, central tournament maps, and game or simul spectator collections. Removing
only the socket object from one collection can leave the whole object graph
reachable through another.

For every websocket handler:

- Put cleanup in `finally`.
- Remove the socket from every central and per-user map.
- Update online state only after the socket sets are current.
- Remove the user from the game's spectators and remove the game ID from
  `user.watched_games`.
- Make missing entries normal during racing or repeated cleanup.
- Do not wait indefinitely for one slow socket while tearing down or broadcasting.
- Use the shared heartbeat/receive-timeout policy so silently dead clients are
  eventually removed; see [websocket-heartbeats.md](websocket-heartbeats.md).

`watched_games` is a reverse index. It lets user cleanup remove spectator
references by visiting only games that the user actually watched, instead of
scanning every cached game. Keep the forward and reverse sides synchronized at
the point of mutation.

### SSE and asyncio queues

The `/api/ongoing` incident showed how a half-dead connection can retain a large
amount of memory even when the queue consumer has a timeout. The consumer timed
out `queue.get()` but not the network `send()`. Once `send()` blocked, game
broadcasts continued to append board JSON to an unbounded queue. A few queues
held more than one hundred thousand messages.

Every long-lived queue needs an explicit policy:

- Set `maxsize`, unless preserving a reconnectable semantic event history
  genuinely requires otherwise.
- Use `put_nowait()` on event-loop producers. A slow consumer must not suspend
  gameplay or a global broadcast.
- Coalesce replaceable snapshots by keeping only the newest value.
- For non-replaceable events, choose a finite limit and disconnect the lagging
  consumer on overflow.
- Time out the actual socket or SSE write, not only `queue.get()`.
- On terminal connection cleanup, remove the queue from its channel set and use
  `shutdown(immediate=True)` where appropriate.
- Balance every successful `get()` with `task_done()`, including timeout and
  exception paths.
- Do not enqueue recurring keepalives if one is already pending.

Current queue policies are:

| Queue family | Policy |
| --- | --- |
| Ongoing-game SSE | Maximum 256 events; overflow closes and drains the lagging subscriber |
| Challenge, notification, and invite SSE | One replaceable snapshot; newer state replaces pending state |
| Inbox SSE | Maximum 32 events; overflow closes the lagging subscriber |
| BOT event/game streams | Semantic queues survive reconnects; writes time out after 10 seconds and pings are coalesced |
| Correspondence push jobs | Maximum 2048 jobs; overload drops new jobs without blocking gameplay |
| Fishnet priority work | Deduplicate analysis per game and compact stale or duplicate queue IDs |

Do not blindly call `shutdown()` on BOT semantic queues. They are not scoped to
one HTTP connection: a BOT stream may reconnect and resume the same account or
game queue. Instead, stop the connection from generating its own backlog and
make game eviction remove queues that no longer have semantic value.

### Global user and tournament caches

A global cache entry is a deliberate GC root. Eviction must account for identity,
not only whether an account currently reports `online`.

The registered-user cache uses one central sweep and a conservative last-access
TTL. It protects exact `User` instances referenced by games, seeks, invites,
tournaments, simuls, auto-pairing, sockets, SSE channels, correspondence state,
and user-owned tasks. This avoids creating two live `User` objects for one
account.

When adding a new global structure that stores users:

- Add it to the protected-reference calculation or clean it before user eviction.
- Re-check object identity at deletion time; the username may now map to a
  replacement instance.
- Track cache access explicitly.
- Keep metrics and bulk scans timestamp-neutral.

The last point prevented a subtle self-refresh bug. `Users` derives from
`collections.UserDict`, whose inherited `values()` and `items()` can enumerate
through `__getitem__`. Because explicit lookup updates last-access time, a
metrics scan could refresh every cached user and prevent eviction. Bulk views
must read the underlying dictionary without changing access timestamps.

Finished tournaments are another large root because loading one materializes
all participants as full `User` objects. Their eviction uses a separate,
last-access-based TTL and:

- re-reads last access after every sleep;
- refuses eviction while central or per-user viewer sockets are active;
- cancels and awaits the tournament clock;
- clears both socket maps;
- removes the tournament and its access record;
- clears derived player JSON cache state.

Do not use a timestamp captured before sleeping. An HTTP request or websocket
can legitimately refresh the tournament during that sleep.

### Fishnet and paired data structures

Fishnet work exists both in a work dictionary and as IDs in an
`asyncio.PriorityQueue`. Removing one side does not remove the other. Stale or
duplicate IDs consume memory and repeated analysis requests can create
unnecessary work.

Keep the dictionary and priority queue consistent, compact stale IDs, deduplicate
pending analysis for a game, and remove all work for an evicted game. Apply the
same rule to any future data structure represented by both an object map and a
scheduling queue.

### Derived caches and native memory

User-defined variants added bounded Python caches and native Fairy-Stockfish
registrations. They are real memory consumers, but entry count alone does not
prove they explain a production slope.

For a cache hypothesis:

1. Identify every stored and derived representation.
2. Fill it locally to a realistic and maximum capacity.
3. Measure current RSS without `tracemalloc`.
4. Compare that upper bound with the observed production growth.
5. Tighten the limit only when the memory saving is material and the hit-rate
   tradeoff is acceptable.

Stored SVG/INI byte counters do not include all parsed Python objects or derived
payloads. Conversely, a bounded cache whose measured maximum is a few MiB cannot
explain growth of hundreds of MiB.

Fairy-Stockfish registrations allocate native memory that Python heap walks do
not see. `tracemalloc` sees only traced Python allocations and materially
increases memory use itself. Stable Python object counts with rising total memory
can mean native allocation, allocator fragmentation, or an unmeasured cache.

## Safe production monitoring

Use the lightweight recorder after the relevant code is deployed:

```bash
./monitor.sh record
```

The default recording takes seven samples ten minutes apart and writes a
mode-0600 JSONL file under `/tmp`. Keep the raw file private. Never print,
commit, or paste `monitor.sh`; it contains the production credential.

Evaluate at least:

- `rss_plus_swap_mib`, not RSS alone;
- current RSS and swap, not only peak RSS;
- registered/cache-only/anonymous users and cumulative evictions;
- games, tournaments, tasks, websockets, and SSE stream counts;
- total and maximum SSE and BOT queue backlogs;
- fishnet work and queue counts;
- catalogued and pyffish variant counts and measured payload bytes;
- Python allocated blocks and all bounded-cache entry counts;
- request errors and slow requests during the sample window.

Compare equal-duration windows within one dyno lifetime. A first/last delta and a
linear slope are useful summaries, but correlate them with traffic and retained
state. One reading cannot establish a leak or prove a fix.

Queue metrics are especially diagnostic. A bounded or zero backlog while stream
and task counts rise is evidence that connections are consuming or being cleaned
up correctly. A growing maximum backlog identifies a lagging consumer before it
becomes a dyno-wide memory problem.

## Escalation ladder

Use the least perturbing tool that can distinguish the remaining hypotheses:

1. Record a representative lightweight production window.
2. Correlate memory with state, stream, task, queue, and cache counters.
3. Reproduce plausible cache or native costs locally.
4. Inspect lifecycle ownership and add focused counters where visibility is
   missing.
5. If the cause remains unknown, capture one isolated full metrics snapshot.

The full endpoint inspects heap objects cooperatively without forcing garbage
collection. It shares one collection between callers and caches the encoded
snapshot for sixty seconds, but still allocates memory while diagnosing memory
and may contain sensitive object detail. Never poll it. Heap counts can include
unreachable objects waiting for normal GC, so detached-object counts alone do
not prove a leak.

The Textual TUI launched by `./monitor.sh` now polls lightweight summaries, with
the same default ten-minute interval and sixty-second production minimum. It
opens the process-memory table; detailed object tables and heap sizes remain
unmeasured until requested. Press **D** for one full snapshot or **I** for task
stack locations. The status line shows the sample timestamp; full data may be
up to sixty seconds old. The next timer update returns to summary data and clears
heap rows and allocation sizes. The recorder (`./monitor.sh record`) continues
to use summaries only.

Queue diagnostics must never use `str(queue)` or `repr(queue)`.
`asyncio.Queue` representations include their pending payloads; during the
ongoing-game incident this turned a diagnostic response itself into roughly
68 MiB. Report only safe metadata such as queue type, identity, `qsize`,
`maxsize`, and `full`.

## Post-deploy acceptance

After a memory fix, require a representative production window rather than a
single healthy sample:

- `RSS + swap` is flat or falls across the window.
- Swap remains zero when practical.
- Queue backlogs remain bounded and normally near zero.
- Cache counts respect their configured bounds.
- Finished-game, tournament, user, task, and socket counts turn over with
  traffic.
- No monitoring requests fail or materially disturb latency.

A one-hour default recording with stable memory despite changing stream and task
counts is strong initial evidence. Continue observing through a longer and busier
window before declaring a long-term growth regression closed.

## Review checklist

Before merging code that introduces long-lived state, answer:

- Who owns this object, task, queue, socket, or cache entry?
- What exact event ends its lifetime?
- Which forward and reverse references must be removed?
- Is cleanup in `finally`, idempotent, and safe under cancellation?
- Are cancelled tasks awaited and removed from their registries?
- Can a blocked network write stop the consumer while producers continue?
- Is the queue bounded, coalesced, or explicitly justified?
- Can metrics or iteration accidentally refresh cache access?
- Does eviction preserve one canonical `User` identity?
- Are native allocations and derived caches observable separately?
- Is there a focused regression test and a lightweight production metric for the
  failure mode?
