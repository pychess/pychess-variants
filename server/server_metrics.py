from __future__ import annotations

import asyncio
import gc
import inspect
import logging
import resource
import sys
import time
from asyncio import Event, Queue, Task
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable, Mapping
from datetime import UTC, datetime
from itertools import chain
from typing import TYPE_CHECKING, Any, TypedDict, cast

import msgspec
import pyffish as sf
from aiohttp import web
from aiohttp.web_response import StreamResponse
from bson import Int64
from bug.game_bug import GameBug
from catalogued_betza import (
    _cached_betza_svg,
    _cached_catalogued_betza_diagrams,
    _cached_piece_diagram_definitions,
)
from catalogued_rules import _cached_catalogued_rule_summary
from clock import Clock
from const import STARTED, reserved
from fairy.fairy_board import FairyBoard, get_fog_fen
from fairy.jieqi import index_to_square, square_to_index
from fishnet import fishnet_variants_payload_cache_bytes
from game import Game
from glicko2.glicko2 import Rating
from json_utils import json_response
from lobby import Lobby
from pychess_global_app_state_utils import get_app_state
from seek import Seek
from settings import LOCALHOST, PYCHESS_MONITOR_TOKEN, URI
from simul.simul import Simul
from tournament.tournament import GameData, PlayerData, Tournament, player_json
from typedefs import request_protection_state_key
from user import User
from variants import CataloguedServerVariant, Variant

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState

log = logging.getLogger(__name__)


FULL_METRICS_CACHE_SECONDS = 60.0
METRICS_BATCH_SIZE = 128
METRICS_SLICE_SECONDS = 0.005


class SnapshotBudget:
    """Yield between small batches without inspecting live objects in another thread."""

    def __init__(self):
        self.deadline = time.monotonic() + METRICS_SLICE_SECONDS

    async def checkpoint(self) -> None:
        if time.monotonic() >= self.deadline:
            await asyncio.sleep(0)
            self.deadline = time.monotonic() + METRICS_SLICE_SECONDS


async def _batched(items: Iterable[Any], budget: SnapshotBudget) -> AsyncIterator[Any]:
    for index, item in enumerate(items):
        if index % METRICS_BATCH_SIZE == 0:
            await budget.checkpoint()
        yield item


def _metrics_json_hook(value: object) -> int:
    # Keep the existing JSON transport's support for legacy MongoDB integer values.
    if isinstance(value, Int64):
        return int(value)
    raise TypeError(f"Unsupported metrics value: {type(value).__name__}")


class FullMetricsSnapshot:
    """One app-owned collection task and one bounded, encoded snapshot cache."""

    def __init__(self):
        self.task: asyncio.Task[bytes] | None = None
        self.body: bytes | None = None
        self.expires_at = 0.0
        self.inspected = False

    async def get(
        self, app_state: PychessGlobalAppState, request: web.Request, need_inspect: bool
    ) -> bytes:
        while True:
            if (
                self.body is not None
                and time.monotonic() < self.expires_at
                and (self.inspected or not need_inspect)
            ):
                return self.body
            if self.task is None:
                self.body = None
                self.task = app_state.create_background_task(
                    self._collect(app_state, request, need_inspect), name="full-metrics-snapshot"
                )
                self.task.add_done_callback(self._clear_task)
            # A disconnected requester must not cancel work shared by other callers.
            # Inspect requests wait for a normal collection before upgrading it.
            await asyncio.shield(self.task)

    async def _collect(
        self, app_state: PychessGlobalAppState, request: web.Request, need_inspect: bool
    ) -> bytes:
        metrics = await _full_metrics(app_state, request, need_inspect)
        # Only detached JSON data crosses the thread boundary, never app/heap objects.
        body = await asyncio.to_thread(msgspec.json.encode, metrics, enc_hook=_metrics_json_hook)
        self.body = body
        self.inspected = need_inspect
        self.expires_at = time.monotonic() + FULL_METRICS_CACHE_SECONDS
        return body

    def _clear_task(self, task: asyncio.Task[bytes]) -> None:
        if self.task is task:
            self.task = None


def _seek_expire_sort_key(seek: Seek) -> float:
    expire_at = seek.expire_at
    if expire_at is None:
        return float("-inf")
    if expire_at.tzinfo is None:
        expire_at = expire_at.replace(tzinfo=UTC)
    return expire_at.timestamp()


class AllocationStat(TypedDict):
    type: str
    count: int
    size_bytes: int
    size_human: str


class TaskInfo(TypedDict):
    id: int
    name: str
    state: object
    file: str
    source: str


class QueueInfo(TypedDict):
    id: int
    name: str
    size: int
    maxsize: int
    full: bool
    file: str
    source: str


class CacheInfo(TypedDict):
    name: str
    hits: int
    misses: int
    maxsize: int
    currsize: int
    full: bool


MONITORED_TYPES = (
    Clock,
    Game,
    GameBug,
    User,
    Seek,
    PlayerData,
    GameData,
    Tournament,
    Simul,
    Lobby,
    StreamResponse,
    Task,
    Queue,
    Event,
    FairyBoard,
    Rating,
    Variant,
    CataloguedServerVariant,
)

CACHE_FUNCTIONS = (
    ("fog_fen", get_fog_fen),
    ("tournament_player_json", player_json),
    ("catalogued_betza_svg", _cached_betza_svg),
    ("catalogued_betza_definitions", _cached_piece_diagram_definitions),
    ("catalogued_betza_diagrams", _cached_catalogued_betza_diagrams),
    ("catalogued_rule_summary", _cached_catalogued_rule_summary),
    ("jieqi_square_to_index", square_to_index),
    ("jieqi_index_to_square", index_to_square),
)


def cache_stats() -> list[CacheInfo]:
    rows: list[CacheInfo] = []
    for name, cached_function in CACHE_FUNCTIONS:
        info = cached_function.cache_info()
        maxsize = -1 if info.maxsize is None else info.maxsize
        rows.append(
            {
                "name": name,
                "hits": info.hits,
                "misses": info.misses,
                "maxsize": maxsize,
                "currsize": info.currsize,
                "full": info.maxsize is not None and info.currsize >= info.maxsize,
            }
        )
    return rows


def _proc_status_memory_kib() -> dict[str, int]:
    wanted = {"VmRSS", "VmSwap", "VmSize", "RssAnon", "RssFile", "RssShmem"}
    values: dict[str, int] = {}
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                name, separator, raw_value = line.partition(":")
                if not separator or name not in wanted:
                    continue
                values[name] = int(raw_value.split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return values


def _peak_rss_kib(ru_maxrss: int, platform: str) -> int:
    """Convert ``getrusage().ru_maxrss`` to kibibytes.

    macOS is the odd one out: its ``getrusage(2)`` reports bytes, whereas Linux
    and the BSDs report kibibytes (compare ``ru_maxrss`` in ``man 2 getrusage``
    on FreeBSD with the macOS manual page). Normalizing here keeps
    ``peak_rss_kib`` comparable with ``rss_kib`` and the procfs values, which are
    always kibibytes.
    """
    return ru_maxrss // 1024 if platform == "darwin" else ru_maxrss


def process_memory_stats() -> dict[str, float | int]:
    """Return an RSS/swap breakdown alongside inexpensive Python runtime counters.

    ``peak_rss_kib`` is available on every platform providing ``resource``. The
    per-segment fields (``virtual_memory_kib``, ``anonymous_rss_kib``,
    ``file_rss_kib``, ``shared_rss_kib``) and the swap counter come from Linux
    procfs: without ``/proc``, as on macOS, they stay ``0`` and ``rss_kib`` falls
    back to ``peak_rss_kib``, so it is a peak rather than a current reading.
    """
    peak_rss_kib = _peak_rss_kib(
        int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss), sys.platform
    )
    status_memory = _proc_status_memory_kib()
    rss_kib = status_memory.get("VmRSS", peak_rss_kib)
    swap_kib = status_memory.get("VmSwap", 0)
    rss_plus_swap_kib = rss_kib + swap_kib

    gc_gen0, gc_gen1, gc_gen2 = gc.get_count()
    return {
        "rss_kib": rss_kib,
        "rss_mib": round(rss_kib / 1024, 2),
        "swap_kib": swap_kib,
        "swap_mib": round(swap_kib / 1024, 2),
        "rss_plus_swap_kib": rss_plus_swap_kib,
        "rss_plus_swap_mib": round(rss_plus_swap_kib / 1024, 2),
        "peak_rss_kib": peak_rss_kib,
        "peak_rss_mib": round(peak_rss_kib / 1024, 2),
        "virtual_memory_kib": status_memory.get("VmSize", 0),
        "anonymous_rss_kib": status_memory.get("RssAnon", 0),
        "file_rss_kib": status_memory.get("RssFile", 0),
        "shared_rss_kib": status_memory.get("RssShmem", 0),
        "allocated_blocks": sys.getallocatedblocks(),
        "gc_gen0": gc_gen0,
        "gc_gen1": gc_gen1,
        "gc_gen2": gc_gen2,
    }


def _catalogued_payload_stats(
    catalogued_variants: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    def stored_svg_bytes(item: Mapping[str, Any]) -> int:
        stored_size = item.get("size")
        if isinstance(stored_size, int) and not isinstance(stored_size, bool) and stored_size >= 0:
            return stored_size
        svg = item.get("svg")
        return len(svg.encode("utf-8")) if isinstance(svg, str) else 0

    ini_bytes = 0
    piece_svg_bytes = 0
    board_svg_bytes = 0
    for doc in catalogued_variants.values():
        ini_bytes += len(str(doc.get("ini") or "").encode("utf-8"))

        piece_set = doc.get("pieceSet")
        if isinstance(piece_set, Mapping):
            for item in piece_set.values():
                if isinstance(item, Mapping):
                    piece_svg_bytes += stored_svg_bytes(item)

        board_svg = doc.get("boardSvg")
        if isinstance(board_svg, Mapping):
            board_svg_bytes += stored_svg_bytes(board_svg)

    return {
        "catalogued_ini_bytes": ini_bytes,
        "catalogued_piece_svg_bytes": piece_svg_bytes,
        "catalogued_board_svg_bytes": board_svg_bytes,
        "catalogued_payload_bytes": ini_bytes + piece_svg_bytes + board_svg_bytes,
    }


def _state_summary(
    app_state: PychessGlobalAppState,
    request: web.Request,
) -> dict[str, int]:
    public_profiles = getattr(app_state.public_users, "_profiles", {})
    public_titles = getattr(app_state.public_users, "_titles", {})
    request_protection = request.app[request_protection_state_key]
    payload_stats = _catalogued_payload_stats(app_state.catalogued_variants)
    tournament_stats = app_state.tournament_cache_stats()
    return {
        "users": len(app_state.users),
        "user_perf_entries": sum(len(user.perfs) for user in app_state.users.values()),
        "user_puzzle_perf_entries": sum(len(user.pperfs) for user in app_state.users.values()),
        "games": len(app_state.games),
        "seeks": len(app_state.seeks),
        "lobby_connections": len(app_state.lobby.lobbysockets),
        "invites": len(app_state.invites),
        "tournaments": len(app_state.tournaments),
        **tournament_stats,
        "simuls": len(app_state.simuls),
        "catalogued_variants": len(app_state.catalogued_variants),
        "pyffish_variants": len(sf.variants()),
        **payload_stats,
        "game_remove_tasks": len(app_state.game_remove_tasks),
        "tournament_remove_tasks": len(app_state.tournament_remove_tasks),
        "background_tasks": len(app_state.background_tasks),
        "active_tasks": len(asyncio.all_tasks()),
        "fishnet_works": len(app_state.fishnet_works),
        "fishnet_queue": app_state.fishnet_queue.qsize(),
        "fishnet_payloads": len(app_state.fishnet_variant_payloads),
        "fishnet_payload_bytes": fishnet_variants_payload_cache_bytes(app_state),
        "public_profile_cache": len(public_profiles),
        "public_title_cache": len(public_titles),
        "request_limit_buckets": len(request_protection._limiter._events),
        "request_block_log": len(request_protection._last_block_log),
    }


def _stream_summary(app_state: PychessGlobalAppState) -> dict[str, int]:
    lobby_ws = sum(len(ws_set) for ws_set in app_state.lobby.lobbysockets.values())
    game_ws = sum(
        len(ws_set) for user in app_state.users.values() for ws_set in user.game_sockets.values()
    )
    tournament_ws = sum(
        sum(1 for ws in ws_set if ws is not None)
        for user in app_state.users.values()
        for ws_set in user.tournament_sockets.values()
    )
    simul_ws = sum(
        len(ws_set) for user in app_state.users.values() for ws_set in user.simul_sockets.values()
    )
    study_ws = sum(
        len(ws_set) for user in app_state.users.values() for ws_set in user.study_sockets.values()
    )
    notify_queues = tuple(
        queue for user in app_state.users.values() for queue in user.notify_channels
    )
    inbox_queues = tuple(
        queue for user in app_state.users.values() for queue in user.inbox_channels
    )
    challenge_queues = tuple(
        queue for user in app_state.users.values() for queue in user.challenge_channels
    )
    invite_queues = tuple(
        queue for channels in app_state.invite_channels.values() for queue in channels
    )
    game_queues = tuple(app_state.game_channels)
    all_sse_queues = game_queues + invite_queues + notify_queues + inbox_queues + challenge_queues
    bot_event_queues = tuple(user.event_queue for user in app_state.users.values() if user.bot)
    bot_game_queues = tuple(
        queue
        for user in app_state.users.values()
        if user.bot
        for queue in user.game_queues.values()
    )
    all_bot_queues = bot_event_queues + bot_game_queues
    active_bot_game_streams = sum(
        len(user.active_game_streams) for user in app_state.users.values() if user.bot
    )
    game_sse_queued_messages = sum(queue.qsize() for queue in game_queues)
    game_sse_max_queue = max(
        (queue.qsize() for queue in game_queues),
        default=0,
    )
    return {
        "lobby_websockets": lobby_ws,
        "game_websockets": game_ws,
        "tournament_websockets": tournament_ws,
        "simul_websockets": simul_ws,
        "study_websockets": study_ws,
        "game_sse": len(game_queues),
        "game_sse_queued_messages": game_sse_queued_messages,
        "game_sse_max_queue": game_sse_max_queue,
        "game_sse_full_queues": sum(queue.full() for queue in game_queues),
        "invite_sse": len(invite_queues),
        "invite_sse_groups": len(app_state.invite_channels),
        "notify_sse": len(notify_queues),
        "inbox_sse": len(inbox_queues),
        "challenge_sse": len(challenge_queues),
        "sse_queued_messages": sum(queue.qsize() for queue in all_sse_queues),
        "sse_max_queue": max((queue.qsize() for queue in all_sse_queues), default=0),
        "sse_full_queues": sum(queue.full() for queue in all_sse_queues),
        "invite_sse_queued_messages": sum(queue.qsize() for queue in invite_queues),
        "notify_sse_queued_messages": sum(queue.qsize() for queue in notify_queues),
        "inbox_sse_queued_messages": sum(queue.qsize() for queue in inbox_queues),
        "challenge_sse_queued_messages": sum(queue.qsize() for queue in challenge_queues),
        "active_bot_game_streams": active_bot_game_streams,
        "bot_event_queued_messages": sum(queue.qsize() for queue in bot_event_queues),
        "bot_game_queued_messages": sum(queue.qsize() for queue in bot_game_queues),
        "bot_max_queue": max((queue.qsize() for queue in all_bot_queues), default=0),
    }


def _registered_summary(app_state: PychessGlobalAppState) -> dict[str, int]:
    protected_users = app_state.registered_user_cache_references()
    registered_total = 0
    registered_online = 0
    registered_never_connected = 0
    registered_cache_only = 0
    registered_notification_users = 0
    registered_notification_entries = 0
    for user in app_state.users.values():
        if user.anon or reserved(user.username):
            continue
        registered_total += 1
        registered_online += int(user.online)
        registered_never_connected += int(not user.ever_connected)
        notification_count = 0 if user.notifications is None else len(user.notifications)
        registered_notification_entries += notification_count
        registered_notification_users += int(notification_count > 0)
        if app_state.users.is_registered_cache_only(user, protected_users):
            registered_cache_only += 1

    return {
        "registered_total": registered_total,
        "registered_online": registered_online,
        "registered_offline": registered_total - registered_online,
        "registered_never_connected": registered_never_connected,
        "registered_cache_only": registered_cache_only,
        "registered_cache_evictions": app_state.users.registered_cache_evictions,
        "registered_cache_tracked": len(app_state.users.cache_access),
        "registered_notification_users": registered_notification_users,
        "registered_notification_entries": registered_notification_entries,
    }


def _anonymous_summary(app_state: PychessGlobalAppState) -> dict[str, int]:
    anon_users = [
        user for user in app_state.users.values() if user.anon and not reserved(user.username)
    ]
    return {
        "anon_total": len(anon_users),
        "anon_online": sum(int(user.online) for user in anon_users),
        "anon_never_connected": sum(int(not user.ever_connected) for user in anon_users),
    }


def _lightweight_metrics(
    app_state: PychessGlobalAppState,
    request: web.Request,
) -> dict[str, object]:
    cache_rows = cache_stats()
    return {
        "mode": "summary",
        "timestamp": datetime.now(UTC).isoformat(),
        "process_memory": process_memory_stats(),
        "state": _state_summary(app_state, request),
        "registered": _registered_summary(app_state),
        "anonymous": _anonymous_summary(app_state),
        "streams": _stream_summary(app_state),
        "caches": cache_rows,
    }


def _task_state(task: Task[None] | None) -> str:
    if task is None:
        return "none"
    if task.cancelled():
        return "cancelled"
    if not task.done():
        return "pending"
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return "cancelled"
    except Exception:
        return "done"
    return "failed" if exc is not None else "done"


def inspect_referrer(ref: object) -> None:
    if isinstance(ref, dict):
        log.info("  Dictionary referrer:")
        log.info("     %s", list(ref.keys()))
    elif isinstance(ref, Task):
        log.info("  TASK REFERRER   ")
        log.info("     %s", ref.get_name())
    elif hasattr(ref, "__dict__"):
        log.info("  Object referrer:")
        log.info("     %s", list(ref.__dict__.keys()))
    elif isinstance(ref, set):
        log.info("  Set referrer:")
        li = tuple(ref)
        log.info("     %s", li if len(li) == 0 else li[0])
    elif isinstance(ref, Iterable):
        log.info("  Iterable referrer:")
        try:
            ref_len = len(ref)  # type: ignore[arg-type]
            log.info("     %s", ref if ref_len == 0 else ref[0])  # type: ignore[index]
        except TypeError:
            log.info("     %s", id(ref))
    else:
        log.info(f"  Other referrer: {ref}")


async def get_deep_size(obj: object, budget: SnapshotBudget | None = None) -> int:
    """Measure the existing container-based deep size, yielding during traversal.

    Snapshot each container's children before yielding so game/socket mutations
    cannot invalidate an iterator. Model attributes are not recursively traversed,
    matching the previous diagnostic's size convention.
    """
    budget = budget or SnapshotBudget()
    seen: set[int] = set()
    pending = [iter((obj,))]
    size = 0
    visited = 0
    while pending:
        if visited % METRICS_BATCH_SIZE == 0:
            await budget.checkpoint()
        visited += 1
        try:
            current = next(pending[-1])
        except StopIteration:
            pending.pop()
            continue
        obj_id = id(current)
        if obj_id in seen:
            continue
        seen.add(obj_id)
        size += sys.getsizeof(current)
        if isinstance(current, dict):
            pending.append(iter(chain.from_iterable(tuple(current.items()))))
        elif isinstance(current, Iterable) and not isinstance(current, (str, bytes, bytearray)):
            pending.append(iter(tuple(current)))
    return size


async def memory_stats(
    top_n: int = 20, need_inspect: bool = False, *, budget: SnapshotBudget | None = None
) -> tuple[list[AllocationStat], list[TaskInfo], list[QueueInfo], dict[str, int]]:
    """Inspect tracked objects cooperatively, without forcing garbage collection.

    gc.get_objects() itself is one native call; the much longer Python traversal
    yields in bounded batches. Tasks and queues are inspected on their event loop.
    """
    budget = budget or SnapshotBudget()

    objects: list[object] = gc.get_objects()

    type_info: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "size": 0})

    tasks: list[TaskInfo] = []
    queues: list[QueueInfo] = []

    for index, obj in enumerate(objects):
        if index % METRICS_BATCH_SIZE == 0:
            await budget.checkpoint()
        if isinstance(obj, MONITORED_TYPES):
            obj_type = type(obj).__name__
            type_info[obj_type]["count"] += 1
            if isinstance(obj, Task):
                type_info[obj_type]["size"] += sys.getsizeof(obj)
                # TODO: using inspect modul is rather time consuming
                # Add a new switch to the monitor TUI to enable this
                stack = obj.get_stack(limit=1) if need_inspect else ""
                if TYPE_CHECKING:
                    assert isinstance(stack, list)
                if len(stack) > 0:
                    stack_file = "/".join(inspect.getfile(stack[0]).split("/")[-2:])
                    # stack_source = inspect.getsource(stack[0])[:25]
                    stack_source = "-"

                    if 0:  # "aiohttp" in stack_file:
                        referrers = gc.get_referrers(obj)  # type: ignore[unreachable]
                        print("------", obj.get_name())
                        for ref in referrers:
                            inspect_referrer(ref)
                else:
                    stack_file = "-"
                    stack_source = "-"

                tasks.append(
                    {
                        "id": id(obj),
                        "name": obj.get_name(),
                        "state": obj._state,
                        "file": stack_file,
                        "source": stack_source,
                    }
                )

            elif isinstance(obj, Queue):
                queues.append(
                    {
                        "id": id(obj),
                        "name": type(obj).__name__,
                        "size": obj.qsize(),
                        "maxsize": obj.maxsize,
                        "full": obj.full(),
                        "file": "-",
                        "source": "-",
                    }
                )
            else:
                type_info[obj_type]["size"] += await get_deep_size(obj, budget)

    type_counts = {obj_type: info["count"] for obj_type, info in type_info.items()}

    # Sort by total deep size descending
    sorted_types = sorted(type_info.items(), key=lambda x: x[1]["size"], reverse=True)[:top_n]

    # Convert to list of dicts for easy consumption/printing
    result: list[AllocationStat] = [
        {
            "type": t,
            "count": info["count"],
            "size_bytes": info["size"],
            "size_human": (
                f"{info['size'] / 1024 / 1024:.2f} MB"
                if info["size"] >= 1024 * 1024
                else (
                    f"{info['size'] / 1024:.2f} KB"
                    if info["size"] >= 1024
                    else f"{info['size']} bytes"
                )
            ),
        }
        for t, info in sorted_types
    ]

    return result, tasks, queues, type_counts


async def metrics_handler(request: web.Request) -> web.StreamResponse:
    """Return server metrics as JSON."""
    auth = request.headers.get("Authorization")
    if auth is None:
        log.error("metrics request without Authorization header!")
        raise web.HTTPNotFound()

    token = auth[auth.find("Bearer") + 7 :]
    if URI != LOCALHOST and token != PYCHESS_MONITOR_TOKEN:
        log.error("Invalid pychess-metrics token!")
        raise web.HTTPNotFound()

    app_state = get_app_state(request.app)
    if request.rel_url.query.get("summary", "").casefold() == "true":
        return json_response(_lightweight_metrics(app_state, request))

    need_inspect = request.rel_url.query.get("inspect", "").casefold() == "true"
    body = await app_state.full_metrics_snapshot.get(app_state, request, need_inspect)
    return web.Response(
        body=body, content_type="application/json", headers={"Cache-Control": "no-store"}
    )


async def _full_metrics(
    app_state: PychessGlobalAppState, request: web.Request, need_inspect: bool
) -> dict[str, object]:
    active_connections = app_state.lobby.lobbysockets
    budget = SnapshotBudget()
    start = time.process_time()
    top_stats, tasks, queues, type_counts = await memory_stats(15, need_inspect, budget=budget)
    log.debug("Running memory_stats() CPU time: %s", time.process_time() - start)

    # Prepare object details
    now = datetime.now(UTC)

    users: list[dict[str, object]] = [
        {
            "title": user.title,
            "username": user.username,
            "anon": user.anon,
            "reserved": reserved(user.username),
            "online": user.online,
            "ever_connected": getattr(user, "ever_connected", False),
            "last_seen": user.last_seen,
            "last_seen_default": user.last_seen.year <= 1,
            "idle_mins": (
                ""
                if user.last_seen.year <= 1
                else int((now - user.last_seen).total_seconds() // 60)
            ),
            "game_in_progress": user.game_in_progress or "",
            "corr_games": len(user.correspondence_games),
            "lobby_sockets": len(user.lobby_sockets),
            "game_socket_games": len(user.game_sockets),
            "game_socket_total": sum(len(ws_set) for ws_set in user.game_sockets.values()),
            "challenge_channels": len(user.challenge_channels),
            "notify_channels": len(user.notify_channels),
            "inbox_channels": len(user.inbox_channels),
            "notifications": 0 if user.notifications is None else len(user.notifications),
            "tournament_sockets": sum(len(ws_set) for ws_set in user.tournament_sockets.values()),
            "simul_sockets": sum(len(ws_set) for ws_set in user.simul_sockets.values()),
            "study_sockets": sum(len(ws_set) for ws_set in user.study_sockets.values()),
            "abandon_tasks": len(user.abandon_game_tasks),
            "background_tasks": len(user.background_tasks),
            "remove_anon_task": _task_state(user.remove_anon_task),
            "game_queues": len(user.game_queues) if user.bot else "",
        }
        async for username, user in _batched(
            sorted(app_state.users.items(), key=lambda x: x[1].last_seen, reverse=True), budget
        )
    ]
    seeks: list[dict[str, object]] = [
        {
            "id": seek_id,
            "creator": seek.creator.username,
            "target": seek.target,
            "expire_at": seek.expire_at,
            "variant": seek.variant,
            "base": seek.base,
            "inc": seek.inc,
            "day": seek.day,
            "rated": seek.rated,
        }
        async for seek_id, seek in _batched(
            sorted(
                app_state.seeks.items(), key=lambda x: _seek_expire_sort_key(x[1]), reverse=True
            ),
            budget,
        )
    ]
    games: list[dict[str, object]] = [
        {
            "id": game_id,
            "date": game.date,
            "status": game.status,
            "players": (game.wplayer.username, game.bplayer.username),
        }
        async for game_id, game in _batched(
            sorted(app_state.games.items(), key=lambda x: x[1].date, reverse=True), budget
        )
    ]
    connections: list[dict[str, str]] = [
        {"id": username, "timestamp": datetime.now(UTC).isoformat()}
        async for username in _batched(tuple(app_state.lobby.lobbysockets), budget)
    ]

    user_objects_total = type_counts.get("User", 0)
    detached_user_objects = max(0, user_objects_total - len(users))

    anon_users: list[dict[str, object]] = []
    anon_total = 0
    anon_online = 0
    anon_removable_now = 0
    anon_default_last_seen = 0
    anon_never_connected = 0
    anon_with_remove_task = 0
    anon_idle_lt_10m = 0
    anon_idle_10m_to_60m = 0
    anon_idle_over_60m = 0
    anon_pending_remove_idle_default = 0
    anon_pending_remove_idle_lt_10m = 0
    anon_pending_remove_idle_10m_to_60m = 0
    anon_pending_remove_idle_over_60m = 0
    anon_removable_idle_default = 0
    anon_removable_idle_lt_10m = 0
    anon_removable_idle_10m_to_60m = 0
    anon_removable_idle_over_60m = 0
    anon_blocker_game_in_progress = 0
    anon_blocker_correspondence_games = 0
    anon_blocker_game_sockets = 0
    anon_blocker_lobby_sockets = 0
    anon_blocker_challenge_channels = 0
    anon_blocker_tournament_sockets = 0
    anon_blocker_simul_sockets = 0

    async for user in _batched(tuple(app_state.users.values()), budget):
        if (not user.anon) or reserved(user.username):
            continue

        anon_total += 1
        lobby_sockets = len(user.lobby_sockets)
        game_socket_games = len(user.game_sockets)
        game_socket_total = sum(len(ws_set) for ws_set in user.game_sockets.values())
        challenge_channels = len(user.challenge_channels)
        tournament_sockets = sum(len(ws_set) for ws_set in user.tournament_sockets.values())
        simul_sockets = sum(len(ws_set) for ws_set in user.simul_sockets.values())
        corr_games = len(user.correspondence_games)
        last_seen_default = user.last_seen.year <= 1
        idle_mins: int | None = (
            None if last_seen_default else int((now - user.last_seen).total_seconds() // 60)
        )
        blockers: list[str] = []
        if user.game_in_progress is not None:
            blockers.append("game_in_progress")
            anon_blocker_game_in_progress += 1
        if corr_games > 0:
            blockers.append("correspondence_games")
            anon_blocker_correspondence_games += 1
        if game_socket_games > 0:
            blockers.append("game_sockets")
            anon_blocker_game_sockets += 1
        if lobby_sockets > 0:
            blockers.append("lobby_sockets")
            anon_blocker_lobby_sockets += 1
        if challenge_channels > 0:
            blockers.append("challenge_channels")
            anon_blocker_challenge_channels += 1
        if tournament_sockets > 0:
            blockers.append("tournament_sockets")
            anon_blocker_tournament_sockets += 1
        if simul_sockets > 0:
            blockers.append("simul_sockets")
            anon_blocker_simul_sockets += 1

        task_state = _task_state(user.remove_anon_task)
        if task_state == "pending":
            anon_with_remove_task += 1
            if last_seen_default:
                anon_pending_remove_idle_default += 1
            elif TYPE_CHECKING:
                assert idle_mins is not None
                if idle_mins < 10:
                    anon_pending_remove_idle_lt_10m += 1
                elif idle_mins < 60:
                    anon_pending_remove_idle_10m_to_60m += 1
                else:
                    anon_pending_remove_idle_over_60m += 1
            else:
                if idle_mins is not None and idle_mins < 10:
                    anon_pending_remove_idle_lt_10m += 1
                elif idle_mins is not None and idle_mins < 60:
                    anon_pending_remove_idle_10m_to_60m += 1
                elif idle_mins is not None:
                    anon_pending_remove_idle_over_60m += 1
        if user.online:
            anon_online += 1
        if last_seen_default:
            anon_default_last_seen += 1
        if not getattr(user, "ever_connected", False):
            anon_never_connected += 1

        if not last_seen_default:
            if TYPE_CHECKING:
                assert idle_mins is not None
            if idle_mins is not None and idle_mins < 10:
                anon_idle_lt_10m += 1
                if len(blockers) == 0:
                    anon_removable_idle_lt_10m += 1
            elif idle_mins is not None and idle_mins < 60:
                anon_idle_10m_to_60m += 1
                if len(blockers) == 0:
                    anon_removable_idle_10m_to_60m += 1
            elif idle_mins is not None:
                anon_idle_over_60m += 1
                if len(blockers) == 0:
                    anon_removable_idle_over_60m += 1

        if last_seen_default and len(blockers) == 0:
            anon_removable_idle_default += 1
        if len(blockers) == 0:
            anon_removable_now += 1

        anon_users.append(
            {
                "username": user.username,
                "online": user.online,
                "ever_connected": getattr(user, "ever_connected", False),
                "last_seen": user.last_seen,
                "last_seen_default": last_seen_default,
                "idle_mins": "" if last_seen_default else idle_mins,
                "game_in_progress": user.game_in_progress or "",
                "corr_games": corr_games,
                "lobby_sockets": lobby_sockets,
                "game_socket_games": game_socket_games,
                "game_socket_total": game_socket_total,
                "challenge_channels": challenge_channels,
                "tournament_sockets": tournament_sockets,
                "simul_sockets": simul_sockets,
                "abandon_tasks": len(user.abandon_game_tasks),
                "remove_anon_task": task_state,
                "blockers": blockers,
                "removable_now": len(blockers) == 0,
            }
        )

    anon_users.sort(key=lambda row: cast(datetime, row["last_seen"]), reverse=True)

    started_games_no_round_sockets: list[dict[str, object]] = []
    async for game_id, game in _batched(tuple(app_state.games.items()), budget):
        if game.status != STARTED:
            continue

        non_bot_players = tuple(game.non_bot_players)
        if len(non_bot_players) == 0:
            continue

        players_with_round_socket = sum(
            1 for player in non_bot_players if player.is_user_active_in_game(game_id)
        )
        players_with_game_in_progress = sum(
            1 for player in non_bot_players if player.game_in_progress == game_id
        )
        if players_with_round_socket > 0:
            continue
        if players_with_game_in_progress == 0:
            continue

        started_games_no_round_sockets.append(
            {
                "id": game_id,
                "variant": game.variant,
                "status": game.status,
                "date": game.date,
                "players": [player.username for player in non_bot_players],
                "players_with_game_in_progress": players_with_game_in_progress,
                "spectators": len(game.spectators),
            }
        )

    started_games_no_round_sockets.sort(key=lambda row: cast(datetime, row["date"]), reverse=True)

    cache_rows = cache_stats()
    cache_entries = sum(row["currsize"] for row in cache_rows)
    process_memory_rows = [process_memory_stats()]

    tournament_rows: list[dict[str, object]] = [
        {
            "id": tournament_id,
            "type": type(tournament).__name__,
            "status": tournament.status,
            "variant": tournament.variant,
            "players": tournament.nb_players,
            "ongoing_games": len(tournament.ongoing_games),
            "clock_task": _task_state(tournament.clock_task),
            "created_at": tournament.created_at,
        }
        async for tournament_id, tournament in _batched(
            tuple(app_state.tournaments.items()), budget
        )
    ]
    tournament_rows.sort(key=lambda row: cast(datetime, row["created_at"]), reverse=True)

    simul_rows: list[dict[str, object]] = [
        {
            "id": simul_id,
            "status": simul.status,
            "variants": list(simul.variants),
            "host": simul.created_by,
            "players": len(simul.players),
            "pending_players": len(simul.pending_players),
            "games": len(simul.games),
            "ongoing_games": len(simul.ongoing_games),
            "spectators": len(simul.spectators),
            "clock_task": _task_state(simul.clock_task),
            "created_at": simul.created_at,
        }
        async for simul_id, simul in _batched(tuple(app_state.simuls.items()), budget)
    ]
    simul_rows.sort(key=lambda row: cast(datetime, row["created_at"]), reverse=True)

    monotonic_now = time.monotonic()
    fishnet_work_rows: list[dict[str, object]] = [
        {
            "id": work_id,
            "type": work["work"]["type"],
            "game_id": work.get("game_id", ""),
            "variant": work.get("variant", ""),
            "age_secs": max(0, int(monotonic_now - work.get("time", monotonic_now))),
            "stale_reissues": work.get("stale_reissue_count", 0),
            "abort_count": work.get("abort_count", 0),
        }
        async for work_id, work in _batched(tuple(app_state.fishnet_works.items()), budget)
    ]
    fishnet_work_rows.sort(key=lambda row: cast(int, row["age_secs"]), reverse=True)

    state_summary = [_state_summary(app_state, request)]
    state_entries = sum(cast(int, value) for value in state_summary[0].values())

    stream_summary = [_stream_summary(app_state)]
    stream_entries = sum(cast(int, value) for value in stream_summary[0].values())

    registered_summary = [_registered_summary(app_state)]

    anon_summary = [
        {
            "anon_total": anon_total,
            "anon_online_flag": anon_online,
            "anon_with_default_last_seen": anon_default_last_seen,
            "anon_never_connected": anon_never_connected,
            "anon_with_pending_remove_task": anon_with_remove_task,
            "anon_removable_now": anon_removable_now,
            "anon_idle_lt_10m": anon_idle_lt_10m,
            "anon_idle_10m_to_60m": anon_idle_10m_to_60m,
            "anon_idle_over_60m": anon_idle_over_60m,
            "anon_pending_remove_idle_default": anon_pending_remove_idle_default,
            "anon_pending_remove_idle_lt_10m": anon_pending_remove_idle_lt_10m,
            "anon_pending_remove_idle_10m_to_60m": anon_pending_remove_idle_10m_to_60m,
            "anon_pending_remove_idle_over_60m": anon_pending_remove_idle_over_60m,
            "anon_removable_idle_default": anon_removable_idle_default,
            "anon_removable_idle_lt_10m": anon_removable_idle_lt_10m,
            "anon_removable_idle_10m_to_60m": anon_removable_idle_10m_to_60m,
            "anon_removable_idle_over_60m": anon_removable_idle_over_60m,
            "anon_blocker_game_in_progress": anon_blocker_game_in_progress,
            "anon_blocker_correspondence_games": anon_blocker_correspondence_games,
            "anon_blocker_game_sockets": anon_blocker_game_sockets,
            "anon_blocker_lobby_sockets": anon_blocker_lobby_sockets,
            "anon_blocker_challenge_channels": anon_blocker_challenge_channels,
            "anon_blocker_tournament_sockets": anon_blocker_tournament_sockets,
            "anon_blocker_simul_sockets": anon_blocker_simul_sockets,
            "cached_users": len(users),
            "user_objects_total": user_objects_total,
            "detached_user_objects": detached_user_objects,
            "started_games_no_round_sockets": len(started_games_no_round_sockets),
        }
    ]

    # Calculate memory sizes
    user_memory_size = await get_deep_size(app_state.users, budget) / 1024  # Convert to KB
    game_memory_size = await get_deep_size(app_state.games, budget) / 1024  # Convert to KB
    task_memory_size = sum([sys.getsizeof(obj) for obj in tasks]) / 1024  # Convert to KB
    queue_memory_size = sum([sys.getsizeof(obj) for obj in queues]) / 1024  # Convert to KB
    conn_memory_size = await get_deep_size(active_connections, budget) / 1024  # Convert to KB
    anon_user_memory_size = await get_deep_size(anon_users, budget) / 1024
    started_game_no_socket_memory_size = (
        await get_deep_size(started_games_no_round_sockets, budget) / 1024
    )
    anon_summary_memory_size = await get_deep_size(anon_summary, budget) / 1024
    registered_summary_memory_size = await get_deep_size(registered_summary, budget) / 1024
    tournament_memory_size = await get_deep_size(app_state.tournaments, budget) / 1024
    simul_memory_size = await get_deep_size(app_state.simuls, budget) / 1024
    fishnet_work_memory_size = await get_deep_size(app_state.fishnet_works, budget) / 1024
    cache_memory_size = await get_deep_size(cache_rows, budget) / 1024
    state_memory_size = await get_deep_size(state_summary, budget) / 1024
    stream_memory_size = await get_deep_size(stream_summary, budget) / 1024

    metrics: dict[str, object] = {
        "active_connections": len(active_connections),
        "timestamp": datetime.now(UTC).isoformat(),
        "mode": "full",
        "heap_gc_collected": False,
        "top_allocations": [
            {
                "type": stat["type"],
                "count": stat["count"],
                "size_bytes": stat["size_bytes"],
                "size_human": stat["size_human"],
            }
            for stat in top_stats
        ],
        "object_counts": {
            "users": len(users),
            "seeks": len(seeks),
            "games": len(games),
            "tasks": len(tasks),
            "queues": len(queues),
            "connections": len(connections),
            "anon_users": len(anon_users),
            "started_games_no_round_sockets": len(started_games_no_round_sockets),
            "anon_summary": len(anon_summary),
            "registered_summary": len(registered_summary),
            "tournaments": len(tournament_rows),
            "simuls": len(simul_rows),
            "fishnet_works": len(fishnet_work_rows),
            "caches": cache_entries,
            "state": state_entries,
            "streams": stream_entries,
            "process_memory": cast(int, process_memory_rows[0]["rss_kib"]),
        },
        "object_sizes": {
            "users": user_memory_size,
            "seeks": await get_deep_size(app_state.seeks, budget) / 1024,
            "games": game_memory_size,
            "tasks": task_memory_size,
            "queues": queue_memory_size,
            "connections": conn_memory_size,
            "anon_users": anon_user_memory_size,
            "started_games_no_round_sockets": started_game_no_socket_memory_size,
            "anon_summary": anon_summary_memory_size,
            "registered_summary": registered_summary_memory_size,
            "tournaments": tournament_memory_size,
            "simuls": simul_memory_size,
            "fishnet_works": fishnet_work_memory_size,
            "caches": cache_memory_size,
            "state": state_memory_size,
            "streams": stream_memory_size,
            "process_memory": cast(int, process_memory_rows[0]["rss_kib"]),
        },
        "object_details": {
            "users": users,
            "seeks": seeks,
            "games": games,
            "tasks": tasks,
            "queues": queues,
            "connections": connections,
            "anon_users": anon_users,
            "started_games_no_round_sockets": started_games_no_round_sockets,
            "anon_summary": anon_summary,
            "registered_summary": registered_summary,
            "tournaments": tournament_rows,
            "simuls": simul_rows,
            "fishnet_works": fishnet_work_rows,
            "caches": cache_rows,
            "state": state_summary,
            "streams": stream_summary,
            "process_memory": process_memory_rows,
        },
    }
    log.debug("Collecting all metrics time: %s", (time.process_time() - start))

    return metrics
