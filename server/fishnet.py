from __future__ import annotations

import asyncio
import hashlib
import math
import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, cast

from aiohttp import web
from broadcast import round_broadcast
from catalogued_variants import (
    CATALOGUED_SOURCE_FSF_BUILTIN,
    catalogued_variant_ai_disabled,
    catalogued_variant_allows_fishnet,
    clear_catalogued_variant_ai_failures,
    extract_variant_base_name,
    record_catalogued_variant_ai_failure,
)
from const import ANALYSIS, INVALIDMOVE, MOVE, STARTED
from csrf import csrf_exempt
from typing_defs import (
    AnalysisStep,
    FishnetAbortPayload,
    FishnetAcquirePayload,
    FishnetAnalysisItem,
    FishnetAnalysisPayload,
    FishnetKeyPayload,
    FishnetMovePayload,
    FishnetScore,
    FishnetWork,
)

if TYPE_CHECKING:
    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
import logging

from game_analysis import enrich_game_analysis
from json_utils import json_response
from pychess_global_app_state_utils import get_app_state
from request_utils import read_json_data
from settings import FISHNET_KEYS
from utils import load_game, play_move

log = logging.getLogger(__name__)

REQUIRED_FISHNET_VERSION = "1.16.69"
_FISHNET_VERSION_RE = re.compile(r"\d+")
MOVE_WORK_TIME_OUT = 5.0
ANALYSIS_WORK_TIME_OUT = 15 * 60.0
FISHNET_ACTIVITY_TIMEOUT = 10 * 60.0
# Variants in this set require an explicitly advertised optional worker engine.
# Older fairyfishnet versions advertise no capabilities and therefore remain
# eligible for every ordinary Fairy-Stockfish variant, but never for Alice.
OPTIONAL_FISHNET_VARIANTS = frozenset(("alice",))


def fishnet_variant_requires_capability(variant: str) -> bool:
    return variant.lower() in OPTIONAL_FISHNET_VARIANTS


ENGINE_CRASH_REASON = "engine_crash"
ENGINE_TIMEOUT_REASON = "engine_timeout"
STALE_WORK_TIMEOUT_REASON = "work_timeout"
INVALID_FISHNET_MOVE_REASON = "invalid_move"
VARIANT_AI_DISABLED_REASON = "variant_ai_disabled"
ENGINE_FAILURE_REASONS = frozenset((ENGINE_CRASH_REASON, ENGINE_TIMEOUT_REASON))
CATALOGUED_QUARANTINE_REASONS = frozenset(
    (
        ENGINE_CRASH_REASON,
        ENGINE_TIMEOUT_REASON,
        STALE_WORK_TIMEOUT_REASON,
        INVALID_FISHNET_MOVE_REASON,
    )
)
# Keep generic abort limits conservative so transient worker/network issues do not
# adjudicate games too aggressively. Explicit engine failures use a tighter limit.
MOVE_ABORT_LIMIT = 6
MOVE_ENGINE_CRASH_LIMIT = 2
ANALYSIS_ABORT_LIMIT = 4
ANALYSIS_ENGINE_CRASH_LIMIT = 2
# A stale reissue means fishnet acquired the job, but the backend did not receive
# a move, analysis update, or explicit abort before the work timeout. Count these
# separately so a dead worker/process cannot make the same job circulate forever.
MOVE_STALE_REISSUE_LIMIT = 6
ANALYSIS_STALE_REISSUE_LIMIT = 2
# A fishnet move failure means the worker returned a malformed/empty move or the
# backend rejected the returned move before it could be applied safely. Retry a
# small number of times before adjudicating the game and recording a catalogued
# variant AI failure.
MOVE_INVALID_MOVE_LIMIT = 2


FISHNET_VARIANTS_PAYLOAD_CACHE_SIZE = 128
FISHNET_VARIANTS_PAYLOAD_CACHE_MAX_BYTES = 2 * 1024 * 1024


def fishnet_variants_payload_cache_bytes(app_state: PychessGlobalAppState) -> int:
    return sum(
        len(payload.get("variantsIni", "").encode("utf-8"))
        for payload in _fishnet_variants_payload_cache(app_state).values()
    )


def _fishnet_variants_payload_cache(
    app_state: PychessGlobalAppState,
) -> dict[str, dict[str, str]]:
    cache = getattr(app_state, "fishnet_variant_payloads", None)
    if cache is None:
        cache = {}
        app_state.fishnet_variant_payloads = cache
    return cache


def _cache_fishnet_variants_payload(
    app_state: PychessGlobalAppState, payload: dict[str, str]
) -> dict[str, str]:
    cache = _fishnet_variants_payload_cache(app_state)
    sha256 = payload["variantsSha256"]
    cache[sha256] = payload
    while (
        len(cache) > FISHNET_VARIANTS_PAYLOAD_CACHE_SIZE
        or fishnet_variants_payload_cache_bytes(app_state)
        > FISHNET_VARIANTS_PAYLOAD_CACHE_MAX_BYTES
    ):
        pinned = {
            str(work.get("variantsSha256"))
            for work in getattr(app_state, "fishnet_works", {}).values()
            if work.get("variantsSha256")
        }
        # The payload currently being cached may be attached to a work item only
        # after this function returns. Protect it as well so an immutable Study
        # snapshot cannot disappear between queueing and the worker's rules fetch.
        pinned.add(sha256)
        evict = next((key for key in cache if key not in pinned), None)
        if evict is None:
            break
        cache.pop(evict)
    return payload


def _catalogued_doc_base_name(doc: dict[str, object]) -> str:
    base_name = str(doc.get("baseVariant") or "").strip()
    if base_name:
        return base_name
    try:
        return extract_variant_base_name(str(doc.get("ini") or "")).strip()
    except Exception:
        return ""


def _split_fishnet_ini_sections(ini: str) -> dict[str, tuple[str, str]]:
    """Split a trusted Fairy-Stockfish INI into named section definitions."""

    sections: dict[str, tuple[str, str]] = {}
    current_name = ""
    current_base = ""
    current_lines: list[str] = []

    def flush() -> None:
        if not current_name:
            return
        text = "".join(current_lines).strip()
        if text:
            sections[current_name] = (current_base, text + "\n")

    for line in ini.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            flush()
            body = stripped[1:-1]
            name_part, separator, base_part = body.partition(":")
            current_name = name_part.strip()
            current_base = base_part.strip() if separator else ""
            current_lines = [line]
        elif current_name:
            current_lines.append(line)

    flush()
    return sections


@lru_cache(maxsize=1)
def _site_fishnet_ini_sections() -> dict[str, tuple[str, str]]:
    base_path = Path(__file__).resolve().parents[1] / "variants.ini"
    return _split_fishnet_ini_sections(base_path.read_text(encoding="utf-8"))


_CUSTOM_VARIANT_UNAVAILABLE = object()


def _fishnet_custom_definition(
    app_state: PychessGlobalAppState, variant_name: str
) -> tuple[str, str] | object | None:
    catalogued_docs = getattr(app_state, "catalogued_variants", {})
    doc = catalogued_docs.get(variant_name)
    if doc is not None and doc.get("ini"):
        if not doc.get("enabled", True) or catalogued_variant_ai_disabled(doc):
            return _CUSTOM_VARIANT_UNAVAILABLE
        return _catalogued_doc_base_name(doc), str(doc["ini"]).strip() + "\n"

    # Catalogued Fairy-Stockfish built-ins are metadata-only and therefore have
    # no INI. They may still be the engine-provided base of a checked-in site
    # variant, as pocketknight is for synochess, so they must not hide that site
    # definition or invalidate the custom chain collected so far.
    if doc is not None and doc.get("source") != CATALOGUED_SOURCE_FSF_BUILTIN:
        return _CUSTOM_VARIANT_UNAVAILABLE
    return _site_fishnet_ini_sections().get(variant_name)


def _fishnet_custom_ini_chain(
    app_state: PychessGlobalAppState, variant_name: str | None
) -> list[str]:
    """Return only the custom definition chain required by one job."""

    if not variant_name:
        return []

    chain: list[str] = []
    seen: set[str] = set()
    current_name = variant_name
    while current_name:
        if current_name in seen:
            log.error("Cyclic fishnet variant inheritance involving %s", current_name)
            return []
        seen.add(current_name)

        definition = _fishnet_custom_definition(app_state, current_name)
        if definition is _CUSTOM_VARIANT_UNAVAILABLE:
            return []
        if definition is None:
            break

        base_name, ini = cast(tuple[str, str], definition)
        chain.append(ini)
        current_name = base_name

    chain.reverse()
    return chain


def fishnet_variants_ini(app_state: PychessGlobalAppState, variant_name: str | None = None) -> str:
    """Return the minimal custom definition chain required by one fishnet job."""

    chain = _fishnet_custom_ini_chain(app_state, variant_name)
    if not chain:
        return ""
    return "\n".join(part.strip() for part in chain) + "\n"


def fishnet_variants_payload(
    app_state: PychessGlobalAppState, variant_name: str | None = None
) -> dict[str, str] | None:
    variants_ini = fishnet_variants_ini(app_state, variant_name)
    if not variants_ini:
        return None
    payload = {
        "variantsIni": variants_ini,
        "variantsSha256": hashlib.sha256(variants_ini.encode("utf-8")).hexdigest(),
    }
    if variant_name:
        payload["variantsScope"] = variant_name
    return _cache_fishnet_variants_payload(app_state, payload)


def fishnet_variants_payload_from_ini(
    app_state: PychessGlobalAppState, variant_name: str, variants_ini: str
) -> dict[str, str]:
    """Cache an immutable rules payload for work pinned to a Study snapshot.

    Historical Study variants run under a content-hashed alias. Include any custom
    base definitions that the current server can resolve, then keep this exact text
    addressable by hash for the lifetime of the queued/reissued Fishnet job.
    """

    base_name = extract_variant_base_name(variants_ini).strip()
    base_chain = _fishnet_custom_ini_chain(app_state, base_name) if base_name else []
    parts = [*base_chain, variants_ini.strip() + "\n"]
    exact_ini = "\n".join(part.strip() for part in parts if part.strip()) + "\n"
    payload = {
        "variantsIni": exact_ini,
        "variantsSha256": hashlib.sha256(exact_ini.encode("utf-8")).hexdigest(),
        "variantsScope": variant_name,
    }
    return _cache_fishnet_variants_payload(app_state, payload)


def _attach_variants_hash(app_state: PychessGlobalAppState, work: FishnetWork) -> None:
    variant_name = str(work.get("variant") or "")
    pinned_sha256 = work.get("variantsSha256")
    pinned_scope = work.get("variantsScope")
    if pinned_sha256 and pinned_scope == variant_name:
        cached = _fishnet_variants_payload_cache(app_state).get(pinned_sha256)
        if cached is not None and cached.get("variantsScope") == variant_name:
            return
    work.pop("variantsSha256", None)
    work.pop("variantsScope", None)
    payload = fishnet_variants_payload(app_state, variant_name)
    if payload is None:
        return
    work["variantsSha256"] = payload["variantsSha256"]
    work["variantsScope"] = payload.get("variantsScope", "")


def _variant_allows_cached_fishnet_payload(
    app_state: PychessGlobalAppState, variant_name: str | None
) -> bool:
    if not variant_name:
        return False
    catalogued_docs = getattr(app_state, "catalogued_variants", {})
    if variant_name in catalogued_docs:
        return catalogued_variant_allows_fishnet(app_state, variant_name)
    if re.fullmatch(r"studysnap_[0-9a-f]{12}", variant_name):
        return True
    return variant_name in _site_fishnet_ini_sections()


async def fishnet_variants(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in FISHNET_KEYS:
        return web.Response(status=404)

    app_state = get_app_state(request.app)
    requested_sha256 = request.query.get("sha256")
    variant_name = request.query.get("variant")

    if requested_sha256:
        cached = _fishnet_variants_payload_cache(app_state).get(requested_sha256)
        if (
            cached is not None
            and cached.get("variantsScope") == variant_name
            and _variant_allows_cached_fishnet_payload(app_state, variant_name)
        ):
            return json_response(cached)

    payload = fishnet_variants_payload(app_state, variant_name)
    if payload is None:
        if requested_sha256:
            return json_response(
                {
                    "error": (
                        "The exact variants.ini requested by this fishnet job "
                        "is no longer available."
                    )
                },
                status=409,
            )
        return json_response(
            {"error": "This variant does not require custom fishnet rules."}, status=404
        )

    if requested_sha256 and payload["variantsSha256"] != requested_sha256:
        log.warning(
            "Fishnet requested variants.ini hash %s for variant %s, but current hash is %s",
            requested_sha256,
            variant_name or "<full>",
            payload["variantsSha256"],
        )
        return json_response(
            {
                "error": (
                    "The exact variants.ini requested by this fishnet job is no longer available."
                ),
                "variantsSha256": payload["variantsSha256"],
            },
            status=409,
        )
    return json_response(payload)


def _work_priority(work: FishnetWork) -> int:
    return ANALYSIS if work["work"]["type"] == "analysis" else MOVE


def _fishnet_version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in _FISHNET_VERSION_RE.findall(version))


def _fishnet_version_is_supported(version: str) -> bool:
    parsed = _fishnet_version_tuple(version)
    required = _fishnet_version_tuple(REQUIRED_FISHNET_VERSION)
    if not parsed or not required:
        return False
    width = max(len(parsed), len(required))
    return parsed + (0,) * (width - len(parsed)) >= required + (0,) * (width - len(required))


def _abort_reason(data: FishnetAbortPayload) -> str:
    error = data.get("error")
    if error is None:
        return "unknown"
    reason = error.get("reason")
    return reason if reason else "unknown"


def _work_timeout(work: FishnetWork) -> float:
    return ANALYSIS_WORK_TIME_OUT if work["work"]["type"] == "analysis" else MOVE_WORK_TIME_OUT


def _winning_chances(score: FishnetScore) -> float:
    """Convert a fishnet score dict to winning chances in [-1.0, 1.0] from White's POV.

    Formula and mate conversion match pychess client/analysis/winningChances.ts,
    which mirrors https://github.com/lichess-org/lila/blob/master/ui/ceval/src/winningChances.ts.
    """
    if "mate" in score:
        mate = score["mate"]
        cp = (21 - min(10, abs(mate))) * 100 * (1 if mate > 0 else -1)
    else:
        cp = max(-1000, min(1000, score.get("cp", 0)))
    return 2 / (1 + math.exp(-0.004 * cp)) - 1


def _should_save_analysis_pv(
    analysis: FishnetAnalysisItem,
    prev: FishnetAnalysisItem | None,
    turn_color: str | None,
    ply: int,
) -> bool:
    """Decide whether the engine PV for this step is worth persisting.

    Save PV only for an inaccuracy, mistake, or blunder (winning chances drop >= 10%).
    Thresholds from lila: github.com/lichess-org/lila/blob/master/modules/tree/src/main/Advice.scala

    turn_color is the color to move *after* this step (game.steps[i]["turnColor"]),
    so "black" means White just moved and "white" means Black just moved. When
    turnColor is missing (legacy/malformed step data) we fall back to ply parity.
    """
    if "pv" not in analysis or prev is None:
        return False
    if "score" not in analysis or "score" not in prev:
        # Defensive guard against a future {"skipped": True}-style payload shape
        # (pychess does not send skipPositions today, but this keeps the function
        # itself safe to call with a malformed/partial FishnetAnalysisItem).
        return False
    white_delta = _winning_chances(analysis["score"]) - _winning_chances(prev["score"])
    if turn_color == "black":
        drop = -white_delta
    elif turn_color == "white":
        drop = white_delta
    else:
        drop = -white_delta if ply % 2 == 1 else white_delta
    return drop >= 0.1


def _compact_fishnet_queue(app_state: PychessGlobalAppState) -> int:
    """Drop stale and duplicate queue IDs while preserving genuinely queued work."""
    retained_ids: set[str] = set()
    retained: list[tuple[int, str]] = []
    drained = 0

    while True:
        try:
            priority, work_id = app_state.fishnet_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        drained += 1
        try:
            app_state.fishnet_queue.task_done()
        except ValueError:
            log.error("Fishnet queue accounting was already unbalanced during compaction")

        work = app_state.fishnet_works.get(work_id)
        if work is not None and work_id not in retained_ids:
            retained_ids.add(work_id)
            retained.append((priority, work_id))

    for item in retained:
        app_state.fishnet_queue.put_nowait(item)

    return drained - len(retained)


def drop_stale_analysis_work(app_state: PychessGlobalAppState, *, now: float | None = None) -> int:
    if now is None:
        now = monotonic()

    stale_ids = [
        work_id
        for work_id, work in tuple(app_state.fishnet_works.items())
        if work["work"]["type"] == "analysis"
        and not work.get("study_id")
        and now - work.get("time", now) > ANALYSIS_WORK_TIME_OUT
    ]
    for work_id in stale_ids:
        del app_state.fishnet_works[work_id]
    _compact_fishnet_queue(app_state)
    return len(stale_ids)


def drop_fishnet_work_for_game(app_state: PychessGlobalAppState, game_id: str) -> int:
    """Remove completed/evicted game work and compact stale PriorityQueue entries."""
    work_ids = {
        work_id
        for work_id, work in tuple(app_state.fishnet_works.items())
        if work.get("game_id") == game_id
    }
    for work_id in work_ids:
        app_state.fishnet_works.pop(work_id, None)
    _compact_fishnet_queue(app_state)
    return len(work_ids)


def _fishnet_worker_is_recent(app_state: PychessGlobalAppState, key: str, now: float) -> bool:
    return now - app_state.fishnet_worker_last_seen.get(key, 0.0) <= FISHNET_ACTIVITY_TIMEOUT


def _fishnet_capability_variants(
    data: FishnetKeyPayload | FishnetAcquirePayload | FishnetAnalysisPayload | FishnetMovePayload,
) -> frozenset[str]:
    capabilities = data["fishnet"].get("capabilities")
    if not isinstance(capabilities, dict):
        return frozenset()
    variants = capabilities.get("variants")
    if not isinstance(variants, list):
        return frozenset()
    return frozenset(str(variant).lower() for variant in variants if isinstance(variant, str))


def _worker_request_supports_work(
    data: FishnetKeyPayload | FishnetAcquirePayload | FishnetAnalysisPayload | FishnetMovePayload,
    work: FishnetWork,
) -> bool:
    variant = str(work.get("variant") or "").lower()
    return variant not in OPTIONAL_FISHNET_VARIANTS or variant in _fishnet_capability_variants(data)


def _fishnet_capability_last_seen(app_state: PychessGlobalAppState) -> dict[tuple[str, str], float]:
    last_seen = getattr(app_state, "fishnet_worker_capability_last_seen", None)
    if last_seen is None:
        last_seen = {}
        app_state.fishnet_worker_capability_last_seen = last_seen
    return last_seen


def _record_fishnet_capabilities(
    app_state: PychessGlobalAppState,
    data: FishnetKeyPayload | FishnetAcquirePayload | FishnetAnalysisPayload | FishnetMovePayload,
    *,
    now: float | None = None,
) -> None:
    if now is None:
        now = monotonic()
    key = data["fishnet"]["apikey"]
    last_seen = _fishnet_capability_last_seen(app_state)
    for variant in _fishnet_capability_variants(data):
        if variant in OPTIONAL_FISHNET_VARIANTS:
            last_seen[(key, variant)] = now


def _prune_stale_fishnet_capabilities(app_state: PychessGlobalAppState, *, now: float) -> None:
    last_seen = _fishnet_capability_last_seen(app_state)
    for capability, seen_at in tuple(last_seen.items()):
        if now - seen_at > FISHNET_ACTIVITY_TIMEOUT:
            last_seen.pop(capability, None)


def _sync_alice_stockfish_online(
    app_state: PychessGlobalAppState, *, now: float | None = None
) -> None:
    users = getattr(app_state, "users", None)
    if users is None:
        return
    users_data = getattr(users, "data", users)
    alice_stockfish = users_data.get("Alice-Stockfish")
    if alice_stockfish is None:
        return
    if now is None:
        now = monotonic()
    capability_last_seen = _fishnet_capability_last_seen(app_state)
    alice_stockfish.online = any(
        key in app_state.workers
        and _fishnet_worker_is_recent(app_state, key, now)
        and now - capability_last_seen.get((key, "alice"), 0.0) <= FISHNET_ACTIVITY_TIMEOUT
        for key in app_state.workers
    )


def _fishnet_bot_player(app_state: PychessGlobalAppState, game: Game):
    wplayer = getattr(game, "wplayer", None)
    bplayer = getattr(game, "bplayer", None)
    bot_players = [player for player in (wplayer, bplayer) if player is not None and player.bot]
    if len(bot_players) == 1:
        return bot_players[0]
    if wplayer is not None and bplayer is not None:
        return bplayer if game.board.color else wplayer
    return app_state.users["Fairy-Stockfish"]


def prune_stale_fishnet_workers(
    app_state: PychessGlobalAppState, *, now: float | None = None
) -> int:
    if now is None:
        now = monotonic()

    stale_keys = [
        key
        for key in tuple(app_state.workers)
        if not _fishnet_worker_is_recent(app_state, key, now)
    ]
    _prune_stale_fishnet_capabilities(app_state, now=now)

    monitor = getattr(app_state, "fishnet_monitor", None)
    for key in stale_keys:
        app_state.workers.discard(key)
        app_state.fishnet_worker_last_seen.pop(key, None)
        worker = FISHNET_KEYS.get(key, key)
        if monitor is not None:
            monitor[worker].append("%s %s %s" % (datetime.now(UTC), "-", "timed out"))

    if stale_keys and len(app_state.workers) == 0:
        users = app_state.users
        if "Fairy-Stockfish" in users:
            users["Fairy-Stockfish"].online = False

    _sync_alice_stockfish_online(app_state, now=now)
    return len(stale_keys)


def has_recent_fishnet_activity(
    app_state: PychessGlobalAppState, *, now: float | None = None
) -> bool:
    if now is None:
        now = monotonic()

    return any(_fishnet_worker_is_recent(app_state, key, now) for key in app_state.workers)


def has_available_fishnet_worker(
    app_state: PychessGlobalAppState,
    *,
    variant: str | None = None,
    now: float | None = None,
) -> bool:
    if now is None:
        now = monotonic()
    prune_stale_fishnet_workers(app_state, now=now)
    if not app_state.workers:
        return False

    normalized_variant = (variant or "").lower()
    if normalized_variant not in OPTIONAL_FISHNET_VARIANTS:
        return True

    capability_last_seen = _fishnet_capability_last_seen(app_state)
    return any(
        key in app_state.workers
        and (key, normalized_variant) in capability_last_seen
        and now - capability_last_seen.get((key, normalized_variant), 0.0)
        <= FISHNET_ACTIVITY_TIMEOUT
        for key in app_state.workers
    )


def has_pending_analysis_work_for_game(app_state: PychessGlobalAppState, game_id: str) -> bool:
    return any(
        work["work"]["type"] == "analysis" and work.get("game_id") == game_id
        for work in app_state.fishnet_works.values()
    )


def _engine_failure_count(work: FishnetWork) -> int:
    # engine_crash_count is kept as a fallback for work created by older server code.
    return work.get("engine_failure_count", work.get("engine_crash_count", 0))


def _invalid_move_count(work: FishnetWork) -> int:
    return work.get("move_failure_count", 0)


def _is_terminal_invalid_move(work: FishnetWork) -> bool:
    return _invalid_move_count(work) >= MOVE_INVALID_MOVE_LIMIT


def _fishnet_bestmove(data: FishnetMovePayload) -> str | None:
    # Be defensive at the HTTP boundary even though normal fairyfishnet clients
    # send the typed shape. A crashed/buggy worker or future protocol change must
    # not turn into a backend 500 or lose the work item.
    move_info = data.get("move")
    if not isinstance(move_info, dict):
        return None

    bestmove = move_info.get("bestmove")
    if not isinstance(bestmove, str):
        return None

    bestmove = bestmove.strip()
    if not bestmove or bestmove == "(none)":
        return None
    return bestmove


def _game_move_stack_string(game: Game) -> str:
    return " ".join(game.board.move_stack)


def _fishnet_work_matches_current_position(work: FishnetWork, game: Game) -> bool:
    return str(work.get("moves") or "") == _game_move_stack_string(game)


def _stale_reissue_limit(work: FishnetWork) -> int:
    return (
        ANALYSIS_STALE_REISSUE_LIMIT
        if work["work"]["type"] == "analysis"
        else MOVE_STALE_REISSUE_LIMIT
    )


def _stale_reissue_count(work: FishnetWork) -> int:
    return work.get("stale_reissue_count", 0)


def _is_terminal_stale_reissue(work: FishnetWork) -> bool:
    return _stale_reissue_count(work) >= _stale_reissue_limit(work)


def _is_terminal_abort(work: FishnetWork, abort_reason: str) -> bool:
    abort_count = work.get("abort_count", 0)
    engine_failure_count = _engine_failure_count(work)
    if work["work"]["type"] == "move":
        return (abort_count >= MOVE_ABORT_LIMIT) or (
            abort_reason in ENGINE_FAILURE_REASONS
            and engine_failure_count >= MOVE_ENGINE_CRASH_LIMIT
        )
    return (abort_count >= ANALYSIS_ABORT_LIMIT) or (
        abort_reason in ENGINE_FAILURE_REASONS
        and engine_failure_count >= ANALYSIS_ENGINE_CRASH_LIMIT
    )


def _work_variant_allows_fishnet(app_state: PychessGlobalAppState, work: FishnetWork) -> bool:
    return catalogued_variant_allows_fishnet(app_state, str(work.get("variant") or ""))


async def _record_terminal_catalogued_ai_failure(
    app_state: PychessGlobalAppState,
    work: FishnetWork,
    failure_reason: str,
) -> None:
    if failure_reason not in CATALOGUED_QUARANTINE_REASONS:
        return
    await record_catalogued_variant_ai_failure(
        app_state,
        str(work.get("variant") or ""),
        failure_reason,
    )


async def _adjudicate_failing_move_work(
    app_state: PychessGlobalAppState, work_id: str, work: FishnetWork, failure_reason: str
) -> None:
    game = await load_game(app_state, work["game_id"])
    if game is None:
        return
    if TYPE_CHECKING:
        assert isinstance(game, Game)

    if game.status > STARTED:
        return

    log.warning(
        "Adjudicating move work %s as engine loss after repeated fishnet failures "
        "(reason=%s, aborts=%s, engine_failures=%s, stale_reissues=%s)",
        work_id,
        failure_reason,
        work.get("abort_count", 0),
        _engine_failure_count(work),
        _stale_reissue_count(work),
    )

    bot_user = _fishnet_bot_player(app_state, game)
    async with game.move_lock:
        response = await game.game_ended(bot_user, "resign")

    # Ensure bot loops also receive terminal state and can clean up game tasks.
    for player in (game.wplayer, game.bplayer):
        if player.bot and game.id in player.game_queues:
            await player.game_queues[game.id].put(game.game_end)

    await round_broadcast(game, response, full=True)


async def _drop_terminal_work_failure(
    app_state: PychessGlobalAppState, work_id: str, work: FishnetWork, failure_reason: str
) -> None:
    await _record_terminal_catalogued_ai_failure(app_state, work, failure_reason)
    del app_state.fishnet_works[work_id]
    if work["work"]["type"] == "move":
        await _adjudicate_failing_move_work(app_state, work_id, work, failure_reason)
    else:
        if work.get("study_id"):
            from study.analysis import fail_study_server_analysis

            await fail_study_server_analysis(app_state, work, reason=failure_reason)
        log.warning(
            "Dropping analysis work %s after repeated fishnet failures "
            "(reason=%s, aborts=%s, engine_failures=%s, stale_reissues=%s)",
            work_id,
            failure_reason,
            work.get("abort_count", 0),
            _engine_failure_count(work),
            _stale_reissue_count(work),
        )


async def _handle_invalid_fishnet_move(
    app_state: PychessGlobalAppState, work_id: str, work: FishnetWork, detail: str
) -> None:
    work["move_failure_count"] = _invalid_move_count(work) + 1
    work["last_abort_reason"] = INVALID_FISHNET_MOVE_REASON

    if _is_terminal_invalid_move(work):
        log.warning(
            "Dropping fishnet move work %s after repeated invalid moves (failures=%s, detail=%s)",
            work_id,
            _invalid_move_count(work),
            detail,
        )
        await _drop_terminal_work_failure(app_state, work_id, work, INVALID_FISHNET_MOVE_REASON)
        return

    log.warning(
        "Requeueing fishnet move work %s after invalid move response (failures=%s/%s, detail=%s)",
        work_id,
        _invalid_move_count(work),
        MOVE_INVALID_MOVE_LIMIT,
        detail,
    )
    work["time"] = monotonic()
    app_state.fishnet_queue.put_nowait((_work_priority(work), work_id))


async def _read_fishnet_json(request: web.Request) -> tuple[object | None, int | None]:
    try:
        data = await read_json_data(request)
        if data is not None:
            return data, None
        log.debug(
            "Fishnet request body read aborted on %s from %s",
            request.rel_url.path,
            request.remote,
        )
        return None, 204
    except web.HTTPBadRequest:
        log.debug(
            "Invalid fishnet JSON payload on %s from %s",
            request.rel_url.path,
            request.remote,
        )
        return None, 400


async def get_work(
    app_state: PychessGlobalAppState,
    data: FishnetKeyPayload | FishnetAcquirePayload | FishnetAnalysisPayload | FishnetMovePayload,
) -> web.Response:
    fm = app_state.fishnet_monitor
    key = data["fishnet"]["apikey"]
    worker = FISHNET_KEYS[key]

    fishnet_work_queue = app_state.fishnet_queue
    deferred_work: list[tuple[int, str]] = []

    def restore_deferred_work() -> None:
        for priority, work_id in deferred_work:
            if work_id in app_state.fishnet_works:
                fishnet_work_queue.put_nowait((priority, work_id))
        deferred_work.clear()

    # priority can be "move" or "analysis"
    try:
        while True:
            try:
                (priority, work_id) = fishnet_work_queue.get_nowait()
                try:
                    fishnet_work_queue.task_done()
                except ValueError:
                    log.error(
                        "task_done() called more times than there were items placed in the queue in fishnet.py get_work()"
                    )
            except asyncio.QueueEmpty:
                break

            work = app_state.fishnet_works.get(work_id)
            if work is None:
                log.debug("Skipping stale fishnet queue item %s", work_id)
                continue
            if not _worker_request_supports_work(data, work):
                deferred_work.append((priority, work_id))
                continue
            if not _work_variant_allows_fishnet(app_state, work):
                log.warning(
                    "Dropping fishnet work %s because AI is temporarily disabled for variant %s",
                    work_id,
                    work.get("variant"),
                )
                await _drop_terminal_work_failure(
                    app_state, work_id, work, VARIANT_AI_DISABLED_REASON
                )
                continue

            # Track the latest assignment time so timeout-based re-acquire does not
            # immediately recycle the same work while another worker is processing it.
            work["time"] = monotonic()

            # Trust the work payload type over queue metadata. This also recovers from
            # legacy enqueue mistakes where priority did not match work type.
            priority = _work_priority(work)
            if priority == ANALYSIS:
                fm[worker].append(
                    "%s %s %s %s of %s moves"
                    % (
                        datetime.now(UTC),
                        work_id,
                        "request",
                        "analysis",
                        len(work["moves"].split()),
                    )
                )

                if work.get("study_id"):
                    from study.analysis import study_analysis_work_is_current

                    if not await study_analysis_work_is_current(app_state, work):
                        app_state.fishnet_works.pop(work_id, None)
                        continue
                else:
                    # Game analysis starts from a clean in-memory analysis array. Study
                    # analysis is persisted separately and can resume after partial reports.
                    game_id = work.get("game_id")
                    if not game_id:
                        app_state.fishnet_works.pop(work_id, None)
                        continue
                    game = await load_game(app_state, game_id)
                    if game is None:
                        app_state.fishnet_works.pop(work_id, None)
                        continue

                    if len(game.steps) == 1 and game.ply > 0:
                        game.ensure_steps()
                    for step in game.steps:
                        if "analysis" in step:
                            del step["analysis"]

                    if "username" in work:
                        response = {
                            "type": "roundchat",
                            "user": "",
                            "room": "spectator",
                            "message": "Work for fishnet sent...",
                        }
                        await app_state.users[work["username"]].send_game_message(game_id, response)
            else:
                fm[worker].append(
                    "%s %s %s %s for level %s"
                    % (
                        datetime.now(UTC),
                        work_id,
                        "request",
                        "move",
                        work["work"]["level"],
                    )
                )

            _attach_variants_hash(app_state, work)
            return json_response(work, status=202)
    finally:
        restore_deferred_work()

    # There was no new work in the queue. Ok
    # Now let see are there any long time pending work in app[fishnet_works_key]
    # (in case when worker grabbed it from queue but not responded after timeout)
    now = monotonic()
    for work_id, work_item in tuple(app_state.fishnet_works.items()):
        if work_item.get("study_id"):
            from study.analysis import study_analysis_work_is_current

            if not await study_analysis_work_is_current(app_state, work_item):
                app_state.fishnet_works.pop(work_id, None)
                continue
        if not _worker_request_supports_work(data, work_item):
            continue
        if not _work_variant_allows_fishnet(app_state, work_item):
            log.warning(
                "Dropping stale fishnet work %s because AI is temporarily disabled for variant %s",
                work_id,
                work_item.get("variant"),
            )
            await _drop_terminal_work_failure(
                app_state, work_id, work_item, VARIANT_AI_DISABLED_REASON
            )
            continue
        if now - work_item["time"] <= _work_timeout(work_item):
            continue

        work_item["stale_reissue_count"] = _stale_reissue_count(work_item) + 1
        work_item["last_abort_reason"] = STALE_WORK_TIMEOUT_REASON
        if _is_terminal_stale_reissue(work_item):
            fm[worker].append(
                "%s %s %s %s"
                % (
                    datetime.now(UTC),
                    work_id,
                    "drop",
                    "%s after %s stale reissues"
                    % (work_item["work"]["type"], _stale_reissue_count(work_item)),
                )
            )
            await _drop_terminal_work_failure(
                app_state, work_id, work_item, STALE_WORK_TIMEOUT_REASON
            )
            continue

        fm[worker].append(
            "%s %s %s %s"
            % (
                datetime.now(UTC),
                work_id,
                "request",
                "%s AGAIN (%s/%s)"
                % (
                    work_item["work"]["type"],
                    _stale_reissue_count(work_item),
                    _stale_reissue_limit(work_item),
                ),
            )
        )
        work_item["time"] = now
        _attach_variants_hash(app_state, work_item)
        return json_response(work_item, status=202)
    return web.Response(status=204)


@csrf_exempt
async def fishnet_acquire(request: web.Request) -> web.Response:
    data_obj, error_status = await _read_fishnet_json(request)
    if data_obj is None:
        return web.Response(status=error_status or 400)
    # Fishnet payloads come from our own worker implementation, so we keep this boundary trusted.
    data = cast(FishnetAcquirePayload, data_obj)

    app_state = get_app_state(request.app)
    key = data["fishnet"]["apikey"]
    version = data["fishnet"]["version"]
    en = data["stockfish"]["name"]
    nnue = data["stockfish"].get("nnue", "")

    if key not in FISHNET_KEYS:
        return web.Response(status=404)
    if not _fishnet_version_is_supported(version):
        return json_response(
            {"error": "Fishnet %s is too old. Please restart fishnet to upgrade." % version},
            status=426,
        )

    worker = FISHNET_KEYS[key]
    now = monotonic()
    app_state.fishnet_worker_last_seen[key] = now
    _record_fishnet_capabilities(app_state, data, now=now)
    app_state.fishnet_versions[worker] = "%s %s" % (version, en)

    if key not in app_state.workers:
        app_state.workers.add(key)
        app_state.fishnet_monitor[worker].append("%s %s %s" % (datetime.now(UTC), "-", "joined"))
        app_state.fishnet_monitor[worker].append(nnue)
        app_state.users["Fairy-Stockfish"].online = True
    _sync_alice_stockfish_online(app_state, now=now)

    response = await get_work(app_state, data)
    return response


@csrf_exempt
async def fishnet_analysis(request: web.Request) -> web.Response:
    work_id = request.match_info["workId"]
    data_obj, error_status = await _read_fishnet_json(request)
    if data_obj is None:
        return web.Response(status=error_status or 400)
    # Fishnet payloads come from our own worker implementation, so we keep this boundary trusted.
    data = cast(FishnetAnalysisPayload, data_obj)

    app_state = get_app_state(request.app)
    key = data["fishnet"]["apikey"]

    if key not in FISHNET_KEYS:
        return web.Response(status=404)
    worker = FISHNET_KEYS[key]
    now = monotonic()
    app_state.fishnet_worker_last_seen[key] = now
    _record_fishnet_capabilities(app_state, data, now=now)
    _sync_alice_stockfish_online(app_state, now=now)

    if work_id not in app_state.fishnet_works:
        response = await get_work(app_state, data)
        return response

    work: FishnetWork = app_state.fishnet_works[work_id]
    app_state.fishnet_monitor[worker].append("%s %s %s" % (datetime.now(UTC), work_id, "analysis"))

    if work.get("study_id"):
        from study.analysis import merge_study_server_analysis

        await merge_study_server_analysis(app_state, work_id, work, data["analysis"])
        return web.Response(status=204)

    game_id = work.get("game_id")
    if not game_id:
        app_state.fishnet_works.pop(work_id, None)
        return web.Response(status=204)
    gameId = game_id
    game = await load_game(app_state, gameId)
    if game is None:
        app_state.fishnet_works.pop(work_id, None)
        return web.Response(status=204)

    if len(game.steps) == 1 and game.ply > 0:
        game.ensure_steps()
    username = work["username"]

    analysis_rows = data["analysis"]
    step_count = len(game.steps)
    known_zero_ply_worker_shape = (
        not work.get("moves") and step_count == 1 and len(analysis_rows) == 2
    )
    if len(analysis_rows) != step_count and not known_zero_ply_worker_shape:
        log.warning(
            "Fishnet analysis length mismatch for work %s game %s: received=%s steps=%s",
            work_id,
            gameId,
            len(analysis_rows),
            step_count,
        )

    # fairyfishnet 1.16.69 treats an empty move string as one empty move and
    # consequently returns two rows for a zero-ply game. Bound the response to
    # the server's reconstructed steps so that current deployed workers remain
    # compatible and malformed/stale responses cannot index past game.steps.
    analysis_rows = analysis_rows[:step_count]
    responses: list[dict[str, object]] = []
    length = len(analysis_rows)
    for j, analysis in enumerate(reversed(analysis_rows)):
        i = length - j - 1
        if analysis is None:
            continue

        # Revisit partial rows when their neighbour arrives. Advice must not be
        # lost merely because this position's evaluation arrived first.
        existing = game.steps[i].get("analysis")
        step_analysis: AnalysisStep = dict(existing) if existing is not None else {}
        step_analysis["s"] = analysis["score"]
        if "depth" in analysis:
            step_analysis["d"] = analysis["depth"]
        prev = analysis_rows[i - 1] if i > 0 else None
        turn_color = game.steps[i].get("turnColor")
        if game.server_variant.two_boards:
            if "p" not in step_analysis and _should_save_analysis_pv(analysis, prev, turn_color, i):
                step_analysis["p"] = analysis["pv"]
        else:
            enrich_game_analysis(game, i, prev, analysis, step_analysis)
        if step_analysis == existing:
            continue
        game.steps[i]["analysis"] = step_analysis
        response = {
            "type": "analysis",
            "ply": str(i),
            "color": "w" if turn_color == "white" else "b",
            "ceval": step_analysis,
        }
        responses.append(response)

    if (
        responses
        and not game.server_variant.two_boards
        and any(step.get("analysis", {}).get("advice") for step in game.steps)
    ):
        responses[-1]["pgn"] = game.pgn
    for response in responses:
        await app_state.users[username].send_game_message(gameId, response)

    # remove completed work
    if len(analysis_rows) == step_count and all(analysis_rows):
        del app_state.fishnet_works[work_id]
        await clear_catalogued_variant_ai_failures(app_state, str(work.get("variant") or ""))
        game.analysis = [step["analysis"] for step in game.steps]
        new_data = {"a": game.analysis}
        await app_state.db.game.find_one_and_update({"_id": game.id}, {"$set": new_data})

    return web.Response(status=204)


@csrf_exempt
async def fishnet_move(request: web.Request) -> web.Response:
    work_id = request.match_info["workId"]
    data_obj, error_status = await _read_fishnet_json(request)
    if data_obj is None:
        return web.Response(status=error_status or 400)
    # Fishnet payloads come from our own worker implementation, so we keep this boundary trusted.
    data = cast(FishnetMovePayload, data_obj)

    app_state = get_app_state(request.app)
    key = data["fishnet"]["apikey"]

    if key not in FISHNET_KEYS:
        return web.Response(status=404)
    worker = FISHNET_KEYS[key]
    now = monotonic()
    app_state.fishnet_worker_last_seen[key] = now
    _record_fishnet_capabilities(app_state, data, now=now)
    _sync_alice_stockfish_online(app_state, now=now)

    app_state.fishnet_monitor[worker].append("%s %s %s" % (datetime.now(UTC), work_id, "move"))

    if work_id not in app_state.fishnet_works:
        response = await get_work(app_state, data)
        return response

    work: FishnetWork = app_state.fishnet_works[work_id]
    gameId = work["game_id"]

    move = _fishnet_bestmove(data)
    if move is None:
        await _handle_invalid_fishnet_move(app_state, work_id, work, "missing or empty bestmove")
        return web.Response(status=204)

    game = await load_game(app_state, gameId)
    if game is None:
        # The game disappeared while the worker was thinking; this work can no
        # longer be applied, but it is not an engine/variant failure.
        app_state.fishnet_works.pop(work_id, None)
        return web.Response(status=204)
    if TYPE_CHECKING:
        assert isinstance(game, Game)

    user = _fishnet_bot_player(app_state, game)
    reported_fen = data.get("move", {}).get("fen")

    # Allow the fishnet move only if the server-side move stack is still the one
    # used to create the work item.  Do not rely on the worker-reported FEN for
    # this guard: fairyfishnet may run several worker threads, while pyffish's
    # VariantPath is process-global. With per-work scoped variants.ini files,
    # another worker can change pyffish's VariantPath before the reporting worker
    # computes its echo FEN. The server's own move stack is the authoritative
    # stale-work check.
    if not _fishnet_work_matches_current_position(work, game):
        log.info(
            "DISCARD FISHNET move %s for stale work %s (work moves=%r, game moves=%r)",
            move,
            work_id,
            work.get("moves", ""),
            _game_move_stack_string(game),
        )
        app_state.fishnet_works.pop(work_id, None)
        response = await get_work(app_state, data)
        return response

    if reported_fen is not None and reported_fen != game.board.fen:
        log.warning(
            "Fishnet move %s for work %s reported FEN %r, but current server FEN is %r; "
            "applying because the server-side move stack still matches",
            move,
            work_id,
            reported_fen,
            game.board.fen,
        )

    try:
        async with game.move_lock:
            await play_move(app_state, user, game, move)
    except Exception:
        log.exception(
            "Fishnet move %s for work %s failed while being applied",
            move,
            work_id,
        )
        await _handle_invalid_fishnet_move(app_state, work_id, work, "play_move raised")
        return web.Response(status=204)

    if game.status == INVALIDMOVE:
        app_state.fishnet_works.pop(work_id, None)
        await _record_terminal_catalogued_ai_failure(app_state, work, INVALID_FISHNET_MOVE_REASON)
        return web.Response(status=204)

    app_state.fishnet_works.pop(work_id, None)
    await clear_catalogued_variant_ai_failures(app_state, str(work.get("variant") or ""))

    response = await get_work(app_state, data)
    return response


@csrf_exempt
async def fishnet_abort(request: web.Request) -> web.Response:
    work_id = request.match_info["workId"]
    data_obj, error_status = await _read_fishnet_json(request)
    if data_obj is None:
        return web.Response(status=error_status or 400)
    # Fishnet payloads come from our own worker implementation, so we keep this boundary trusted.
    data = cast(FishnetAbortPayload, data_obj)

    app_state = get_app_state(request.app)
    key = data["fishnet"]["apikey"]

    if key not in FISHNET_KEYS:
        return web.Response(status=404)
    worker = FISHNET_KEYS[key]
    abort_reason = _abort_reason(data)
    app_state.fishnet_worker_last_seen[key] = monotonic()

    app_state.fishnet_monitor[worker].append(
        "%s %s %s (%s)" % (datetime.now(UTC), work_id, "abort", abort_reason)
    )

    # remove fishnet client
    try:
        app_state.workers.remove(data["fishnet"]["apikey"])
    except KeyError:
        log.debug("Worker %s was already removed", worker)
    app_state.fishnet_worker_last_seen.pop(key, None)
    capability_last_seen = _fishnet_capability_last_seen(app_state)
    for capability in tuple(capability_last_seen):
        if capability[0] == key:
            capability_last_seen.pop(capability, None)
    _sync_alice_stockfish_online(app_state)
    no_workers = len(app_state.workers) == 0

    work = app_state.fishnet_works.get(work_id)
    if work is None:
        if no_workers:
            app_state.users["Fairy-Stockfish"].online = False
        return web.Response(status=204)

    work["abort_count"] = work.get("abort_count", 0) + 1
    work["last_abort_reason"] = abort_reason
    if abort_reason in ENGINE_FAILURE_REASONS:
        work["engine_failure_count"] = _engine_failure_count(work) + 1
        if abort_reason == ENGINE_CRASH_REASON:
            work["engine_crash_count"] = work.get("engine_crash_count", 0) + 1

    if _is_terminal_abort(work, abort_reason):
        await _drop_terminal_work_failure(app_state, work_id, work, abort_reason)
        if no_workers:
            app_state.users["Fairy-Stockfish"].online = False
        return web.Response(status=204)

    # Re-schedule the job with correct priority.
    work["time"] = monotonic()
    app_state.fishnet_queue.put_nowait((_work_priority(work), work_id))

    if no_workers:
        app_state.users["Fairy-Stockfish"].online = False
        # TODO: msg to work user

    return web.Response(status=204)


async def fishnet_validate_key(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in FISHNET_KEYS:
        return web.Response(status=404)

    return web.Response()


async def fishnet_monitor(request: web.Request) -> web.Response:
    app_state = get_app_state(request.app)
    workers = {
        worker + " v" + app_state.fishnet_versions[worker]: list(app_state.fishnet_monitor[worker])
        for worker in app_state.fishnet_monitor
        if app_state.fishnet_monitor[worker]
    }
    return json_response(workers)
