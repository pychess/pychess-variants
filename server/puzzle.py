from __future__ import annotations

import logging
import random
from datetime import UTC, datetime
from inspect import isawaitable

import aiohttp_session
from const import (
    CATEGORY_VARIANT_LISTS,
    CATEGORY_VARIANT_SETS,
    GAME_CATEGORY_ALL,
)
from fairy import FairyBoard
from glicko2.glicko2 import MU, PHI, SIGMA, Rating, gl2
from json_utils import json_response
from preferences import effective_game_category
from pychess_global_app_state_utils import get_app_state
from pymongo.errors import DuplicateKeyError
from request_utils import read_post_data
from variants import VARIANTS

log = logging.getLogger(__name__)


# This was used only once to rename the document properties
# but it is useful to let it here for documentation purpose
FIELD_MAPPING = {
    "fen": "f",
    "variant": "v",
    "moves": "m",
    "eval": "e",
    "type": "t",
    "uploadedBy": "b",
    "site": "s",
    "review": "r",
    "played": "p",
    "up": "u",
    "down": "d",
    "cooked": "c",
    "gameId": "g",
}

# variants having 0 puzzle so far
NO_PUZZLE_VARIANTS = (
    "antichess",
    "horde",
    "placement",
    "gorogoroplus",
    "cannonshogi",
    "bughouse",
    "fogofwar",
    "supply",
    "makbug",
    "shoshogi",
    "jieqi",
)

PUZZLE_VARIANTS = [v for v in VARIANTS if (not v.endswith("960") and (v not in NO_PUZZLE_VARIANTS))]

NOT_VOTED = 0
UP = 1
DOWN = -1


def daily_puzzle_key(date_str: str, category: str) -> str:
    return f"{date_str}:{category}"


def daily_puzzle_category(key: str) -> str:
    if ":" in key:
        return key.split(":", 1)[1]
    return GAME_CATEGORY_ALL


def forget_daily_puzzle_references(app_state, puzzle_id: str) -> list[str]:
    """Drop every daily puzzle entry pointing at a puzzle that no longer exists.

    A deleted puzzle must not stay wired into the daily rotation: the lobby
    would serialize a null puzzle and the puzzle page would 404. Only the
    in-memory cache is touched here; the returned keys are the documents the
    caller has to remove from the ``dailypuzzle`` collection as well.
    """
    daily_puzzle_ids = app_state.daily_puzzle_ids
    stale_keys = [key for key, value in daily_puzzle_ids.items() if value == puzzle_id]
    for key in stale_keys:
        del daily_puzzle_ids[key]
    return stale_keys


async def drop_stale_daily_puzzle_keys(app_state, puzzle_id: str) -> None:
    """Forget a deleted puzzle in both the daily cache and the database."""
    for key in forget_daily_puzzle_references(app_state, puzzle_id):
        await app_state.db.dailypuzzle.delete_one({"_id": key})


async def rename_puzzle_fields(db):
    log.info("-----------------------------------------")
    log.info("Starting puzzle field rename migration...")
    for old_name, new_name in FIELD_MAPPING.items():
        try:
            result = await db.puzzle.update_many(
                {old_name: {"$exists": True}},
                {"$rename": {old_name: new_name}},
            )
            log.info(f"Renamed {old_name} -> {new_name} in {result.modified_count} documents.")
        except Exception as e:
            log.info(f"Failed renaming {old_name} -> {new_name}: {e}")
    log.info("Migration completed.")
    log.info("--------------------")


def empty_puzzle(variant):
    puzzle = {
        "_id": "0",
        "v": variant,
        "f": FairyBoard.start_fen(variant),
        "t": "",
        "m": "",
        "e": "",
    }
    return puzzle


async def _read_puzzle_post(request):
    return await read_post_data(request)


async def _get_puzzle_session_user(request):
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    session_user_value = session.get("user_name")
    session_user = session_user_value if isinstance(session_user_value, str) else None
    if session_user is not None:
        return await app_state.users.get(session_user)
    if app_state.disable_new_anons:
        return None

    # The puzzle page itself is stateless, but completing or voting on a
    # puzzle is an anonymous action that needs a stable browser identity.
    from user import mint_guest_user

    return await mint_guest_user(app_state, request, session, arriving_at="puzzle")


async def get_puzzle(request, puzzleId):
    puzzle = await get_app_state(request.app).db.puzzle.find_one({"_id": puzzleId})
    return puzzle


async def get_daily_puzzle(request):
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return empty_puzzle("chess")

    if await app_state.db.puzzle.find_one({}, {"_id": 1}) is None:
        return empty_puzzle("chess")

    today = datetime.now(UTC).date().isoformat()
    daily_puzzle_ids = app_state.daily_puzzle_ids
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if isinstance(session_user, str) and session_user in app_state.users:
        current_user = app_state.users[session_user]
    elif session_user:
        current_user = await app_state.users.get(session_user)
    else:
        current_user = None
    game_category = effective_game_category(session, current_user)
    key = daily_puzzle_key(today, game_category)

    puzzle = None
    cached_keys = [key]
    if game_category == GAME_CATEGORY_ALL and today in daily_puzzle_ids:
        cached_keys.append(today)
    for cached_key in cached_keys:
        # Read the id before awaiting: a concurrent request cleaning up the same
        # dangling entry would otherwise drop the key while we are suspended.
        cached_puzzle_id = daily_puzzle_ids.get(cached_key)
        if cached_puzzle_id is None:
            continue
        cached_puzzle = await get_puzzle(request, cached_puzzle_id)
        if cached_puzzle is not None:
            puzzle = cached_puzzle
            break
        # The cached daily puzzle was deleted. Forget the dangling entries so a
        # replacement is chosen below instead of returning None, which would be
        # serialized into the lobby as a null puzzle and break the whole page.
        await drop_stale_daily_puzzle_keys(app_state, cached_puzzle_id)

    if puzzle is None:
        user = app_state.users["PyChess"]

        # skip previous daily puzzles
        category_puzzle_ids = {
            puzzle_id
            for puzzle_key, puzzle_id in daily_puzzle_ids.items()
            if daily_puzzle_category(puzzle_key) == game_category
        }
        user.puzzles = {puzzle_id: NOT_VOTED for puzzle_id in category_puzzle_ids}
        # print(user.puzzles)

        if game_category == GAME_CATEGORY_ALL:
            available_variants = PUZZLE_VARIANTS
        else:
            allowed_variants = CATEGORY_VARIANT_SETS[game_category]
            available_variants = [v for v in PUZZLE_VARIANTS if v in allowed_variants]
            if not available_variants:
                fallback_variants = CATEGORY_VARIANT_LISTS[game_category]
                available_variants = list(fallback_variants) if fallback_variants else ["chess"]

        puzzleId = "0"
        while puzzleId == "0":
            # randomize daily puzzle variant
            if available_variants:
                user.puzzle_variant = random.choice(available_variants)
            else:
                user.puzzle_variant = None
            puzzle = await next_puzzle(request, user)
            if puzzle.get("e") != "#1":
                puzzleId = puzzle["_id"]

        try:
            await app_state.db.dailypuzzle.insert_one({"_id": key, "puzzleId": puzzleId})
            app_state.daily_puzzle_ids[key] = puzzle["_id"]
        except DuplicateKeyError:
            # I have no idea how this can happen though...
            daily_puzzle_doc = await app_state.db.dailypuzzle.find_one({"_id": key})
            if daily_puzzle_doc is None:
                return empty_puzzle("chess")
            puzzleId = daily_puzzle_doc["puzzleId"]
            try:
                await app_state.db.dailypuzzle.insert_one({"_id": key, "puzzleId": puzzleId})
                app_state.daily_puzzle_ids[key] = puzzleId
                puzzle = await get_puzzle(request, puzzleId)
            except Exception:
                return empty_puzzle("chess")
    return puzzle


async def next_puzzle(
    request,
    user,
    *,
    puzzle_variant: str | None = None,
    use_user_variant: bool = True,
):
    app_state = get_app_state(request.app)
    skipped = list(user.puzzles.keys())
    filters = [
        {"_id": {"$nin": skipped}},
        {"c": {"$ne": True}},
        {"r": {"$ne": False}},
    ]
    selected_variant = user.puzzle_variant if use_user_variant else puzzle_variant
    if selected_variant is not None:
        variant = selected_variant
        filters.append({"v": variant})
    else:
        session = await aiohttp_session.get_session(request)
        game_category = effective_game_category(session, user)
        if game_category != GAME_CATEGORY_ALL:
            category_variants = CATEGORY_VARIANT_LISTS[game_category]
            variant = category_variants[0] if category_variants else "chess"
            filters.append({"v": variant})
        else:
            variant = "chess"

    puzzle = None

    if app_state.db is not None:
        pipeline = [
            {"$match": {"$and": filters}},
            {"$sample": {"size": 1}},
        ]
        cursor_or_awaitable = app_state.db.puzzle.aggregate(pipeline)
        cursor = (
            await cursor_or_awaitable if isawaitable(cursor_or_awaitable) else cursor_or_awaitable
        )

        async for doc in cursor:
            puzzle = {
                "_id": doc["_id"],
                "v": doc["v"],
                "f": doc["f"],
                "m": doc["m"],
                "t": doc["t"],
                "e": doc["e"],
                "s": doc.get("s", ""),
                "g": doc.get("g", ""),
                "p": doc.get("p", 0),
                "lm": doc.get("lm", ""),
            }
            break

    if puzzle is None:
        puzzle = empty_puzzle(variant)

    return puzzle


async def puzzle_complete(request):
    app_state = get_app_state(request.app)
    puzzleId = request.match_info.get("puzzleId")
    post_data = await _read_puzzle_post(request)
    if post_data is None:
        return json_response({})
    rated = post_data["rated"] == "true"

    puzzle_data = await get_puzzle(request, puzzleId)
    if puzzle_data is None:
        # The puzzle was deleted while the page was open. Nothing to rate.
        return json_response({})
    puzzle = Puzzle(app_state.db, puzzle_data)

    await puzzle.set_played()

    user = await _get_puzzle_session_user(request)
    if user is None:
        return json_response({})

    if puzzleId in user.puzzles:
        return json_response({})
    else:
        user.puzzles[puzzleId] = NOT_VOTED

    if user.anon or (not rated):
        return json_response({})

    variant = post_data["v"]
    chess960 = False  # TODO: add chess960 to xxx960 variant puzzles
    color = post_data["color"]
    win = post_data["win"] == "true"

    if color[0] == "w":
        wplayer, bplayer = user, puzzle
        white_rating = user.get_puzzle_rating(variant, chess960)
        black_rating = puzzle.get_rating(variant, chess960)
        result = "1-0" if win else "0-1"
    else:
        wplayer, bplayer = puzzle, user
        white_rating = puzzle.get_rating(variant, chess960)
        black_rating = user.get_puzzle_rating(variant, chess960)
        result = "0-1" if win else "1-0"

    ratings = await update_puzzle_ratings(
        wplayer, bplayer, white_rating, black_rating, variant, chess960, result
    )
    return json_response(ratings)


async def puzzle_vote(request):
    app_state = get_app_state(request.app)
    puzzleId = request.match_info.get("puzzleId")
    post_data = await _read_puzzle_post(request)
    if post_data is None:
        return json_response({})
    good = post_data["vote"] == "true"
    up_or_down = "u" if good else "d"

    user = await _get_puzzle_session_user(request)
    if user is None:
        return json_response({})

    if user.puzzles.get(puzzleId):
        return json_response({})
    else:
        user.puzzles[puzzleId] = UP if good else DOWN

    db = app_state.db
    if db is not None:
        await db.puzzle.find_one_and_update({"_id": puzzleId}, {"$inc": {up_or_down: 1}})

    return json_response({})


async def update_puzzle_ratings(
    wplayer, bplayer, white_rating, black_rating, variant, chess960, result
):
    if result == "1-0":
        (white_score, black_score) = (1.0, 0.0)
    elif result == "0-1":
        (white_score, black_score) = (0.0, 1.0)
    else:
        raise RuntimeError("game.result: unexpected result code")

    wr = gl2.rate(white_rating, [(white_score, black_rating)])
    br = gl2.rate(black_rating, [(black_score, white_rating)])

    await wplayer.set_puzzle_rating(variant, chess960, wr)
    await bplayer.set_puzzle_rating(variant, chess960, br)

    wrdiff = int(round(wr.mu - white_rating.mu, 0))
    brdiff = int(round(br.mu - black_rating.mu, 0))
    return (wrdiff, brdiff)


def default_puzzle_perf(puzzle_eval):
    perf = {
        "gl": {"r": float(MU), "d": float(PHI), "v": float(SIGMA)},
        "la": datetime.now(UTC),
        "nb": 0,
    }
    if len(puzzle_eval) > 1 and puzzle_eval[0] == "#":
        perf["gl"]["r"] = MU + 200 * (int(puzzle_eval[1:]) - 2)
    return perf


class Puzzle:
    def __init__(self, db, puzzle_data):
        self.db = db
        self.puzzle_data = puzzle_data
        self.puzzleId = puzzle_data["_id"]
        self.perf = puzzle_data.get("perf", default_puzzle_perf(puzzle_data["e"]))

    def get_rating(self, variant: str, chess960: bool) -> Rating:
        gl = self.perf["gl"]
        la = self.perf["la"]
        return gl2.create_rating(gl["r"], gl["d"], gl["v"], la)

    async def set_puzzle_rating(self, _variant: str, _chess960: bool, rating: Rating):
        gl = {"r": rating.mu, "d": rating.phi, "v": rating.sigma}
        la = datetime.now(UTC)
        nb = self.perf.get("nb", 0)
        self.perf = {
            "gl": gl,
            "la": la,
            "nb": nb + 1,
        }

        if self.db is not None:
            await self.db.puzzle.find_one_and_update(
                {"_id": self.puzzleId}, {"$set": {"perf": self.perf}}
            )

    async def set_played(self):
        if self.db is not None:
            await self.db.puzzle.find_one_and_update(
                {"_id": self.puzzleId}, {"$set": {"p": self.puzzle_data.get("p", 0) + 1}}
            )
