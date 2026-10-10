from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, TypedDict

import aiohttp_session
import pymongo
from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError
from aiohttp_sse import sse_response
from aiohttp_swagger3 import swagger_doc
from catalogued_variants import (
    CATALOGUED_VARIANT_COLLECTION,
    register_historical_catalogued_variant_doc,
)
from compress import C2R, decode_move_standard
from const import (
    CATEGORY_VARIANT_SETS,
    CLAIM,
    DARK_FEN,
    GAME_CATEGORY_ALL,
    INVALIDMOVE,
    MATE,
    ONGOING_GAME_QUEUE_MAXSIZE,
    SSE_SNAPSHOT_QUEUE_MAXSIZE,
    STARTED,
    SWISS,
    VARIANTEND,
)
from convert import zero2grand
from json_utils import json_dumps, json_response
from preferences import effective_game_category
from pychess_global_app_state_utils import get_app_state
from pymongo.errors import BulkWriteError, ExecutionTimeout
from seek import BOT_CHALLENGE_DECLINED
from settings import ADMINS
from sse_utils import consume_sse_queue, enqueue_sse_payload
from tournament.tournaments import get_tournament_name, load_tournament
from utils import pgn
from variants import C2V, GRANDS, VARIANTS, get_server_variant, is_catalogued_variant

log = logging.getLogger(__name__)

GAME_PAGE_SIZE = 12
GAME_SEARCH_MAX_TIME_MS = 10_000
_seen_discontinued_variants: set[str] = set()
EXPORT_FAILED_SAMPLE_LIMIT = 5
USER_GAMES_FILTERS = ("all", "win", "loss", "rated", "playing", "import", "me", "perf")

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState


class VariantCountId(TypedDict):
    p: str
    v: str
    z: int


class VariantCountDoc(TypedDict):
    _id: VariantCountId
    c: int


GameDoc = TypedDict(
    "GameDoc",
    {
        "_id": str,
        "v": str,
        "vini": str,
        "vd": str,
        "r": str,
        "z": int,
        "us": list[str],
        "m": list[str] | str,
        "o": list[int],
        "if": str | None,
        "f": str,
        "p": int,
        "s": int,
        "d": datetime,
        "tid": str,
        "y": int,
        "by": str,
        "x": int,
        "wt": str,
        "bt": str,
        "wtB": str,
        "btB": str,
        "lm": str,
        "lmB": str,
        "tn": str,
        "initialFen": str | None,
    },
    total=False,
)


def duplicate_key_only_bulk_write_error(error: BulkWriteError) -> bool:
    details = error.details
    write_errors = details.get("writeErrors", []) if isinstance(details, dict) else []
    write_concern_errors = (
        details.get("writeConcernErrors", []) if isinstance(details, dict) else []
    )
    return (
        bool(write_errors)
        and not write_concern_errors
        and all(item.get("code") == 11000 for item in write_errors)
    )


async def persist_variant_count_docs(
    app_state: PychessGlobalAppState, humans: bool, docs: list[VariantCountDoc]
) -> None:
    if not docs:
        return

    collection = app_state.db.stats_humans if humans else app_state.db.stats
    try:
        await collection.insert_many(docs, ordered=False)
    except BulkWriteError as error:
        if not duplicate_key_only_bulk_write_error(error):
            raise
        periods = sorted({doc["_id"]["p"] for doc in docs})
        log.info(
            "Ignoring duplicate monthly variant stats write for humans=%s periods=%s",
            humans,
            periods,
        )


async def variant_counts_aggregation(
    app_state: PychessGlobalAppState, humans: bool, query_period: str | None = None
) -> list[VariantCountDoc]:
    pipeline: list[dict[str, object]] = [
        {
            "$group": {
                "_id": {
                    "p": {"$dateToString": {"format": "%Y%m", "date": "$d"}},
                    "v": "$v",
                    "z": "$z",
                },
                "c": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    match_cond: dict[str, object] = {}

    # Catalogued/user-defined games carry their inline Fairy-Stockfish config.
    # They are not first-class site variants and must not enter the monthly
    # built-in variant series.
    match_cond["vini"] = {"$exists": False}

    if query_period is not None:
        year, month = int(query_period[:4]), int(query_period[4:])
        match_cond["$expr"] = {
            "$and": [
                {"$eq": [{"$month": "$d"}, month]},
                {"$eq": [{"$year": "$d"}, year]},
            ]
        }

    if humans:
        match_cond["$and"] = [
            {"us.0": {"$nin": ["Fairy-Stockfish", "Alice-Stockfish", "Random-Mover"]}},
            {"us.1": {"$nin": ["Fairy-Stockfish", "Alice-Stockfish", "Random-Mover"]}},
        ]

    if len(match_cond) > 0:
        pipeline.insert(0, {"$match": match_cond})

    cursor = await app_state.db.game.aggregate(pipeline)

    docs: list[VariantCountDoc] = []

    cur_period = datetime.now(UTC).isoformat()[:7].replace("-", "")

    async for doc in cursor:
        # print(doc)
        period = doc["_id"]["p"]
        if period < "201907":
            continue
        # skip current period
        if period == cur_period:
            break

        docs.append(doc)

    await persist_variant_count_docs(app_state, humans, docs)

    return docs


def variant_counts_from_docs(
    variant_counts: dict[str, list[int]], docs: list[VariantCountDoc]
) -> None:
    period = ""
    for doc in docs:
        # print(doc)
        variant_code = doc["_id"]["v"]
        variant_name = C2V.get(variant_code)
        variant = (
            variant_code
            if variant_name is None
            else variant_name
            + ("960" if doc["_id"].get("z", 0) and not is_catalogued_variant(variant_name) else "")
        )
        if variant not in variant_counts:
            if variant not in _seen_discontinued_variants:
                _seen_discontinued_variants.add(variant)
                log.info(
                    "Ignoring discontinued or user-defined variant %s in historical stats",
                    variant,
                )
            continue

        if doc["_id"]["p"] != period:
            period = doc["_id"]["p"]
            for series_variant in VARIANTS:
                variant_counts[series_variant].append(0)

        variant_counts[variant][-1] = doc["c"]


async def get_variant_stats(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    humans = "/humans" in request.path
    stats = app_state.stats_humans if humans else app_state.stats

    first_day_of_current_month = date.today().replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)

    cur_period = last_day_of_previous_month.isoformat()[:7].replace("-", "")
    # print(cur_period)

    series: list[dict[str, object]]
    if cur_period in stats:
        series = stats[cur_period]
    else:
        variant_counts: dict[str, list[int]] = {variant: [] for variant in VARIANTS}
        if humans:
            n = await app_state.db.stats_humans.count_documents({})
        else:
            n = await app_state.db.stats.count_documents({})

        if n > 0:
            # We already have some stats
            if humans:
                cursor = app_state.db.stats_humans.find()
            else:
                cursor = app_state.db.stats.find()
            cursor.sort("_id", pymongo.ASCENDING)
            docs: list[VariantCountDoc] = await cursor.to_list(n)
            variant_counts_from_docs(variant_counts, docs)

            # If cur_period is missing from the stats we call the aggregation
            if docs[-1]["_id"]["p"] != cur_period:
                docs = await variant_counts_aggregation(app_state, humans, cur_period)
                variant_counts_from_docs(variant_counts, docs)
        else:
            # Call the aggregation on the whole games collection
            docs = await variant_counts_aggregation(app_state, humans)
            variant_counts_from_docs(variant_counts, docs)

        series = [{"name": variant, "data": variant_counts[variant]} for variant in VARIANTS]

        stats[cur_period] = series

    return json_response(series)


async def get_tournament_games(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    tournamentId = request.match_info.get("tournamentId")

    if tournamentId is not None and tournamentId not in app_state.tournaments:
        await asyncio.sleep(3)
        return json_response({})

    cursor = app_state.db.game.find({"tid": tournamentId})
    game_doc_list: list[dict[str, object] | GameDoc] = []

    if TYPE_CHECKING:
        assert tournamentId is not None
    tournament = app_state.tournaments[tournamentId]
    variant = tournament.variant
    decode_method = tournament.server_variant.move_decoding

    doc: GameDoc
    async for doc in cursor:
        doc["v"] = C2V[doc["v"]]
        doc["r"] = C2R[doc["r"]]
        game_doc_list.append(
            {
                "id": doc["_id"],
                "variant": variant,
                "is960": doc.get("z", 0),
                "users": doc["us"],
                "result": doc["r"],
                "fen": doc.get("if"),
                "moves": [*map(decode_method, doc["m"])],
            }
        )

    return json_response(game_doc_list)


def _parse_positive_int_query_param(request: web.Request, name: str) -> int | None:
    raw_value = request.rel_url.query.get(name)
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except ValueError as error:
        raise web.HTTPBadRequest(
            text=f"Query parameter '{name}' must be a positive integer."
        ) from error
    if value <= 0:
        raise web.HTTPBadRequest(text=f"Query parameter '{name}' must be a positive integer.")
    return value


def _resolve_user_games_filter_and_variant(
    request: web.Request,
) -> tuple[str, str | None, list[str]]:
    path_parts: list[str] = request.path.split("/")
    query_filter = request.rel_url.query.get("filter")

    if query_filter is not None:
        selected_filter = query_filter.lower()
        if selected_filter not in USER_GAMES_FILTERS:
            raise web.HTTPBadRequest(
                text="Query parameter 'filter' must be one of: all, win, loss, rated, playing, import, me, perf."
            )
    else:
        selected_filter = "all"
        for candidate in USER_GAMES_FILTERS:
            if candidate != "all" and candidate in path_parts:
                selected_filter = candidate
                break

    selected_variant = request.rel_url.query.get("variant")
    if selected_variant is None and "perf" in path_parts:
        selected_variant = request.path[request.path.rfind("/") + 1 :]

    return selected_filter, selected_variant, path_parts


def _build_user_games_filter_cond(
    profile_id: str,
    session_user: str | None,
    selected_filter: str,
    selected_variant: str | None,
    level: str | None,
) -> dict[str, object] | None:
    filter_cond: dict[str, object] = {}

    if selected_filter == "win":
        filter_cond["$or"] = [
            {"r": "a", "us.0": profile_id},
            {"r": "b", "us.1": profile_id},
        ]
    elif selected_filter == "loss":
        if level is not None:
            filter_cond["$and"] = [
                {"$or": [{"r": "a", "us.1": profile_id}, {"r": "b", "us.0": profile_id}]},
                {"x": int(level)},
                {"$or": [{"if": None}, {"v": "j"}]},  # Janggi games always have initial FEN!
                {
                    "$or": [
                        {"s": MATE},
                        {"s": VARIANTEND},
                        {"s": INVALIDMOVE},
                        {"s": CLAIM},
                    ]
                },
            ]
        else:
            filter_cond["$or"] = [
                {"r": "a", "us.1": profile_id},
                {"r": "b", "us.0": profile_id},
            ]
    elif selected_filter == "rated":
        filter_cond["$or"] = [{"y": 1, "us.1": profile_id}, {"y": 1, "us.0": profile_id}]
    elif selected_filter == "playing":
        filter_cond["$and"] = [
            {"$or": [{"c": True, "us.1": profile_id}, {"c": True, "us.0": profile_id}]},
            {"s": STARTED},
        ]
    elif selected_filter == "import":
        filter_cond["by"] = profile_id
        filter_cond["y"] = 2
    elif selected_filter == "perf":
        if selected_variant not in VARIANTS:
            return None

        variant960 = selected_variant.endswith("960")
        uci_variant = selected_variant[:-3] if variant960 else selected_variant

        v = get_server_variant(uci_variant, variant960)
        z = 1 if variant960 else 0

        filter_cond["$or"] = [
            {"v": v.code, "z": z, "us.1": profile_id},
            {"v": v.code, "z": z, "us.0": profile_id},
        ]
    elif selected_filter == "me":
        filter_cond["$or"] = [
            {"us.0": session_user, "us.1": profile_id},
            {"us.1": session_user, "us.0": profile_id},
        ]
    else:
        filter_cond["us"] = profile_id

    if selected_filter != "import":
        filter_cond = {
            "$and": [
                filter_cond,
                {"y": {"$ne": 2}},
            ]
        }

    return filter_cond


def _apply_category_filter(
    filter_cond: dict[str, object], user: object
) -> dict[str, object] | None:
    if getattr(user, "game_category", "all") == "all":
        return filter_cond

    allowed_codes = getattr(user, "category_variant_codes", set())
    if not allowed_codes:
        return None
    return {"$and": [filter_cond, {"v": {"$in": list(allowed_codes)}}]}


async def _resolve_user_game_variant(app_state: PychessGlobalAppState, doc: GameDoc) -> str | None:
    code = doc["v"]
    variant = C2V.get(code)
    if variant is not None:
        return variant

    # Archived variants are absent from the live catalogue. Restore historical
    # metadata without making them available for new games.
    historical_doc = (
        doc
        if doc.get("vini")
        else await app_state.db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": code})
    )
    if historical_doc is not None:
        try:
            register_historical_catalogued_variant_doc(historical_doc)
        except Exception:
            log.exception("Failed to restore variant %r for user game %s", code, doc["_id"])
        else:
            variant = C2V.get(code)
            if variant is not None:
                return variant

    log.error("get_user_games() KeyError. Unknown variant %r", code)
    return None


@swagger_doc("docs/api/get_user_games.yaml")
async def get_user_games(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    profileId = request.match_info.get("profileId")

    if profileId is not None:
        public_profile = await app_state.public_users.get_profile(profileId)
        if public_profile is None:
            await asyncio.sleep(3)
            return json_response({})

    # Who made the request?
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user)
    if user.anon:
        await asyncio.sleep(3)
        return json_response({})
    if TYPE_CHECKING:
        assert profileId is not None

    selected_filter, selected_variant, path_parts = _resolve_user_games_filter_and_variant(request)

    # print("URL", request.rel_url)
    level = request.rel_url.query.get("x")
    filter_cond = _build_user_games_filter_cond(
        profile_id=profileId,
        session_user=session_user,
        selected_filter=selected_filter,
        selected_variant=selected_variant,
        level=level,
    )
    if filter_cond is None:
        return json_response([])

    # produce UCI move list for puzzle generator
    uci_moves: bool = "json" in path_parts
    filter_cond = _apply_category_filter(filter_cond, user)
    if filter_cond is None:
        return json_response([])

    page_num = request.rel_url.query.get("p", 0)
    latest_games = _parse_positive_int_query_param(request, "max")

    game_doc_list: list[dict[str, object] | GameDoc] = []
    if profileId is not None:
        # print("FILTER:", filter_cond)
        cursor = app_state.db.game.find(filter_cond)
        if uci_moves or latest_games is not None:
            cursor.sort("d", -1)
            if latest_games is not None:
                cursor.limit(latest_games)
        else:
            cursor.sort("d", -1).skip(int(page_num) * GAME_PAGE_SIZE).limit(GAME_PAGE_SIZE)
        doc: GameDoc
        async for doc in cursor:
            variant = await _resolve_user_game_variant(app_state, doc)
            if variant is None:
                continue
            doc["v"] = variant

            doc["r"] = C2R[doc["r"]]
            doc["wt"] = (
                app_state.users[doc["us"][0]].title if doc["us"][0] in app_state.users else ""
            )
            doc["bt"] = (
                app_state.users[doc["us"][1]].title if doc["us"][1] in app_state.users else ""
            )

            if len(doc["us"]) > 2:
                doc["wtB"] = (
                    app_state.users[doc["us"][2]].title if doc["us"][2] in app_state.users else ""
                )
                doc["btB"] = (
                    app_state.users[doc["us"][3]].title if doc["us"][3] in app_state.users else ""
                )

            server_variant = get_server_variant(variant, bool(doc.get("z", 0)))
            decode_method = server_variant.move_decoding
            if server_variant.two_boards:
                mA = [m for idx, m in enumerate(doc["m"]) if "o" in doc and doc["o"][idx] == 0]
                mB = [m for idx, m in enumerate(doc["m"]) if "o" in doc and doc["o"][idx] == 1]
                doc["lm"] = decode_move_standard(mA[-1]) if len(mA) > 0 else ""
                doc["lmB"] = decode_move_standard(mB[-1]) if len(mB) > 0 else ""
            else:
                doc["lm"] = decode_method(doc["m"][-1]) if len(doc["m"]) > 0 else ""

            if variant in GRANDS and doc["lm"] != "":
                doc["lm"] = zero2grand(doc["lm"])

            tournament_id = doc.get("tid")
            if tournament_id is not None:
                doc["tn"] = await get_tournament_name(request, tournament_id)

            doc["initialFen"] = doc.get("if", "")

            if uci_moves:
                game_doc_list.append(
                    {
                        "id": doc["_id"],
                        "variant": variant,
                        "is960": doc.get("z", 0),
                        "users": doc["us"],
                        "result": doc["r"],
                        "fen": doc.get("f"),
                        "moves": [*map(decode_method, doc["m"])],
                    }
                )
            else:
                if doc["s"] <= STARTED and variant == "fogofwar":
                    doc["f"] = DARK_FEN
                    doc["lm"] = ""
                    doc["m"] = ""

                game_doc_list.append(doc)

    return json_response(game_doc_list)


async def cancel_invite(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    gameId = request.match_info.get("gameId")
    if TYPE_CHECKING:
        assert gameId is not None

    invite = app_state.invites.pop(gameId, None)
    if invite is not None:
        seek_id = invite.id
        seek = app_state.seeks.pop(seek_id, None)
        if seek is not None:
            seek.creator.seeks.pop(seek_id, None)

    return web.HTTPFound("/")


def invite_resolution_snapshot(app_state: PychessGlobalAppState, game_id: str) -> str | None:
    """Return invite state that may have changed before the browser subscribed."""
    if game_id in app_state.games:
        return json_dumps({"gameId": game_id, "accept": True})

    seek = app_state.invites.get(game_id)
    if (
        seek is not None
        and seek.is_bot_challenge
        and seek.bot_challenge_status == BOT_CHALLENGE_DECLINED
    ):
        return json_dumps(
            {
                "gameId": game_id,
                "accept": False,
                "declineReason": seek.bot_challenge_decline_reason or "",
            }
        )

    return None


async def subscribe_invites(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    gameId = request.match_info.get("gameId")
    if TYPE_CHECKING:
        assert gameId is not None

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SSE_SNAPSHOT_QUEUE_MAXSIZE)
    if gameId not in app_state.invite_channels:
        app_state.invite_channels[gameId] = set()
    app_state.invite_channels[gameId].add(queue)

    snapshot = invite_resolution_snapshot(app_state, gameId)
    if snapshot is not None:
        enqueue_sse_payload(queue, snapshot, replace_pending=True)

    response: web.StreamResponse = web.Response(status=200)
    try:
        async with sse_response(request) as response:
            await consume_sse_queue(response, queue)
    except Exception:
        pass
    finally:
        channels = app_state.invite_channels.get(gameId)
        if channels is not None:
            channels.discard(queue)
            if len(channels) == 0:
                app_state.invite_channels.pop(gameId, None)
        queue.shutdown(immediate=True)
    return response


async def subscribe_games(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=ONGOING_GAME_QUEUE_MAXSIZE)
    app_state.game_channels.add(queue)
    response: web.StreamResponse = web.Response(status=200)
    try:
        async with sse_response(request) as response:
            await consume_sse_queue(response, queue)
    except Exception:
        pass
    finally:
        app_state.game_channels.discard(queue)
        queue.shutdown(immediate=True)
    return response


async def _get_games(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    games = app_state.games.values()
    variant = request.match_info.get("variant")
    if variant and variant.endswith("960") and not is_catalogued_variant(variant):
        chess960 = True
        variant = variant[:-3]
    else:
        chess960 = False
    allowed_variants = None
    if variant is None:
        session = await aiohttp_session.get_session(request)
        session_user = session.get("user_name")
        user = None
        if isinstance(session_user, str):
            if session_user in app_state.users:
                user = app_state.users[session_user]
            else:
                user = await app_state.users.get(session_user)
        game_category = effective_game_category(session, user)
        if game_category != GAME_CATEGORY_ALL:
            allowed_variants = CATEGORY_VARIANT_SETS[game_category]
    return json_response(
        [
            {
                "gameId": game.id,
                "variant": game.variant,
                "fen": DARK_FEN if game.variant == "fogofwar" else game.preview_fen,
                "lastMove": "" if game.variant == "fogofwar" else game.lastmove,
                "tp": game.turn_player,
                "w": game.wplayer.username,
                "wTitle": game.wplayer.title,
                "b": game.bplayer.username,
                "bTitle": game.bplayer.title,
                "chess960": game.chess960,
                "base": game.base,
                "inc": game.inc,
                "byoyomi": game.byoyomi_period,
                "level": game.level,
                "day": game.base if game.corr else 0,
            }
            for game in games
            if game.status == STARTED
            and (
                (
                    game.variant == variant
                    and (is_catalogued_variant(variant) or game.chess960 == chess960)
                )
                if variant
                else True
            )
            and (
                get_server_variant(game.variant, game.chess960).server_name in allowed_variants
                if allowed_variants is not None
                else True
            )
        ][-20:]
    )


@swagger_doc("docs/api/get_games.yaml")
async def get_games(request: web.Request) -> web.StreamResponse:
    return await _get_games(request)


@swagger_doc("docs/api/get_games_by_variant.yaml")
async def get_games_by_variant(request: web.Request) -> web.StreamResponse:
    return await _get_games(request)


async def _stream_pgn_cursor(
    request: web.Request, cursor: object, *, disconnect_message: str
) -> web.StreamResponse:
    game_counter = 0
    failed = 0
    failed_games: list[str] = []

    response = web.StreamResponse()
    response.content_type = "text/pgn"
    await response.prepare(request)
    try:
        doc: GameDoc
        async for doc in cursor:
            game_counter += 1
            try:
                pgn_text = pgn(doc)
                if pgn_text is not None:
                    await response.write(pgn_text.encode())
                    await asyncio.sleep(0)
            except (ConnectionResetError, ClientConnectionResetError):
                log.debug("%s", disconnect_message)
                break
            except Exception:
                failed += 1
                if len(failed_games) < EXPORT_FAILED_SAMPLE_LIMIT:
                    failed_games.append(
                        "%s %s %s" % (doc["_id"], C2V[doc["v"]], doc["d"].strftime("%Y.%m.%d"))
                    )
                continue
        log.info("failed/all: %s/%s", failed, game_counter)
        if failed_games:
            log.info(
                "PGN export skipped invalid/legacy games: %s",
                "; ".join(failed_games),
            )
    except (ConnectionResetError, ClientConnectionResetError):
        log.debug("%s", disconnect_message)
    except Exception:
        log.exception("An unexpected error occurred: ")
    finally:
        await safe_write_eof(response)
    return response


@swagger_doc("docs/api/export_user_pgn.yaml")
async def export_user_pgn(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    profileId = request.match_info.get("profileId")
    if profileId is not None:
        public_profile = await app_state.public_users.get_profile(profileId)
        if public_profile is None:
            await asyncio.sleep(3)
            return web.Response(text="")
    if TYPE_CHECKING:
        assert profileId is not None

    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    requester = await app_state.users.get(session_user)
    if requester.anon:
        await asyncio.sleep(3)
        return web.Response(text="")
    if session_user != profileId and session_user not in ADMINS:
        raise web.HTTPForbidden(text="Users can only export their own games.")

    selected_filter, selected_variant, _path_parts = _resolve_user_games_filter_and_variant(request)
    level = request.rel_url.query.get("x")
    filter_cond = _build_user_games_filter_cond(
        profile_id=profileId,
        session_user=session_user,
        selected_filter=selected_filter,
        selected_variant=selected_variant,
        level=level,
    )
    if filter_cond is None:
        return web.Response(text="")

    filter_cond = _apply_category_filter(filter_cond, requester)
    if filter_cond is None:
        return web.Response(text="")

    latest_games = _parse_positive_int_query_param(request, "max")
    cursor = app_state.db.game.find(filter_cond).sort("d", -1)
    if latest_games is not None:
        cursor = cursor.limit(latest_games)

    return await _stream_pgn_cursor(
        request,
        cursor,
        disconnect_message="Client disconnected during user PGN export.",
    )


async def export_tournament_pgn(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    tournament_id = request.match_info.get("tournamentId")
    if tournament_id is None:
        return web.Response(text="")

    cursor = app_state.db.game.find({"tid": tournament_id})
    return await _stream_pgn_cursor(
        request,
        cursor,
        disconnect_message="Client disconnected during tournament PGN export.",
    )


async def export_monthly_pgn(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user not in ADMINS:
        return web.Response(text="")

    yearmonth = request.match_info.get("yearmonth")
    if yearmonth is None:
        return web.Response(text="")

    log.debug("yearmonth: %r %r", yearmonth[:4], yearmonth[4:])
    filter_cond = {
        "$and": [
            {"$expr": {"s": {"$gt": STARTED}}},  # prevent leaking ongoing fogofwar game info
            {"$expr": {"$eq": [{"$year": "$d"}, int(yearmonth[:4])]}},
            {"$expr": {"$eq": [{"$month": "$d"}, int(yearmonth[4:])]}},
        ]
    }
    cursor = app_state.db.game.find(filter_cond)
    return await _stream_pgn_cursor(
        request,
        cursor,
        disconnect_message="Client disconnected during monthly PGN export.",
    )


async def export_tournament_trf(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    tournament_id = request.match_info.get("tournamentId")
    if tournament_id is None:
        return web.Response(text="")

    tournament = await load_tournament(app_state, tournament_id)
    if tournament is None:
        await asyncio.sleep(3)
        return web.Response(text="")

    if tournament.system != SWISS:
        return web.Response(text="", status=400)

    try:
        from tournament.swiss import build_trf_export_text

        trf_text = build_trf_export_text(tournament)
    except Exception:
        log.exception("TRF export failed for tournament %s", tournament_id)
        return web.Response(text="", status=500)

    response = web.Response(text=trf_text, content_type="text/plain")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="pychess_tournament_{tournament_id}.trf"'
    )
    return response


async def safe_write_eof(response: web.StreamResponse) -> None:
    try:
        await response.write_eof()
    except (ConnectionResetError, ClientConnectionResetError):
        log.debug("Connection closed before PGN export EOF write.")


def _search_int(value: str | None, minimum: int = 0) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= minimum else None


async def _canonical_search_username(app_state: PychessGlobalAppState, raw_username: str) -> str:
    candidate = raw_username.strip().lstrip("@")
    if not candidate or app_state.db is None:
        return candidate

    user_doc = await app_state.db.user.find_one(
        {
            "$or": [
                {"_id": candidate},
                {
                    "username_lower": {
                        "$eq": candidate.lower(),
                        "$type": "string",
                    }
                },
            ]
        },
        projection={"_id": 1},
    )
    if user_doc is None:
        return candidate

    username = user_doc.get("_id")
    return username if isinstance(username, str) else candidate


async def _game_doc_for_list(request: web.Request, doc: GameDoc) -> GameDoc | None:
    app_state = get_app_state(request.app)
    try:
        variant = C2V[doc["v"]]
    except KeyError:
        log.error("game search: unknown variant code %r", doc.get("v"))
        return None
    doc["v"] = variant
    doc["r"] = C2R[doc["r"]]
    doc["wt"] = app_state.users[doc["us"][0]].title if doc["us"][0] in app_state.users else ""
    doc["bt"] = app_state.users[doc["us"][1]].title if doc["us"][1] in app_state.users else ""
    if len(doc["us"]) > 2:
        doc["wtB"] = app_state.users[doc["us"][2]].title if doc["us"][2] in app_state.users else ""
        doc["btB"] = app_state.users[doc["us"][3]].title if doc["us"][3] in app_state.users else ""

    server_variant = get_server_variant(variant, bool(doc.get("z", 0)))
    decode_method = server_variant.move_decoding
    if server_variant.two_boards:
        m_a = [m for idx, m in enumerate(doc["m"]) if "o" in doc and doc["o"][idx] == 0]
        m_b = [m for idx, m in enumerate(doc["m"]) if "o" in doc and doc["o"][idx] == 1]
        doc["lm"] = decode_move_standard(m_a[-1]) if m_a else ""
        doc["lmB"] = decode_move_standard(m_b[-1]) if m_b else ""
    else:
        doc["lm"] = decode_method(doc["m"][-1]) if doc["m"] else ""
    if variant in GRANDS and doc["lm"]:
        doc["lm"] = zero2grand(doc["lm"])
    tournament_id = doc.get("tid")
    if tournament_id is not None:
        doc["tn"] = await get_tournament_name(request, tournament_id)
    doc["initialFen"] = doc.get("if", "")
    if doc["s"] <= STARTED and variant == "fogofwar":
        doc["f"] = DARK_FEN
        doc["lm"] = ""
        doc["m"] = ""
    return doc


async def search_games(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    user = await app_state.users.get(session.get("user_name"))
    if user.anon:
        return json_response({"error": "Login required."}, status=401)

    query = request.rel_url.query
    page = min(_search_int(query.get("p")) or 0, 99)
    conditions: list[dict[str, object]] = []

    raw_players = [
        query.get("player1", "").strip().lstrip("@"),
        query.get("player2", "").strip().lstrip("@"),
    ]
    players: list[str] = []
    player_aliases: dict[str, str] = {}
    seen_players: set[str] = set()
    for raw_player in raw_players:
        if not raw_player:
            continue
        alias = raw_player.casefold()
        canonical = player_aliases.get(alias)
        if canonical is None:
            canonical = await _canonical_search_username(app_state, raw_player)
            player_aliases[alias] = canonical
            player_aliases[canonical.casefold()] = canonical
        canonical_key = canonical.casefold()
        if canonical_key not in seen_players:
            players.append(canonical)
            seen_players.add(canonical_key)

    tournament = query.get("tournament", "").strip()
    if len(players) == 1:
        conditions.append({"us": players[0]})
    elif len(players) == 2:
        conditions.append({"us": {"$all": players}})
    if tournament:
        conditions.append({"tid": tournament})

    player_roles: dict[str, str] = {}
    for role in ("white", "black", "winner", "loser"):
        requested = query.get(role, "").strip().lstrip("@")
        if not requested:
            player_roles[role] = ""
            continue
        canonical = player_aliases.get(requested.casefold())
        if canonical is None:
            return json_response(
                {
                    "error": (
                        "White, black, winner, and loser must be one of the two searched players."
                    )
                },
                status=400,
            )
        player_roles[role] = canonical
    if player_roles["white"]:
        conditions.append({"us.0": player_roles["white"]})
    if player_roles["black"]:
        conditions.append({"us.1": player_roles["black"]})
    if player_roles["winner"]:
        winner = player_roles["winner"]
        conditions.append(
            {
                "$or": [
                    {"r": "a", "$or": [{"us.0": winner}, {"us.3": winner}]},
                    {"r": "b", "$or": [{"us.1": winner}, {"us.2": winner}]},
                ]
            }
        )
    if player_roles["loser"]:
        loser = player_roles["loser"]
        conditions.append(
            {
                "$or": [
                    {"r": "a", "$or": [{"us.1": loser}, {"us.2": loser}]},
                    {"r": "b", "$or": [{"us.0": loser}, {"us.3": loser}]},
                ]
            }
        )

    variant_name = query.get("variant", "").strip()
    if variant_name.casefold() in {"", "all"}:
        variant_name = ""
    if variant_name:
        variant_code = next((code for code, name in C2V.items() if name == variant_name), None)
        if variant_code is None:
            return json_response({"error": "Unknown variant."}, status=400)
        conditions.append({"v": variant_code})

    result_value = query.get("result", "")
    result_codes = {"1-0": "a", "0-1": "b", "1/2-1/2": "c"}
    if result_value:
        if result_value not in result_codes:
            return json_response({"error": "Invalid result."}, status=400)
        conditions.append({"r": result_codes[result_value]})

    game_type = query.get("type", "")
    type_conditions = {
        "casual": {"y": 0, "c": {"$ne": True}},
        "rated": {"y": 1, "c": {"$ne": True}},
        "imported": {"y": 2},
        "correspondence": {"c": True},
    }
    if game_type:
        if game_type not in type_conditions:
            return json_response({"error": "Invalid game type."}, status=400)
        conditions.append(type_conditions[game_type])

    date_range: dict[str, datetime] = {}
    try:
        if query.get("from"):
            date_range["$gte"] = datetime.fromisoformat(query["from"]).replace(tzinfo=UTC)
        if query.get("to"):
            date_range["$lt"] = datetime.fromisoformat(query["to"]).replace(tzinfo=UTC) + timedelta(
                days=1
            )
    except ValueError:
        return json_response({"error": "Invalid date."}, status=400)
    if date_range:
        conditions.append({"d": date_range})

    min_moves = _search_int(query.get("minMoves"))
    max_moves = _search_int(query.get("maxMoves"))
    if (query.get("minMoves") and min_moves is None) or (
        query.get("maxMoves") and max_moves is None
    ):
        return json_response({"error": "Invalid move count."}, status=400)
    if min_moves is not None or max_moves is not None:
        ply_range: dict[str, int] = {}
        legacy_ply_checks: list[dict[str, object]] = []
        if min_moves is not None:
            ply_range["$gte"] = min_moves
            legacy_ply_checks.append({"$gte": [{"$size": {"$ifNull": ["$m", []]}}, min_moves]})
        if max_moves is not None:
            ply_range["$lte"] = max_moves
            legacy_ply_checks.append({"$lte": [{"$size": {"$ifNull": ["$m", []]}}, max_moves]})
        conditions.append(
            {
                "$or": [
                    {"p": ply_range},
                    {
                        "$and": [
                            {"p": {"$exists": False}},
                            {"$expr": {"$and": legacy_ply_checks}},
                        ]
                    },
                ]
            }
        )
    if query.get("analysed") == "1":
        conditions.append({"a.0": {"$exists": True}})

    if not conditions:
        return json_response({"error": "Choose at least one search condition."}, status=400)
    if not (players or tournament or variant_name or date_range):
        return json_response(
            {
                "error": (
                    "Add a player, variant, tournament, or date range to keep the search efficient."
                )
            },
            status=400,
        )

    filter_cond: dict[str, object] = conditions[0] if len(conditions) == 1 else {"$and": conditions}
    filter_cond = _apply_category_filter(filter_cond, user) or {"_id": None}
    direction = 1 if query.get("sort") == "oldest" else -1
    # Player-oriented indexes end with ``d``. Adding ``_id`` to the sort forces
    # MongoDB to perform a blocking sort instead of reading those indexes in
    # order, which is especially costly for prolific players. Date values are
    # already sufficiently precise for the existing page/skip pagination, and
    # this matches the long-standing profile-game query. Keep the deterministic
    # tie-breaker for searches that can use the d/_id catalogue indexes.
    sort_fields = [("d", direction)]
    if not players:
        sort_fields.append(("_id", direction))

    try:
        docs = await (
            app_state.db.game.find(filter_cond)
            .sort(sort_fields)
            .skip(page * GAME_PAGE_SIZE)
            .limit(GAME_PAGE_SIZE + 1)
            .max_time_ms(GAME_SEARCH_MAX_TIME_MS)
            .to_list(GAME_PAGE_SIZE + 1)
        )
    except ExecutionTimeout:
        return json_response(
            {
                "error": (
                    "Search took too long. Add a player, variant, tournament, "
                    "or narrower date range."
                )
            },
            status=422,
        )

    has_more = len(docs) > GAME_PAGE_SIZE and page < 99
    games: list[GameDoc] = []
    for raw_doc in docs[:GAME_PAGE_SIZE]:
        prepared = await _game_doc_for_list(request, raw_doc)
        if prepared is not None:
            games.append(prepared)
    return json_response({"games": games, "hasMore": has_more})
