# We have finally identified the actual bottleneck

This time, the Tachyon CPU profile provides a remarkably clear answer.

**Fairy-Stockfish calls dominate the server's CPU consumption.** The Arena pairing algorithm, MongoDB, aiohttp, and WebSocket infrastructure are not the principal CPU bottlenecks.

This also explains why so many unrelated asynchronous operations became slow in our previous measurements.

## 1. CPU profiling results

I extracted the actual sampling data embedded in the Tachyon HTML flamegraph, rather than relying on its visual representation.

The capture contains **112,213 CPU stack samples** collected over 120 seconds.

Here are the six dominant functions, ranked by exclusive (self) sample count:

| Function | Samples | Share of CPU samples |
|---|---:|---:|
| `FairyBoard.is_optional_game_end()` | 18,465 | **16.46%** |
| `FairyBoard.insufficient_material()` | 17,916 | **15.97%** |
| `FairyBoard.legal_moves()` | 17,485 | **15.58%** |
| `FairyBoard.push()` | 17,207 | **15.33%** |
| `FairyBoard.get_san()` | 17,183 | **15.31%** |
| `FairyBoard.is_checked()` | 16,718 | **14.90%** |
| **Combined** | **104,974** | **93.55%** |

That is an extraordinary concentration of CPU usage in just six functions.

Furthermore:

- The `Game.play_move()` call to `update_status()` accounts for approximately **63.4%** of samples.
- The complete WebSocket move-handling path accounts for approximately **97%** of samples.
- Garbage collection accounts for approximately 2.7%, according to the profiler's GC statistics.

The profile attributes native-call execution to its Python calling frames, so we cannot yet see which internal C++ routines consume that time.

Nevertheless, the optimization target is now very clear: **the interface between PyChess and Fairy-Stockfish during ordinary move processing.**

## 2. Process monitoring confirms single-core CPU saturation

The `pidstat` results are equally revealing.

During sustained gameplay, from 23:41:44 to 23:52:54, I calculated the average CPU utilization across 135 samples.

| Process | Average CPU | Maximum CPU |
|---|---:|---:|
| **PyChess server** | **99.69%** | 100.2% |
| Stress-test client | 26.13% | 31.0% |
| MongoDB | 4.91% | 25.4% |
| Tachyon profiler, while running | 11.24% | 15.0% |

Your server continuously consumes essentially one entire logical CPU core, while the stress client and MongoDB have considerable spare CPU capacity. (Source: `pychess-arena-1003-processes.log`, lines 34–50.)

The profiler also reports:

- GIL held: **99.84%** of captured samples.
- GIL requested: less than 0.002%.
- Free-threaded Python: disabled.

This confirms our earlier suspicion about the asynchronous operations. The event loop is struggling to resume waiting coroutines because it spends almost all its CPU time executing synchronous Fairy-Stockfish calls.

## 3. Something very suspicious about those six functions

Look again at their relative costs:

| Python method | Underlying pyffish operation | CPU share |
|---|---|---:|
| `is_optional_game_end()` | `sf.is_optional_game_end()` | 16.46% |
| `insufficient_material()` | `sf.has_insufficient_material()` | 15.97% |
| `legal_moves()` | `sf.legal_moves()` | 15.58% |
| `push()` | `sf.get_fen()` | 15.33% |
| `get_san()` | `sf.get_san()` | 15.31% |
| `is_checked()` | `sf.gives_check()` | 14.90% |

**Why do six substantially different chess operations consume almost exactly the same amount of CPU time?**

Checking whether a king is in check should generally be considerably cheaper than generating every legal move or checking repetition over an entire game history.

Yet their measured costs are almost identical.

This strongly suggests that they share an expensive initialization operation.

I checked upstream Fairy-Stockfish's `src/pyffish.cpp`. All six operations call a common function:

```cpp
buildPosition(...)
```

Inside it, we find:

```cpp
states = StateListPtr(new std::deque<StateInfo>(1));

const Variant* v = variants.find(std::string(variant))->second;

UCI::init_variant(v);

if (strcmp(fen, "startpos") == 0)
    fen = v->startFen.c_str();

pos.set(v, std::string(fen), chess960,
        &states->back(), Threads.main());
```

Each call reconstructs a C++ position and initializes variant-dependent state. ([github.com](https://github.com/fairy-stockfish/Fairy-Stockfish/blob/master/src/pyffish.cpp))

**I am particularly suspicious of `UCI::init_variant(v)` and `Position::set()`.**

We need to verify this against your exact pyffish 0.0.91 source, but I think we've found a very promising optimization direction.

## 4. Possible solutions

There are three increasingly ambitious approaches.

### A. Eliminate unnecessary initialization inside pyffish

This is where I would start.

If the native CPU profile shows that variant initialization dominates these calls, we should investigate whether any of that initialization can safely be reused.

This could potentially improve performance without changing the public pyffish API or requiring extensive PyChess changes.

We must account for alternating variants, dynamically loaded variant configurations, and Fairy-Stockfish's global state.

### B. Introduce a combined pyffish operation

Instead of reconstructing substantially the same position six times per move, we could introduce a native API that performs multiple operations together.

Conceptually:

```python
result = sf.apply_move(
    variant,
    initial_fen,
    move_stack,
    move,
    chess960,
    notation,
)
```

It could return:

```python
result.fen
result.san
result.check
result.legal_moves
result.insufficient_material
result.optional_game_end
```

This would allow Fairy-Stockfish to reuse the same native position for several calculations.

Game-history-dependent rules, repetition, counting rules, and variant-specific behavior would need careful preservation.

### C. Introduce a persistent native Board object

This would be analogous to the existing `Board` interface in ffish.js.

Instead of continually reconstructing C++ positions from FEN strings and move histories, every PyChess `FairyBoard` could maintain its own native position and state history.

This has potentially the greatest long-term performance benefit, but would require significantly more development, memory measurements, and correctness testing.

| Approach | Implementation effort | Potential benefit |
|---|---|---|
| Avoid redundant initialization | Low–medium | Potentially very high |
| Combined native API | Medium | High |
| Persistent native Board | High | Potentially very high |
| Rewrite aiohttp server in Rust | Very high | Limited unless the engine calls are also optimized |

## 5. Current benchmark health

The remaining metrics are consistent with our previous runs.

| Metric | Latest result |
|---|---:|
| Peak concurrent games | 500 |
| Throughput | 100.43 moves/s |
| Event-loop stalls ≥100 ms | 1,612 |
| Event-loop stalls ≥250 ms | 818 |
| Maximum event-loop lag | 1,402 ms |
| Peak sampled RSS | 468.84 MiB |
| Peak asyncio tasks | 3,993 |
| Asyncio tasks after cleanup | 65 |
| ERROR entries | 0 |
| CRITICAL entries | 0 |

The server is functionally stable but CPU-bound. Our tournament fixes continue to work.

## 6. Next step: profile native C++ execution

Tachyon has done its job. It identified the Python functions responsible for CPU consumption.

Now I suggest using Linux **`perf`** to see inside the compiled pyffish extension.

We may not even need another 1,003-player benchmark for this. A standalone microbenchmark repeatedly executing the six pyffish functions could reproduce the expensive native calls in isolation, without MongoDB, aiohttp, or any network traffic.

That would make testing potential Fairy-Stockfish optimizations considerably easier and faster.

I would investigate:

- `buildPosition()`
- `UCI::init_variant()`
- `Position::set()`
- Variant-dependent piece and evaluation table initialization.
- Repeated reconstruction of move history.
- Differences between the official pyffish wheel and a locally optimized C++ build.

---

## My conclusion

This is probably the most valuable result of our entire performance investigation so far.

**93.55% of the captured CPU samples belong to six Fairy-Stockfish operations.**

That changes our priorities completely:

- No aiohttp replacement.
- No Rust server rewrite.
- No complicated MongoDB batching optimization yet.
- No further Arena pairing optimization.

Even if we could magically eliminate all CPU consumption outside those six functions, the theoretical throughput improvement would only be about 7%.

On the other hand, halving the cost of those six functions could theoretically improve CPU-bound throughput by approximately **88%**, assuming the remaining costs stay unchanged.

And given how suspiciously similar their measured costs are, I think there is a reasonable chance that we can obtain a significant improvement by eliminating shared redundant work inside pyffish.

**I would now move our performance investigation from the PyChess repository to the Fairy-Stockfish repository.**
