# Server CPU usage and event-loop latency audit

PyChess production runs on a resource-constrained Heroku dyno while serving many
simultaneous real-time games. Very short time controls make latency especially
important: a CPU-heavy synchronous operation in the aiohttp process does not only
make its own request slow; it can prevent unrelated WebSocket games from being
scheduled while the operation is running.

This document records the initial server-side CPU/event-loop audit performed on
2026-10-07. It is intentionally an audit baseline rather than an implementation
plan. Each finding should be discussed before deciding how to change it.

## What matters most

The main risk is **uninterrupted synchronous work on the aiohttp event-loop
thread**. A function can be relatively rare and still be dangerous if one
invocation monopolizes the event loop for hundreds of milliseconds or seconds.
Conversely, a small synchronous cost may be important when it occurs on every
move in every live game.

The initial priorities are:

| Priority | Area | Main concern |
| --- | --- | --- |
| P0 | Study tree validation | Large user-supplied trees can monopolize the event loop for seconds; history-dependent variants are especially expensive |
| P0 | Historical game reconstruction | Replaying a complete game synchronously can cause second-scale stalls after cache misses/restarts |
| P0/P1 | Full `/metrics` snapshot | Explicit GC and Python heap traversal run synchronously in the server process |
| P1 | Ordinary live move processing | Several Fairy-Stockfish calls run synchronously for every move |
| P1 | Bughouse live move processing | Similar per-move engine work, with both boards participating in status calculations |
| P2 | Other Study whole-tree/document operations | Repeated scans, BSON encoding, and snapshot hashing add avoidable latency |
| P2 | Tournament pairing and other occasional CPU work | Rare CPU-heavy algorithms should not unexpectedly block live games |

The absolute timings below were measured in a development/test environment, not
on the production Heroku dyno. They should therefore be treated as indicators of
relative cost and event-loop risk, not as production benchmarks. The important
fact is that the measured work is synchronous and does not yield to aiohttp.

## 1. Study tree validation — P0

The largest observed one-shot risk is Study import/tree validation in
`server/study/builder.py`, especially `_validated_tree()` around line 467.

For each submitted node, validation performs several synchronous board/engine
operations, including legal-move generation, SAN generation, move application,
and check detection. The configured chapter limit is currently 3,000 nodes in
`server/study/constants.py`.

A linear orthodox-chess tree measured approximately:

- 100 nodes: 0.72 s
- 200 nodes: 1.43 s
- 400 nodes: 2.99 s

Those seconds are uninterrupted server-side CPU work from the point of view of
the event loop.

### History-dependent variants are substantially worse

For variants whose legal moves require history, including Janggi, Ataxx, and
applicable custom variants, validation reconstructs the board from the initial
position and replays preceding moves while validating nodes. A linear chapter
therefore repeats more and more historical work as it advances.

Measured Janggi validation cost was approximately:

- 10 nodes: 0.135 s
- 20 nodes: 0.416 s
- 40 nodes: 1.46 s
- 80 nodes: 5.34 s

This growth is consistent with effectively quadratic replay work for a linear
history-dependent chapter. A legal user-supplied import can therefore become a
major event-loop stall long before reaching the general 3,000-node limit.

### Tree traversal also contains repeated linear scans

`StudyTree.children_of()` in `server/study/tree.py` scans the node collection to
find a node's children. Algorithms that call it repeatedly while walking a tree,
such as preferred-mainline construction, can therefore introduce O(N^2)
Python-level work independently of engine replay.

`preferred_mainline()` measured roughly:

- 1,000 nodes: 26 ms
- 2,000 nodes: 107 ms
- 3,000 nodes: 263 ms

This is much smaller than history-dependent engine replay, but it is still
avoidable synchronous work and compounds other Study costs.

### Resolution: move bulk chess-semantic validation to the browser

The expensive part of this finding was addressed after review on 2026-10-07.
PyChess already uses the same Fairy-Stockfish rules on both sides through
`ffish.js` in the browser and `pyffish` on the server, and PGN import already
replayed every branch client-side. Replaying the complete tree again on the
resource-constrained production server duplicated the expensive work.

Bulk Study creation/import now uses the following trust boundary:

- the browser owns move legality, variation replay, derived node FEN, SAN, check
  state, and side-to-move normalization;
- the server still validates the initial position;
- the server still enforces cheap structural/resource invariants such as node
  limits, IDs, parents, cycles, sibling order, annotation/value limits, bounded
  node FENs, and node FEN/turn consistency;
- authenticated comment authorship remains server-authoritative;
- embedded custom-variant INI plus the imported root FEN are still validated in
  an isolated pyffish child process before an accepted immutable snapshot can
  reach the long-lived server process;
- interactive one-move Study mutations continue to validate the newly-added move
  server-side.

When a later edit or Fishnet variation needs to initialize a board from an imported
node FEN, the server checks that one position's syntax, geometry, and pocket-material
limits before native move generation. This check is performed on demand, independently
of chapter size; bulk import still performs no per-node engine calls.

The full-tree `_validated_tree()` engine replay was removed from the bulk
`from_analysis()` / PGN-import path. A synthetic linear tree measured after the
change (including `StudyTree.from_payload()` structural validation and comment
author canonicalization) at approximately:

- 100 nodes: 1.5-1.6 ms
- 400 nodes: 5.6-5.8 ms
- 1,000 nodes: 14-15 ms
- 3,000 nodes: 45-50 ms

These are development/sandbox numbers, not Heroku guarantees, but the important
change is algorithmic: bulk creation no longer makes per-node Fairy-Stockfish
calls or repeatedly reconstructs move history on the aiohttp event-loop thread.
The Janggi/Ataxx quadratic replay case is therefore eliminated from this path.

The separate `StudyTree.children_of()` / `preferred_mainline()` repeated-scan
issue remains open and should be discussed independently; it is no longer
compounded by bulk engine replay.

## 2. Historical game reconstruction — P0

`Game.get_board()` in `server/game.py` can call synchronous `create_steps()` when
a loaded game has moves but its derived step list has not yet been reconstructed.
`create_steps()` replays the game from the beginning and performs SAN generation,
move application/FEN reconstruction, and status/check work for every ply.

Approximate measured core replay cost was:

- 20 plies: 84 ms
- 100 plies: 420 ms
- 200 plies: 880 ms
- 400 plies: 1.66 s
- 800 plies: 3.43 s

The risk is particularly relevant after dyno restart, cache eviction, or other
situations where several historical/live games need reconstruction at nearly the
same time.

Bughouse reconstruction in `server/bug/utils_bug.py` is heavier because it must
rebuild two related boards and pocket state. Equivalent engine work was roughly
5.7-6.2 ms per ply in the audit, around 1.1 s for 200 plies.

### Implemented: finished single-board display replay

Finished single-board HTML and round-socket snapshots now carry the initial
position, normalized stored moves, clock history, analysis, and replay metadata.
The browser builds the move-list positions, SAN, and checks with its existing
ffish engine. Old Shogi coordinates remain normalized during database loading;
legacy Capablanca castling, manual counting, and Jieqi reveal identities are
handled without server display replay.

Active games, Study game conversion, and explicitly requested server
analysis retain authoritative server reconstruction. PGN generation is still
included in finished board responses and still replays SAN on the server; removing
that separate cost is the next step.

### Implemented: finished two-board display replay

Finished Bughouse, Supply Chess, and Makbug archives now restore the server's
final boards directly from the stored FEN pair. HTML and round-socket snapshots
send the initial boards, globally ordered moves and board names, and the existing
clock, timestamp, analysis, and chat metadata. The browser replays both boards in
that order, transferring captures before subsequent partner drops. Promoted
capture demotion, en passant, castling, pocket insertion order, variant notation,
and the archive reader's check/mate markers are preserved.

Parity fixtures captured from the previous server reader compare both boards and
all step metadata after 450 moves, including focused special-move cases. Finished
loading and display tests reject any per-move server SAN, push, or capture calls.
A local 800-ply Bughouse load plus full snapshot took about 4.04 seconds before
the change; loading, compact snapshot generation, and JSON encoding now take
about 9 milliseconds. These are development measurements, not production guarantees.

Active two-board games still replay authoritatively during restoration. Explicit
backend analysis reconstructs archive steps on demand. Games already holding
derived steps serve those directly. Older documents without a final FEN pair
retain the existing server reconstruction path. Bughouse's server PGN field is
already a placeholder; its actual BPGN generation remains on the client.

### Points to discuss before implementation

Potential approaches include persisting enough derived state to avoid complete
replay for common reconnect/load cases, making expensive reconstruction lazy,
and making unavoidable long reconstruction cooperative by yielding between
small batches. Cooperative replay still consumes CPU, but it prevents a
multi-second uninterrupted global pause.

## 3. Full `/metrics` snapshot — P0/P1

The full metrics handler in `server/server_metrics.py` performs intentionally
expensive diagnostic work synchronously inside an async request handler.

`memory_stats()` includes work such as:

- `gc.collect()`;
- enumerating GC-tracked Python objects;
- recursively estimating deep object sizes;
- aggregating/sorting object information.

The full handler then also gathers/sorts live application structures such as
users, games, seeks, and asyncio tasks. The source itself notes that the memory
snapshot is suitable for executor/off-thread work, but the current request path
calls it directly.

Even in a mostly idle test process, `memory_stats()` took around 140 ms. A
production process containing many games, users, sockets, tasks, studies, and
cached objects has a substantially larger heap. Opening or polling the detailed
monitor can therefore create a visible site-wide scheduler pause.

The lightweight summary path does not have the same concern and should remain the
normal monitoring path.

### Implemented: summary polling and cooperative, shared full snapshots

The Textual monitor previously fetched full heap snapshots every ten minutes.
Its timer now requests only `/metrics?summary=True`; **D** requests one full
snapshot and **I** requests one with task stack locations. The existing lightweight
recorder already used summaries and keeps its seven-sample, ten-minute defaults.

Full snapshots no longer call `gc.collect()`. Heap scanning and container-size
traversal yield between batches when a roughly five-millisecond work slice is
used up. Live application objects stay on the event-loop thread, and mutable
containers' children are copied before yielding to avoid invalidated iterators.
Only the detached response data is passed to a worker thread for JSON encoding.

One app-owned collection task serves concurrent callers; cancelling one request
does not cancel the shared snapshot. The encoded response is reused for sixty
seconds. Task inspection can upgrade a normal snapshot after its collection
finishes, and inspected snapshots also satisfy normal requests. Authentication
still runs before any cache access, and HTTP responses use `Cache-Control: no-store`.
The full response retains its existing object tables and adds `mode: "full"` and
`heap_gc_collected: false`. Its timestamp identifies the cached sample.

A local probe with 1,000 cached users and about 484,000 tracked objects measured:

| Request | Total time | Largest observed heartbeat gap |
| --- | --- | --- |
| Previous full snapshot | 347 ms | 347 ms |
| Cooperative full snapshot | 293 ms | 24 ms |
| Cached full snapshot | Below 1 ms | About 1 ms |
| Lightweight summary | About 5 ms | About 5 ms |

These are development measurements, not production guarantees. `gc.get_objects()`,
container copying, and sorting still include native operations that cannot yield;
full snapshots remain occasional diagnostics. Summary polling avoids the heap
work entirely, and sharing/caching prevents callers from repeating it together.
Without forced GC, heap counts can include unreachable objects awaiting normal
collection; detached-object counts alone do not prove a leak.

## 4. Ordinary live move processing — P1

The highest-frequency synchronous cost is the normal human move path in
`server/utils.py` and `server/game.py`.

A submitted move involves multiple separate Fairy-Stockfish/pyffish operations,
including legal-move validation, SAN generation, pushing the move/FEN creation,
new legal-move generation, check detection, insufficient-material detection, and
optional game-end evaluation.

The audit measured an ordinary move's synchronous native-engine sequence at
roughly 10-13 ms on the test machine. Individual wrapper operations were commonly
around 1.3-1.5 ms.

Ten milliseconds is not a major pause by itself, but this code runs continually
across all real-time games. For example, 30 moves arriving in one second at an
average of 10-13 ms of synchronous processing represents roughly 300-390 ms of
that second spent in move-related synchronous engine work before accounting for
other Python, database, serialization, and WebSocket activity.

Long histories can make some status operations more expensive because historical
move data is supplied to the engine. History-dependent variants deserve special
attention here as well.

### Points to discuss before implementation

This path should be optimized differently from rare long jobs. Offloading each
individual move may add scheduling/serialization overhead and could make latency
worse. A more promising direction is to identify duplicate engine queries and,
where possible, obtain several pieces of post-move information from one native
operation instead of repeatedly parsing/reconstructing essentially the same
position.

Random-Mover also has an obvious small duplication where availability of a legal
move can be checked immediately before obtaining the legal-move list itself.

## 5. Bughouse live move processing — P1

`server/bug/game_bug.py` performs similar synchronous work for each Bughouse
move, with additional two-board interactions. The path validates the move,
handles transferred captured pieces/pockets, generates SAN, pushes the move,
checks legal-move availability, and evaluates status/check state involving both
boards.

An approximation of the corresponding native-engine sequence measured around
11.7 ms median on a fresh Bughouse position in the audit.

Like ordinary move processing, the main concern is frequency rather than one
extreme invocation: every millisecond spent here is time in which the same event
loop cannot process unrelated games.

## 6. Additional Study whole-tree/document work — P2

Several other Study operations synchronously process an entire chapter or tree:

- `preferred_mainline()` repeatedly depends on `children_of()` scans;
- `server/study/mutations.py` and `server/study/storage.py` call
  `BSON.encode(chapter.to_document())` to enforce chapter-size limits;
- `server/study/snapshot.py` creates a snapshot token by BSON-encoding and
  SHA-256 hashing the complete chapter document.

A chapter can be several megabytes, so these are potential latency spikes even
when they are not in the same category as history-dependent import validation.
They should be reviewed together with the broader Study data-structure work so
that optimizations do not simply move the cost to another operation.

### Implemented: indexed children and cooperative document processing

Each immutable `StudyTree` now builds an ordered child index. Mainline traversal,
variation cleanup, and subtree deletion use that index instead of repeatedly
scanning all nodes. The node mapping is read-only so an in-place change cannot
silently invalidate the index; constructing a replacement tree rebuilds it.

Chapter size checks and snapshot hashing share a serializer that converts and
BSON-encodes the flat tree in batches of 32 nodes, yielding between batches.
Size checks discard each encoded batch after measuring it. Snapshot hashing
retains the encoded batches until their enclosing BSON lengths are known, then
hashes them cooperatively. BSON field ordering, exact byte sizes, and snapshot
tokens match the previous complete-document encoding. Tokens continue to cover
content changes made without a collaborative revision update, including Fishnet
analysis. No document or token cache survives the operation.

Storage inserts, bulk imports, cleanup writes, and Fishnet tree merges reuse the
document produced during size validation, removing their second tree conversion.
Mutations retain their revision checks, and cancellation during serialization
propagates before the candidate is committed.

Local Python 3.14 measurements used an already parsed 3,000-node linear tree and
a 2,000-node chapter with one 3,500-character comment per node (7.3 MB BSON):

| Operation | Previous median | Current median |
| --- | ---: | ---: |
| Mainline traversal, 3,000 nodes | 252 ms | 0.34 ms |
| Tree construction plus mainline traversal, 3,000 nodes | 253 ms | 4.1 ms |
| Large chapter size check | 7.3 ms | 5.7 ms |
| Large chapter size check plus document for insertion | 9.3 ms | 6.1 ms |
| Large chapter snapshot token | 13.6 ms | 13.1 ms |

The largest observed event-loop gap during snapshot generation dropped from
18.5 ms to 0.25 ms. Hashing still processes the complete persisted chapter, so
its total CPU cost is similar; indexing and document reuse reduce CPU work,
while batching improves scheduling fairness. Database-driver encoding and other
HTTP payload construction retain their existing paths. These are development
measurements, not production guarantees.

## 7. Tournament pairing and other occasional CPU algorithms — P2

The base `Tournament.create_pairing_async()` in
`server/tournament/tournament.py` currently calls synchronous pairing logic
inline. Swiss pairing eventually performs Dutch pairing generation in the event
loop.

The current Swiss participant limit makes this less urgent than the findings
above, but it is a useful example of CPU work whose name/interface suggests
asynchronous behavior while the actual algorithm executes synchronously. Similar
occasional algorithms should be audited with the same rule: if the runtime can
become significant, they should not unexpectedly monopolize the gameplay event
loop.

Custom-variant validation already uses child processes, which protects the event
loop from direct blocking. On a one-vCPU dyno, however, concurrent child-process
validation can still compete with the web process for CPU, so concurrency limits
also matter even when work is correctly off-process.

## Production observability gap: event-loop lag

Existing slow-request timing is useful, but it cannot fully answer the question
that matters for fast games: **how long was the aiohttp event loop unable to
schedule other work?**

A request may appear slow because it awaited MongoDB without harming other games.
Conversely, a synchronous Study import or heap scan may freeze every WebSocket
without producing an obvious per-game slow-request trace.

A small event-loop-lag watchdog would make the impact measurable in production.
For example, periodically schedule a short sleep/timer and record the difference
between expected and actual wake-up time, logging or counting stalls above
thresholds such as 50 ms and 100 ms. The exact thresholds and reporting mechanism
should be discussed before implementation.

## Suggested discussion order

Before writing fixes, discuss the findings in this order:

1. Study validation/tree algorithms and safe limits.
2. Historical game and Bughouse reconstruction.
3. Full metrics/memory diagnostics.
4. Ordinary per-move Fairy-Stockfish call count and duplication.
5. Bughouse per-move processing.
6. Remaining Study serialization/tree costs.
7. Tournament/other occasional CPU algorithms.
8. Event-loop-lag production instrumentation and how to use it to verify changes.

The first three are the clearest sources of large one-shot stalls. Items 4 and 5
are likely more important for continuous CPU utilization and jitter under normal
bullet-game load.
