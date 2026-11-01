from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pyffish as sf
from catalogued.variants import ensure_catalogued_variant_from_game_doc
from compress import R2C
from const import CASUAL, INVALIDMOVE, STARTED
from convert import mirror5, mirror9, zero2grand
from fairy import FairyBoard
from fairy.jieqi import make_initial_mapping
from pymongo import AsyncMongoClient
from settings import MONGO_DB_NAME, MONGO_HOST
from variants import C2V, GRANDS, TWO_BOARD_VARIANT_CODES, get_server_variant


class UnsafeRepair(RuntimeError):
    """A suspicious game cannot be repaired without guessing."""


class _CataloguedVariantState:
    def __init__(self) -> None:
        self.catalogued_variants: dict[str, dict[str, Any]] = {}


CATALOGUED_VARIANT_STATE = _CataloguedVariantState()

# Commit 01513577d ("Faster server restart") introduced background loading of
# correspondence games at this instant. Use it as the requested default game
# creation boundary while allowing explicit broader historical scans.
BACKGROUND_CORRESPONDENCE_LOAD_INTRODUCED_AT = datetime(2026, 6, 23, 10, 13, 35, tzinfo=UTC)


@dataclass(frozen=True)
class RepairPlan:
    game_id: str
    original_moves: list[str]
    repaired_moves: list[str]
    removed_indexes: tuple[int, ...]
    original_fen: str
    original_status: int
    set_fields: dict[str, Any]
    can_reopen_correspondence: bool


def _has_adjacent_duplicate(moves: list[str]) -> bool:
    return any(move == moves[index - 1] for index, move in enumerate(moves[1:], start=1))


def _ensure_variant_available(doc: dict[str, Any]) -> None:
    code = str(doc.get("v") or "")
    if code in C2V:
        return
    ini = doc.get("vini")
    if not isinstance(ini, str) or not ini:
        raise UnsafeRepair(f"unknown variant code {code!r} without inline variant rules")
    sf.load_variant_config(ini)
    ensure_catalogued_variant_from_game_doc(CATALOGUED_VARIANT_STATE, doc)


def _decode_position(doc: dict[str, Any]) -> tuple[str, str, bool, list[str]]:
    _ensure_variant_available(doc)
    variant = C2V[str(doc["v"])]
    chess960 = bool(doc.get("z"))
    initial_fen = doc.get("if")

    usi_format = variant.endswith("shogi") and doc.get("uci") is None
    if usi_format and isinstance(initial_fen, str):
        parts = initial_fen.split()
        if len(parts) > 3 and parts[1] in "wb":
            pockets = f"[{parts[2]}]" if parts[2] not in "-0" else ""
            initial_fen = (
                parts[0] + pockets + (" w" if parts[1] == "b" else " b") + " 0 " + parts[3]
            )
        else:
            initial_fen = parts[0] + (" w" if parts[1] == "b" else " b") + " 0"

    server_variant = get_server_variant(variant, chess960)
    moves = [server_variant.move_decoding(move) for move in doc["m"]]
    if usi_format and variant in ("shogi", "shoshogi"):
        moves = [mirror9(move) for move in moves]
    elif usi_format and variant in ("minishogi", "kyotoshogi"):
        moves = [mirror5(move) for move in moves]
    elif variant in GRANDS:
        moves = [zero2grand(move) for move in moves]

    return variant, initial_fen or "", chess960, moves


def _repair_parallel_array(
    doc: dict[str, Any],
    field: str,
    *,
    original_length: int,
    repaired_length: int,
    removed_indexes: tuple[int, ...],
    offset: int = 0,
) -> list[Any] | None:
    values = doc.get(field)
    if values is None:
        return None
    if not isinstance(values, list):
        raise UnsafeRepair(f"{field} is not an array")
    if not values:
        return values

    expected_original = original_length + offset
    expected_repaired = repaired_length + offset
    if len(values) == expected_repaired:
        return values
    if len(values) != expected_original:
        raise UnsafeRepair(
            f"{field} length {len(values)} matches neither original history "
            f"{expected_original} nor repaired history {expected_repaired}"
        )

    removed = {index + offset for index in removed_indexes}
    return [value for index, value in enumerate(values) if index not in removed]


def build_repair_plan(doc: dict[str, Any]) -> RepairPlan | None:
    if int(doc.get("y", -1)) != int(CASUAL):
        return None
    users = doc.get("us")
    if not isinstance(users, list) or len(users) != 2:
        return None
    if doc.get("v") in TWO_BOARD_VARIANT_CODES:
        return None

    raw_moves = doc.get("m")
    if not isinstance(raw_moves, list) or len(raw_moves) < 2:
        return None
    if not all(isinstance(move, str) for move in raw_moves):
        raise UnsafeRepair("move history contains a non-string value")
    if not _has_adjacent_duplicate(raw_moves):
        return None
    if doc.get("mct"):
        raise UnsafeRepair("manual-count intervals require game-specific reconstruction")

    variant, initial_fen, chess960, decoded_moves = _decode_position(doc)
    server_variant = get_server_variant(variant, chess960)
    board = FairyBoard(
        variant,
        initial_fen,
        chess960,
        show_promoted=server_variant.show_promoted,
        legal_moves_need_history=server_variant.legal_moves_need_history,
    )
    if variant == "jieqi":
        black_pieces = doc.get("bj")
        white_pieces = doc.get("wj")
        if not isinstance(black_pieces, list) or not isinstance(white_pieces, list):
            raise UnsafeRepair("Jieqi history is missing its covered-piece mapping")
        board.jieqi_covered_pieces = make_initial_mapping(black_pieces, white_pieces)

    removed_indexes: list[int] = []
    for index, move in enumerate(decoded_moves):
        if not board.push(move, raise_on_error=False):
            if index == 0 or raw_moves[index] != raw_moves[index - 1]:
                raise UnsafeRepair(
                    f"first invalid move is not an adjacent duplicate at ply {index + 1}: {move}"
                )
            removed_indexes.append(index)

    if not removed_indexes:
        return None
    if board.fen != doc.get("f"):
        raise UnsafeRepair("repaired history does not reproduce the stored final FEN")

    removed_tuple = tuple(removed_indexes)
    removed_set = set(removed_tuple)
    repaired_moves = [move for index, move in enumerate(raw_moves) if index not in removed_set]
    set_fields: dict[str, Any] = {
        "m": repaired_moves,
        "p": len(repaired_moves),
    }

    raw_byost = doc.get("byost")
    if isinstance(raw_byost, list) and len(raw_byost) == len(repaired_moves) and raw_byost:
        # This shape means a later move reached the board but failed before its
        # byoyomi snapshot was appended (the HEbciizV cascade). Keeping the
        # existing array is safe only when the affected tail did not change.
        tail_start = max(0, min(removed_tuple) - 1)
        if any(state != raw_byost[tail_start] for state in raw_byost[tail_start:]):
            raise UnsafeRepair(
                "byost omits a post-duplicate snapshot and its affected states differ"
            )

    repaired_byost = _repair_parallel_array(
        doc,
        "byost",
        original_length=len(raw_moves),
        repaired_length=len(repaired_moves),
        removed_indexes=removed_tuple,
    )
    if repaired_byost is not None:
        set_fields["byost"] = repaired_byost

    repaired_analysis = _repair_parallel_array(
        doc,
        "a",
        original_length=len(raw_moves),
        repaired_length=len(repaired_moves),
        removed_indexes=removed_tuple,
        offset=1,
    )
    if repaired_analysis is not None:
        set_fields["a"] = repaired_analysis

    status = int(doc.get("s", STARTED))
    can_reopen_correspondence = (
        doc.get("c") is True
        and status == int(INVALIDMOVE)
        and not any(doc.get(field) for field in ("tid", "aid", "sid"))
    )
    return RepairPlan(
        game_id=str(doc["_id"]),
        original_moves=raw_moves,
        repaired_moves=repaired_moves,
        removed_indexes=removed_tuple,
        original_fen=str(doc["f"]),
        original_status=status,
        set_fields=set_fields,
        can_reopen_correspondence=can_reopen_correspondence,
    )


async def apply_repair_plan(
    collection: Any,
    plan: RepairPlan,
    *,
    reopen_correspondence: bool = False,
) -> bool:
    set_fields = dict(plan.set_fields)
    if reopen_correspondence:
        if not plan.can_reopen_correspondence:
            raise UnsafeRepair(f"game {plan.game_id} is not safe to reopen")
        set_fields.update({"s": int(STARTED), "r": R2C["*"]})

    result = await collection.update_one(
        {
            "_id": plan.game_id,
            "y": int(CASUAL),
            "m": plan.original_moves,
            "f": plan.original_fen,
            "s": plan.original_status,
        },
        {"$set": set_fields},
    )
    return result.modified_count == 1


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 date/time: {value!r}") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("date/time must include a timezone, such as Z or +02:00")
    return parsed.astimezone(UTC)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair casual single-board games containing an accidentally duplicated move. "
            "A repair is accepted only when skipping engine-rejected adjacent duplicates "
            "reproduces the stored final FEN. Dry-run by default. Run with PYTHONPATH=server."
        )
    )
    parser.add_argument("--mongo-host", default=MONGO_HOST)
    parser.add_argument("--mongo-db", default=MONGO_DB_NAME)
    date_scope = parser.add_mutually_exclusive_group()
    date_scope.add_argument(
        "--started-after",
        type=_parse_datetime,
        default=BACKGROUND_CORRESPONDENCE_LOAD_INTRODUCED_AT,
        metavar="ISO_DATETIME",
        help=(
            "Only scan games created at or after this timezone-aware ISO-8601 date/time. "
            "Defaults to 2026-06-23T10:13:35Z, when background correspondence loading "
            "was introduced."
        ),
    )
    date_scope.add_argument(
        "--all-dates",
        action="store_true",
        help="Disable the default introduction-date boundary and scan all historical games.",
    )
    parser.add_argument(
        "--game-id",
        action="append",
        default=[],
        help="Only inspect this game id; repeat for multiple games. The default scans all casual games.",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Maximum documents to scan; 0 is unlimited."
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=250_000,
        help="Print progress every N scanned games; 0 disables progress output.",
    )
    parser.add_argument("--apply", action="store_true", help="Write safe repairs to MongoDB.")
    parser.add_argument(
        "--reopen-correspondence-invalid",
        action="store_true",
        help=(
            "With --apply, reopen repaired correspondence games whose only terminal status "
            "is INVALIDMOVE. Tournament, arrangement, and simul games are never reopened."
        ),
    )
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be >= 0")
    if args.progress_every < 0:
        parser.error("--progress-every must be >= 0")
    if args.reopen_correspondence_invalid and not args.apply:
        parser.error("--reopen-correspondence-invalid requires --apply")
    return args


def build_game_query(args: argparse.Namespace) -> dict[str, Any]:
    query: dict[str, Any] = {
        "y": int(CASUAL),
        "us.2": {"$exists": False},
        "m.1": {"$exists": True},
    }
    if not args.all_dates:
        query["d"] = {"$gte": args.started_after}
    if args.game_id:
        query["_id"] = {"$in": list(dict.fromkeys(args.game_id))}
    return query


async def main() -> None:
    args = parse_args()
    client = AsyncMongoClient(args.mongo_host, tz_aware=True)
    collection = client[args.mongo_db].game

    query = build_game_query(args)

    scanned = 0
    suspicious = 0
    candidates = 0
    modified = 0
    unsafe = 0

    try:
        if args.all_dates:
            print("SCOPE dates=all", flush=True)
        else:
            print(
                f"SCOPE started_after={args.started_after.isoformat().replace('+00:00', 'Z')}",
                flush=True,
            )
        cursor = collection.find(query).sort("d", 1)
        if not args.game_id:
            cursor = cursor.hint("d_id_desc")
        if args.limit:
            cursor = cursor.limit(args.limit)

        async for doc in cursor:
            scanned += 1
            if args.progress_every and scanned % args.progress_every == 0:
                print(
                    "PROGRESS scanned=%d suspicious=%d candidates=%d unsafe=%d"
                    % (scanned, suspicious, candidates, unsafe),
                    flush=True,
                )
            raw_moves = doc.get("m")
            if not isinstance(raw_moves, list) or not _has_adjacent_duplicate(raw_moves):
                continue
            suspicious += 1

            try:
                plan = build_repair_plan(doc)
            except (KeyError, RuntimeError, SystemError, TypeError, ValueError) as exc:
                unsafe += 1
                print(f"UNSAFE id={doc.get('_id')} reason={exc}", flush=True)
                continue
            if plan is None:
                continue

            candidates += 1
            removed_plies = ",".join(str(index + 1) for index in plan.removed_indexes)
            reopen = args.reopen_correspondence_invalid and plan.can_reopen_correspondence
            print(
                "CANDIDATE id=%s removed_plies=%s moves=%d->%d status=%s reopen=%s"
                % (
                    plan.game_id,
                    removed_plies,
                    len(plan.original_moves),
                    len(plan.repaired_moves),
                    plan.original_status,
                    reopen,
                ),
                flush=True,
            )

            if not args.apply:
                continue

            if await apply_repair_plan(
                collection,
                plan,
                reopen_correspondence=reopen,
            ):
                modified += 1
            else:
                print(
                    f"STALE id={plan.game_id} changed after inspection; no repair applied",
                    flush=True,
                )

        print(
            "SUMMARY mode=%s scanned=%d suspicious=%d candidates=%d unsafe=%d modified=%d"
            % (
                "apply" if args.apply else "dry-run",
                scanned,
                suspicious,
                candidates,
                unsafe,
                modified,
            ),
            flush=True,
        )
        if not args.apply:
            print("No changes written. Review candidates, then rerun with --apply.", flush=True)
        elif modified:
            print(
                "Restart every running server process so repaired games are reloaded from MongoDB.",
                flush=True,
            )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
