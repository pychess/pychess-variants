from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

from monitor.metrics_client import fetch_metrics, metrics_url, monitor_token

DEFAULT_INTERVAL_SECONDS = 600.0
DEFAULT_SAMPLES = 7
MIN_PRODUCTION_INTERVAL_SECONDS = 60.0

SUMMARY_KEYS = (
    "rss_mib",
    "swap_mib",
    "rss_plus_swap_mib",
    "peak_rss_mib",
    "allocated_blocks",
    "loop_lag_stalls_20ms",
    "loop_lag_stalls_50ms",
    "loop_lag_stalls_100ms",
    "loop_lag_stalls_250ms",
    "users",
    "user_perf_entries",
    "user_puzzle_perf_entries",
    "registered_total",
    "registered_cache_only",
    "registered_cache_evictions",
    "anon_total",
    "games",
    "tournaments",
    "finished_tournaments",
    "tournament_remove_tasks",
    "tournament_user_references",
    "finished_tournament_user_references",
    "tournaments_with_active_sockets",
    "tournament_active_sockets",
    "tasks",
    "queues",
    "streams",
    "game_sse",
    "game_sse_queued_messages",
    "game_sse_max_queue",
    "game_sse_full_queues",
    "sse_queued_messages",
    "sse_max_queue",
    "sse_full_queues",
    "bot_event_queued_messages",
    "bot_game_queued_messages",
    "bot_max_queue",
    "catalogued_variants",
    "pyffish_variants",
    "catalogued_payload_bytes",
    "fishnet_works",
    "fishnet_payload_bytes",
    "cache_entries",
)


def _first_detail(metrics: Mapping[str, Any], category: str) -> Mapping[str, Any]:
    details = metrics.get("object_details")
    if not isinstance(details, Mapping):
        return {}
    rows = details.get(category)
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes) or not rows:
        return {}
    row = rows[0]
    return row if isinstance(row, Mapping) else {}


def _number(mapping: Mapping[str, Any], key: str) -> int | float:
    value = mapping.get(key, 0)
    return value if isinstance(value, int | float) and not isinstance(value, bool) else 0


def _mapping(metrics: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = metrics.get(key)
    return value if isinstance(value, Mapping) else {}


def summarize_metrics(metrics: Mapping[str, Any]) -> dict[str, int | float]:
    summary_mode = metrics.get("mode") == "summary"
    if summary_mode:
        process = _mapping(metrics, "process_memory")
        state = _mapping(metrics, "state")
        registered = _mapping(metrics, "registered")
        anon = _mapping(metrics, "anonymous")
        streams = _mapping(metrics, "streams")
        counts: Mapping[str, Any] = {}
        tasks = _number(state, "active_tasks")
        queues = 0
        cache_rows = metrics.get("caches")
        cache_entries = (
            sum(_number(row, "currsize") for row in cache_rows if isinstance(row, Mapping))
            if isinstance(cache_rows, Sequence) and not isinstance(cache_rows, str | bytes)
            else 0
        )
    else:
        process = _first_detail(metrics, "process_memory")
        state = _first_detail(metrics, "state")
        registered = _first_detail(metrics, "registered_summary")
        anon = _first_detail(metrics, "anon_summary")
        streams = _first_detail(metrics, "streams")
        object_counts = metrics.get("object_counts")
        counts = object_counts if isinstance(object_counts, Mapping) else {}
        tasks = _number(counts, "tasks")
        queues = _number(counts, "queues")
        cache_entries = _number(counts, "caches")

    loop_lag = _mapping(metrics, "event_loop_lag")
    return {
        "loop_lag_stalls_20ms": _number(loop_lag, "stalls_20ms"),
        "loop_lag_stalls_50ms": _number(loop_lag, "stalls_50ms"),
        "loop_lag_stalls_100ms": _number(loop_lag, "stalls_100ms"),
        "loop_lag_stalls_250ms": _number(loop_lag, "stalls_250ms"),
        "loop_lag_max_ms": _number(loop_lag, "max_lag_ms"),
        "rss_mib": _number(process, "rss_mib"),
        "swap_mib": _number(process, "swap_mib"),
        "rss_plus_swap_mib": _number(
            process,
            "rss_plus_swap_mib",
        )
        or _number(process, "rss_mib"),
        "peak_rss_mib": _number(process, "peak_rss_mib"),
        "allocated_blocks": _number(process, "allocated_blocks"),
        "users": _number(state, "users"),
        "user_perf_entries": _number(state, "user_perf_entries"),
        "user_puzzle_perf_entries": _number(state, "user_puzzle_perf_entries"),
        "registered_total": _number(registered, "registered_total"),
        "registered_cache_only": _number(registered, "registered_cache_only"),
        "registered_cache_evictions": _number(registered, "registered_cache_evictions"),
        "anon_total": _number(anon, "anon_total"),
        "games": _number(state, "games"),
        "tournaments": _number(state, "tournaments"),
        "finished_tournaments": _number(state, "finished_tournaments"),
        "tournament_remove_tasks": _number(state, "tournament_remove_tasks"),
        "tournament_user_references": _number(state, "tournament_user_references"),
        "finished_tournament_user_references": _number(
            state, "finished_tournament_user_references"
        ),
        "tournaments_with_active_sockets": _number(state, "tournaments_with_active_sockets"),
        "tournament_active_sockets": _number(state, "tournament_active_sockets"),
        "tasks": tasks,
        "queues": queues,
        "streams": sum(
            _number(streams, key)
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
            )
        ),
        "game_sse": _number(streams, "game_sse"),
        "game_sse_queued_messages": _number(streams, "game_sse_queued_messages"),
        "game_sse_max_queue": _number(streams, "game_sse_max_queue"),
        "game_sse_full_queues": _number(streams, "game_sse_full_queues"),
        "sse_queued_messages": _number(streams, "sse_queued_messages"),
        "sse_max_queue": _number(streams, "sse_max_queue"),
        "sse_full_queues": _number(streams, "sse_full_queues"),
        "bot_event_queued_messages": _number(streams, "bot_event_queued_messages"),
        "bot_game_queued_messages": _number(streams, "bot_game_queued_messages"),
        "bot_max_queue": _number(streams, "bot_max_queue"),
        "catalogued_variants": _number(state, "catalogued_variants"),
        "pyffish_variants": _number(state, "pyffish_variants"),
        "catalogued_payload_bytes": _number(state, "catalogued_payload_bytes"),
        "fishnet_works": _number(state, "fishnet_works"),
        "fishnet_payload_bytes": _number(state, "fishnet_payload_bytes"),
        "cache_entries": cache_entries,
    }


def summary_deltas(
    first: Mapping[str, int | float],
    last: Mapping[str, int | float],
) -> dict[str, int | float]:
    return {key: last.get(key, 0) - first.get(key, 0) for key in SUMMARY_KEYS}


def validate_interval(url: str, interval_seconds: float) -> None:
    if interval_seconds <= 0:
        raise ValueError("Interval must be greater than zero")

    hostname = (urlparse(url).hostname or "").casefold()
    is_local = hostname in {"localhost", "127.0.0.1", "::1"}
    if not is_local and interval_seconds < MIN_PRODUCTION_INTERVAL_SECONDS:
        raise ValueError(
            f"Production interval must be at least {MIN_PRODUCTION_INTERVAL_SECONDS:g} seconds"
        )


def _new_output_file(output: Path | None) -> tuple[Path, Any]:
    if output is None:
        fd, filename = tempfile.mkstemp(
            prefix="pychess-production-metrics-",
            suffix=".jsonl",
        )
        return Path(filename), os.fdopen(fd, "w", encoding="utf-8")

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return output, os.fdopen(fd, "w", encoding="utf-8")


def _format_summary(sample: int, summary: Mapping[str, int | float]) -> str:
    return (
        f"sample={sample} total={summary['rss_plus_swap_mib']:.2f} MiB "
        f"rss={summary['rss_mib']:.2f} MiB swap={summary['swap_mib']:.2f} MiB "
        f"users={summary['users']} cache_only={summary['registered_cache_only']} "
        f"ratings={summary['user_perf_entries']}+{summary['user_puzzle_perf_entries']} "
        f"games={summary['games']} tasks={summary['tasks']} streams={summary['streams']} "
        f"game_sse={summary['game_sse']} "
        f"sse_backlog={summary['sse_queued_messages']} "
        f"sse_max={summary['sse_max_queue']} "
        f"bot_backlog={summary['bot_event_queued_messages'] + summary['bot_game_queued_messages']} "
        f"loop_lag_max={summary['loop_lag_max_ms']:.1f}ms "
        f"loop_stalls_100ms={summary['loop_lag_stalls_100ms']}"
    )


async def record_metrics(
    *,
    url: str,
    token: str,
    interval_seconds: float,
    samples: int,
    request_timeout_seconds: float,
    output: Path | None,
) -> Path:
    validate_interval(url, interval_seconds)
    if samples < 1:
        raise ValueError("Samples must be at least one")
    if not token:
        raise ValueError("PYCHESS_MONITOR_TOKEN is not set")

    output_path, output_file = _new_output_file(output)
    first_summary: dict[str, int | float] | None = None
    last_summary: dict[str, int | float] | None = None
    interrupted = False
    started = time.monotonic()
    timeout = aiohttp.ClientTimeout(total=request_timeout_seconds)

    print(f"Writing private JSONL snapshots to {output_path}", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for sample in range(1, samples + 1):
                scheduled_at = started + (sample - 1) * interval_seconds
                delay = scheduled_at - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)

                captured_at = datetime.now(UTC).isoformat()
                request_started = time.monotonic()
                try:
                    metrics = await fetch_metrics(
                        session,
                        url=url,
                        token=token,
                        inspect_tasks=False,
                        summary_only=True,
                    )
                    summary = summarize_metrics(metrics)
                    record: dict[str, Any] = {
                        "captured_at": captured_at,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "request_seconds": round(time.monotonic() - request_started, 3),
                        "summary": summary,
                        "metrics": metrics,
                    }
                    first_summary = first_summary or summary
                    last_summary = summary
                    print(_format_summary(sample, summary), flush=True)
                except (TimeoutError, aiohttp.ClientError, TypeError, ValueError) as exc:
                    record = {
                        "captured_at": captured_at,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "request_seconds": round(time.monotonic() - request_started, 3),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    print(f"sample={sample} failed: {type(exc).__name__}: {exc}", flush=True)

                json.dump(record, output_file, separators=(",", ":"), default=str)
                output_file.write("\n")
                output_file.flush()
                os.fsync(output_file.fileno())
    except asyncio.CancelledError:
        interrupted = True
    finally:
        output_file.close()

    if first_summary is not None and last_summary is not None:
        print(
            "deltas="
            + json.dumps(summary_deltas(first_summary, last_summary), separators=(",", ":")),
            flush=True,
        )
    if interrupted:
        print("Recorder stopped; completed snapshots were preserved.", flush=True)
    return output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record low-frequency pychess production metrics as private JSONL. "
            "Task stack inspection is always disabled."
        )
    )
    parser.add_argument("--url", default=metrics_url())
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--request-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        asyncio.run(
            record_metrics(
                url=args.url,
                token=monitor_token(),
                interval_seconds=args.interval_seconds,
                samples=args.samples,
                request_timeout_seconds=args.request_timeout_seconds,
                output=args.output,
            )
        )
    except (FileExistsError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    except KeyboardInterrupt:
        print("Recorder stopped; completed snapshots were preserved.")


if __name__ == "__main__":
    main()
