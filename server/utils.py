from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import aiohttp_session
from aiohttp import web
from aiohttp_sse import sse_response
from broadcast import round_broadcast
from clock import Clock, CorrClock, first_move_timeout_reason
from compress import C2R, R2C
from const import (
    CASUAL,
    DARK_FEN,
    IMPORTED,
    INVALIDMOVE,
    NOTIFY_PAGE_SIZE,
    RATED,
    SSE_SNAPSHOT_QUEUE_MAXSIZE,
    STARTED,
    T_STARTED,
    UNKNOWNFINISH,
    VARIANT_960_TO_PGN,
    category_matches,
)
from convert import grand2zero, mirror5, mirror9, zero2grand
from fairy import (
    BLACK,
    FEN_OK,
    MANCHU_FEN,
    NOTATION_SAN,
    STANDARD_FEN,
    WHITE,
    FairyBoard,
    get_san_moves,
    modded_variant,
    validate_fen,
)
from game import Game, StaleMovePersistenceError
from newid import new_id
from seek import (
    ANON_RESTRICTED_SEEK_MESSAGE,
    DIRECT_CHALLENGE_ACCEPTED,
    TWO_BOARD_TARGETED_SEEK_MESSAGE,
    is_anon_restricted_seek,
    is_targeted_two_board_seek,
)
from ublog import display_date, image_src, post_url
from user import User
from users import NotInDbUsers
from valid_fen import VALID_FEN

if TYPE_CHECKING:
    from bug.game_bug import GameBug
    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
    from seek import Seek
    from typing_defs import (
        ClockValues,
        Crosstable,
        GameBoardResponse,
        GameDocument,
        GameEndResponse,
    )
    from user import User
    from ws_types import (
        AnalysisBoardMessage,
        ErrorMessage,
        JieqiCaptureMoveMessage,
        NewGameMessage,
        SeekStatusMessage,
    )
import logging

from json_utils import json_response
from preferences import effective_game_category
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from session_security import session_expiry_timeout
from settings import URI
from sse_utils import consume_sse_queue
from variants import (
    C2V,
    GRANDS,
    TWO_BOARD_VARIANT_CODES,
    catalogued_variant_random_start,
    get_server_variant,
    is_catalogued_variant,
)

log = logging.getLogger(__name__)
USERNAME_PREFIX_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")

NO_LEGAL_MOVES_START_FEN_MESSAGE = (
    "Failed to create game. The starting position leaves the side to move with no legal move."
)
MAX_CUSTOM_FEN_LENGTH = 4096
FAIRY_STOCKFISH_MAX_ACTIVE_PIECES = 128
FAIRY_STOCKFISH_POCKET_SLOTS_PER_FILE = 2
REALTIME_GAME_IN_PROGRESS_MESSAGE = "You already have a realtime game in progress."


def active_realtime_game_for_user(
    app_state: PychessGlobalAppState,
    user: User | None,
    *,
    allowed_simul_id: str | None = None,
):
    """Return an active non-correspondence game that blocks a new realtime game.

    ``app_state.games`` is authoritative here rather than ``User.game_in_progress``.
    The latter is intentionally only a single navigation hint and cannot represent
    a simul host's several simultaneous boards.
    """
    if user is None or user.bot:
        return None

    for game in getattr(app_state, "games", {}).values():
        if game.status > STARTED or getattr(game, "corr", False):
            continue
        if allowed_simul_id is not None and getattr(game, "simulId", None) == allowed_simul_id:
            continue
        if any(player.username == user.username for player in game.non_bot_players):
            return game
    return None


def realtime_game_conflict(
    app_state: PychessGlobalAppState,
    players,
    *,
    allowed_simul_id: str | None = None,
    simul_host_username: str | None = None,
):
    """Return ``(player, game)`` for the first blocked realtime participant.

    A simul host may already be playing other boards belonging to that same simul.
    Duplicate seats in one two-board seek are collapsed by username, allowing the
    supported one-person-team Bughouse/Supply-style setup without permitting an
    unrelated second realtime game.
    """
    seen: set[str] = set()
    for player in players:
        if player is None or player.bot or player.username in seen:
            continue
        seen.add(player.username)
        same_simul = allowed_simul_id if player.username == simul_host_username else None
        game = active_realtime_game_for_user(app_state, player, allowed_simul_id=same_simul)
        if game is not None:
            return player, game
    return None


async def put_bot_game_queue(player: User, game_id: str, payload: str) -> bool:
    queue = player.game_queues.get(game_id)
    if queue is None:
        return False
    await queue.put(payload)
    return True


def should_send_game_start_to_bot(game: Game | GameBug) -> bool:
    """Janggi bots must wait for setup phase completion before first move."""
    return game.variant != "janggi" or not (game.bsetup or game.wsetup)


async def send_bot_game_start_unless_streaming(player: User, game: Game | GameBug) -> bool:
    """Queue bot gameStart unless Janggi setup is incomplete or a live stream exists."""
    if not should_send_game_start_to_bot(game):
        return False
    if game.id in player.active_game_streams:
        return False
    await player.event_queue.put(game.game_start)
    return True


def activate_correspondence_game(game: Game) -> None:
    """Attach an active correspondence game to its players and restore its clock.

    ``load_game()`` can be called lazily from a game URL before the background
    correspondence restore has finished. Keep the activation idempotent so both
    paths may safely touch the same game.
    """
    if game not in game.wplayer.correspondence_games:
        game.wplayer.correspondence_games.append(game)
    if game not in game.bplayer.correspondence_games:
        game.bplayer.correspondence_games.append(game)

    assert isinstance(game.stopwatch, CorrClock)
    game.stopwatch.restart(from_db=True)


async def tv_game(app_state: PychessGlobalAppState):
    """Get latest played game id"""
    if app_state.tv is not None:
        return app_state.tv
    game_id = None
    # No Fog of War games to TV
    doc = await app_state.db.game.find_one({"v": {"$ne": "Q"}}, sort=[("$natural", -1)])
    if doc is not None:
        game_id = doc["_id"]
        app_state.tv = game_id
    return game_id


async def tv_game_user(db, users, profileId):
    """Get latest played game id by a given user name"""
    if users[profileId].tv is not None:
        return users[profileId].tv
    game_id = None
    # Use date sort so Mongo can use the profile compound index.
    doc = await db.game.find_one({"us": profileId}, sort=[("d", -1)])
    if doc is not None:
        game_id = doc["_id"]
        users[profileId].tv = game_id
    return game_id


async def load_game(
    app_state: PychessGlobalAppState,
    game_id: str,
    *,
    cache_finished: bool = True,
) -> Game | GameBug | None:
    """Return Game object from app cache or from database."""
    if game_id in app_state.games:
        return app_state.games[game_id]

    # log.debug("load_game() %s from db ", game_id)
    doc: GameDocument | None = await app_state.db.game.find_one({"_id": game_id})
    if doc is None:
        return None

    return await load_game_from_doc(app_state, doc, cache_finished=cache_finished)


async def load_game_from_doc(
    app_state: PychessGlobalAppState,
    doc: GameDocument,
    *,
    cache_finished: bool = True,
) -> Game | GameBug | None:
    """Return one shared Game object for an already fetched database document.

    Startup restore already iterates over game documents from MongoDB. Parsing the
    document directly avoids one extra ``find_one({_id: ...})`` round trip for
    every active game restored during server initialization. A construction task
    is shared by concurrent lazy loads and background restore so a game can never
    acquire two independent in-process move locks.
    """
    game_id = doc["_id"]
    if game_id in app_state.games:
        return app_state.games[game_id]

    load_task = app_state.game_load_tasks.get(game_id)
    if load_task is None:
        load_task = asyncio.create_task(
            _load_game_from_doc(app_state, doc),
            name=f"load-game-{game_id}",
        )
        app_state.game_load_tasks[game_id] = load_task

        def remove_completed_load_task(done: asyncio.Task[Game | GameBug | None]) -> None:
            if app_state.game_load_tasks.get(game_id) is done:
                app_state.game_load_tasks.pop(game_id, None)

        load_task.add_done_callback(remove_completed_load_task)

    game = await asyncio.shield(load_task)
    if game is None:
        return None

    if game.status > STARTED and cache_finished:
        cached_game = app_state.games.setdefault(game_id, game)
        if cached_game is game:
            app_state.schedule_game_cache_removal(game)
        return cached_game

    return game


async def _load_game_from_doc(
    app_state: PychessGlobalAppState,
    doc: GameDocument,
) -> Game | GameBug | None:
    """Construct a game once; callers apply their finished-game cache policy."""
    game_id = doc["_id"]

    if doc.get("vini") and doc["v"] not in C2V:
        from catalogued_variants import ensure_catalogued_variant_from_game_doc

        ensure_catalogued_variant_from_game_doc(app_state, doc)

    variant = C2V[doc["v"]]

    if doc["v"] in TWO_BOARD_VARIANT_CODES:
        from bug.utils_bug import load_game_bug_from_doc

        return await load_game_bug_from_doc(app_state, doc, cache_finished=False)

    # log.debug("load_game() parse START")
    wp, bp = doc["us"]

    wplayer = await app_state.users.get(wp)
    bplayer = await app_state.users.get(bp)

    initial_fen = doc.get("if")
    if variant == "manchu" and initial_fen is None and doc["d"].date() < date(2024, 9, 9):
        initial_fen = MANCHU_FEN

    # Old USI Shogi games saved using usi2uci() need special handling
    usi_format = variant.endswith("shogi") and doc.get("uci") is None

    if usi_format:
        wplayer, bplayer = bplayer, wplayer
        if initial_fen:
            # print("load_game() USI SFEN was:", initial_fen)
            parts = initial_fen.split()
            if len(parts) > 3 and parts[1] in "wb":
                pockets = "[%s]" % parts[2] if parts[2] not in "-0" else ""
                initial_fen = (
                    parts[0] + pockets + (" w" if parts[1] == "b" else " b") + " 0 " + parts[3]
                )
            else:
                initial_fen = parts[0] + (" w" if parts[1] == "b" else " b") + " 0"
            # print("   changed to:", initial_fen)

    corr = doc.get("c", False)

    if TYPE_CHECKING:
        assert initial_fen is not None

    game = Game(
        app_state,
        game_id,
        variant,
        initial_fen,
        wplayer,
        bplayer,
        base=doc["b"],
        inc=doc["i"],
        byoyomi_period=int(doc.get("bp", 0)),
        level=doc.get("x"),
        rated=doc.get("y"),
        chess960=bool(doc.get("z")),
        corr=corr,
        create=False,
        tournamentId=doc.get("tid"),
        tournamentArrangementId=doc.get("aid"),
        simulId=doc.get("sid"),
    )
    simul_host_color = doc.get("sh")
    if game.simulId is not None:
        if simul_host_color not in ("w", "b"):
            raise ValueError(f"Simul game {game.id} is missing host side")
        game.simulHostColor = simul_host_color

    if variant == "jieqi":
        game.board.set_jieqi_initial_pieces(doc["bj"], doc["wj"])

    game.usi_format = usi_format

    decode_method = game.server_variant.move_decoding
    mlist = [*map(decode_method, doc["m"])]

    if game.byoyomi:
        loaded_states: list[tuple[tuple[int, int], bool, int]] = []
        for raw_state in doc.get("byost", []):
            if not isinstance(raw_state, dict):
                continue
            periods = raw_state.get("p")
            overtime = raw_state.get("o")
            correction = raw_state.get("c")
            if (
                isinstance(periods, list)
                and len(periods) == 2
                and all(isinstance(period, int) for period in periods)
                and isinstance(overtime, bool)
                and isinstance(correction, int)
            ):
                loaded_states.append(((periods[0], periods[1]), overtime, correction))

        # Only a complete stack is safe for takebacks. Older active games have
        # no snapshots and remain playable, but takebacks are disabled for them.
        if len(loaded_states) == len(mlist):
            game.byoyomi_state_stack.extend(loaded_states)

        current_periods = doc.get("byop")
        if (
            isinstance(current_periods, list)
            and len(current_periods) == 2
            and all(isinstance(period, int) for period in current_periods)
        ):
            game.restore_byoyomi_state(
                (
                    (current_periods[0], current_periods[1]),
                    bool(doc.get("byoo", False)),
                    int(doc.get("byoc", 0)),
                )
            )
        elif len(game.byoyomi_state_stack) == len(mlist) + 1:
            game.restore_byoyomi_state(game.byoyomi_state_stack[-1])

    if (mlist or game.tournamentId is not None) and doc["s"] > STARTED:
        game.saved = True

    if usi_format and variant in ("shogi", "shoshogi"):
        mirror = mirror9
        mlist = [*map(mirror, mlist)]

    elif usi_format and (variant in ("minishogi", "kyotoshogi")):
        mirror = mirror5
        mlist = [*map(mirror, mlist)]

    elif variant in GRANDS:
        mlist = [*map(zero2grand, mlist)]
        if variant == "janggi":
            game.wsetup = doc.get("ws", False)
            game.bsetup = doc.get("bs", False)

    if "a" in doc:
        game.analysis = doc["a"]

    if "cw" in doc or "cb" in doc:
        # Use .get() with a fallback so documents written before this change
        # (or mid-game documents that only have one side's clock pushed yet)
        # load without a KeyError.
        base_clock_time_w = doc.get("cw0")
        if not isinstance(base_clock_time_w, int):
            base_clock_time_w = (game.base * 1000 * 60) + (0 if game.base > 0 else game.inc * 1000)
        base_clock_time_b = doc.get("cb0")
        if not isinstance(base_clock_time_b, int):
            base_clock_time_b = (game.base * 1000 * 60) + (0 if game.base > 0 else game.inc * 1000)
        cw: list[int] = doc.get("cw", [])
        cb: list[int] = doc.get("cb", [])
        game.clocks_w = [base_clock_time_w] + cw if len(cw) > 0 else [base_clock_time_w]
        game.clocks_b = [base_clock_time_b] + cb if len(cb) > 0 else [base_clock_time_b]

    level = doc.get("x")
    game.date = doc["d"]
    game.last_move_time = doc.get("l")
    if game.date.tzinfo is None:
        game.date = game.date.replace(tzinfo=UTC)
    game.status = doc["s"]
    game.level = level if level is not None else 0
    game.result = C2R[doc["r"]]
    if not game.corr:
        if game.status <= STARTED:
            for player in game.non_bot_players:
                player.game_in_progress = game.id
        else:
            for player in game.non_bot_players:
                if player.game_in_progress == game.id:
                    player.game_in_progress = None
    if game.status > STARTED:
        # Finished games loaded from DB should not keep a live clock task.
        # Cancel immediately so the clock does not pin the game in memory
        # during the cache retention window.
        await game.stopwatch.cancel()

    try:
        wrating = doc["p0"]["e"]
        brating = doc["p1"]["e"]
        if TYPE_CHECKING:
            assert isinstance(wrating, str)
            assert isinstance(brating, str)
        game.wrating = wrating
        game.brating = brating
    except KeyError:
        game.wrating = "1500?"
        game.brating = "1500?"

    try:
        game.wrdiff = doc["p0"]["d"]
        game.brdiff = doc["p1"]["d"]
    except KeyError:
        game.wrdiff = ""
        game.brdiff = ""

    if game.tournamentId is not None:
        if doc.get("wb", False):
            game.berserk("white")
        if doc.get("bb", False):
            game.berserk("black")

    imported_by = doc.get("by")
    if imported_by is not None:
        game.imported_by = imported_by

    if game.corr:
        if doc.get("wd", False):
            game.draw_offers.add(game.wplayer.username)
        if doc.get("bd", False):
            game.draw_offers.add(game.bplayer.username)

    if len(mlist) > 0:
        game.board.move_stack = mlist
        game.board.fen = doc["f"]
        game.board.ply = len(mlist)
        game.board.color = WHITE if game.board.fen.split()[1] == "w" else BLACK
        game.lastmove = mlist[-1]

    if game.manual_count:
        raw_manual_count_toggled = doc.get("mct", [])
        manual_count_toggled: list[tuple[int, int]] = []
        if isinstance(raw_manual_count_toggled, list):
            for interval in raw_manual_count_toggled:
                if (
                    isinstance(interval, (list, tuple))
                    and len(interval) == 2
                    and isinstance(interval[0], int)
                    and isinstance(interval[1], int)
                ):
                    manual_count_toggled.append((interval[0], interval[1]))
        game.manual_count_toggled = manual_count_toggled

        active_count_started = doc.get("mc")
        if isinstance(active_count_started, int) and game.status <= STARTED:
            game.board.count_started = active_count_started
            if active_count_started > 0:
                count_start_ply = active_count_started - 1
                moves_since_count_start = game.board.ply - count_start_ply
                counting_color = game.board.color
                if moves_since_count_start % 2 != 0:
                    counting_color = BLACK if game.board.color == WHITE else WHITE
                counting_player = game.wplayer if counting_color == WHITE else game.bplayer
                game.draw_offers.add(counting_player.username)

        # Replay wants closed intervals plus a synthetic end for an active
        # interval at the current position. Keep manual_count_toggled itself
        # free of that synthetic end so a later stop/game end can persist the
        # real interval exactly once.
        replay_manual_count_toggled = list(manual_count_toggled)
        if game.board.count_started > 0 and game.status <= STARTED:
            replay_manual_count_toggled.append((game.board.count_started, game.board.ply + 1))
        game.mct = replay_manual_count_toggled

    game.counted_as_active = game.status == STARTED and game.board.ply > 0

    if game.corr and game.status <= STARTED:
        activate_correspondence_game(game)

    if game.has_crosstable:
        crosstable_doc = await app_state.db.crosstable.find_one({"_id": game.ct_id})
        if crosstable_doc is not None:
            crosstable: Crosstable = crosstable_doc
            game.crosstable = crosstable

    loaded_at = datetime.now(UTC)
    game.loaded_at = loaded_at

    if (not game.corr) and game.status <= STARTED:
        game.restore_realtime_clock_after_load(loaded_at)

    if game.status <= STARTED:
        app_state.games[game_id] = game

    # log.debug("load_game() parse DONE")
    return game


async def import_game(request):
    data = await read_post_data(request)
    if data is None:
        return json_response({})
    app_state = get_app_state(request.app)

    # print("---IMPORT GAME---")
    # print(data)
    # print("-----------------")

    username = data.get("username")
    if not isinstance(username, str) or not username:
        return json_response({"error": "Missing username."})

    wp = data.get("White", "White")
    bp = data.get("Black", "Black")

    try:
        wplayer = await app_state.users.get(wp)
    except NotInDbUsers:
        wplayer = User(app_state, username=wp, anon=True)
        app_state.users[wp] = wplayer

    try:
        bplayer = await app_state.users.get(bp)
    except NotInDbUsers:
        bplayer = User(app_state, username=bp, anon=True)
        app_state.users[bp] = bplayer

    variant = data.get("Variant", "chess").lower()
    chess960 = (
        catalogued_variant_random_start(variant)
        if is_catalogued_variant(variant)
        else variant.endswith("960")
    )
    if not is_catalogued_variant(variant):
        variant = variant.removesuffix("960")
    if variant == "caparandom":
        variant = "capablanca"
        chess960 = True
    elif variant == "fischerandom":
        variant = "chess"
        chess960 = True

    initial_fen = data.get("FEN", "")
    final_fen = data.get("final_fen", "")
    status = int(data.get("Status", UNKNOWNFINISH))
    result = data.get("Result", "*")
    result = result if result in R2C else "*"
    try:
        date_tag = data.get("Date", "")
        date = date_tag[0:10]
        date = map(int, date.split("." if "." in date else "/"))
        date = datetime(*date, tzinfo=UTC)
    except Exception:
        log.debug("Date tag parsing failed. %s", date_tag)
        date = datetime.now(UTC)

    try:
        minute = False
        tc_tag = data.get("TimeControl", "")
        tc = tc_tag.split("+")
        if tc[0][-1] == "分":
            minute = True
            tc[0] = tc[0][:-1]
        if tc[1][-1] == "秒":
            tc[1] = tc[1][:-1]
        tc = list(map(int, tc))
        base = int((tc[0] / 60 if tc[0] > 60 else tc[0]) if not minute else tc[0])
        inc = int(tc[1])
    except Exception:
        log.debug("TimeControl tag parsing failed. %s", tc_tag)
        base, inc = 0, 0

    try:
        server_variant = get_server_variant(variant, chess960)
    except KeyError:
        message = "Unsupported variant in imported PGN: %s" % variant
        log.warning("PGN import rejected: %s", message)
        return json_response({"error": message})

    moves, import_error = _encode_import_moves(
        data.get("moves", ""),
        move_encoding=server_variant.move_encoding,
        grand_variant=server_variant.server_name in GRANDS,
    )
    if import_error is not None:
        return json_response({"error": import_error})

    game_id = await new_id(None if app_state.db is None else app_state.db.game)
    existing = await app_state.db.game.find_one({"_id": {"$eq": game_id}})
    if existing:
        message = "Failed to create game. Game ID %s already in mongodb." % game_id
        log.exception(message)
        return json_response({"error": message})

    new_game: Game | None = None
    try:
        # print(game_id, variant, initial_fen, wplayer, bplayer)
        new_game = Game(
            app_state,
            game_id,
            variant,
            initial_fen,
            wplayer,
            bplayer,
            rated=IMPORTED,
            chess960=chess960,
            create=False,
        )
    except Exception:
        message = "Creating new Game %s failed!" % game_id
        log.exception(message)
        return json_response({"error": message})

    try:
        if TYPE_CHECKING:
            assert new_game is not None

        chess960 = new_game.chess960
        if TYPE_CHECKING:
            assert chess960 is not None
        document: GameDocument = {
            "_id": game_id,
            "us": [wplayer.username, bplayer.username],
            "v": new_game.server_variant.code,
            "b": base,
            "i": inc,
            "bp": new_game.byoyomi_period,
            "m": moves,
            "d": date,
            "f": final_fen,
            "s": status,
            "r": R2C[result],
            "x": new_game.level,
            "y": IMPORTED,
            "z": int(chess960),
            "by": username,
        }

        if initial_fen or chess960:
            document["if"] = new_game.initial_fen

        if variant.endswith("shogi") or variant in ("dobutsu", "gorogoro", "gorogoroplus"):
            document["uci"] = 1

        wrating = data.get("WhiteElo")
        brating = data.get("BlackElo")
        if wrating:
            document["p0"] = {"e": wrating}
        if brating:
            document["p1"] = {"e": brating}

        # print(document)
        result = await app_state.db.game.insert_one(document)
        # print("db insert IMPORTED game result %s" % repr(result.inserted_id))

        return json_response({"gameId": game_id})
    finally:
        # import_game() constructs a temporary Game only to validate/import the PGN.
        # It is never cached, so its clock task must be cancelled explicitly.
        if new_game is not None:
            await new_game.stopwatch.cancel()


def _encode_import_moves(
    raw_moves: str, *, move_encoding: Callable[[str], str], grand_variant: bool
) -> tuple[list[str], str | None]:
    move_stack = raw_moves.split()
    moves: list[str] = []
    for ply, move in enumerate(move_stack, start=1):
        try:
            normalized_move = grand2zero(move) if grand_variant else move
            moves.append(move_encoding(normalized_move))
        except Exception as exc:
            message = "Invalid move '%s' at ply %s in imported PGN." % (move, ply)
            log.warning("PGN import rejected: %s (%s: %s)", message, type(exc).__name__, exc)
            return [], message
    return moves, None


async def join_seek(
    app_state: PychessGlobalAppState,
    user: User,
    seek: Seek,
    game_id: str | None = None,
    join_as: str = "any",
) -> SeekStatusMessage | NewGameMessage | ErrorMessage:
    if is_targeted_two_board_seek(seek.variant, seek.chess960, seek.target):
        return {"type": "error", "message": TWO_BOARD_TARGETED_SEEK_MESSAGE}

    if not getattr(seek, "is_rr_challenge", False) and (
        seek.creator.username in user.blocked or user.username in seek.creator.blocked
    ):
        return {"type": "error", "message": "You cannot accept this seek."}

    if is_catalogued_variant(seek.variant):
        from catalogued_variants import can_create_catalogued_seek

        # AI games are created as a human-owned seek that the internal engine
        # user immediately joins.  Access for that internal bot join should be
        # determined by the human creator; otherwise private variants owned by
        # the player are rejected as inaccessible to Random-Mover/Fairy-Stockfish.
        access_user = seek.creator if getattr(user, "bot", False) else user
        username = None if access_user.anon else access_user.username
        if not can_create_catalogued_seek(app_state, seek.variant, username):
            return {"type": "error", "message": "This user-defined variant is not available."}

    log.info(
        "+++ Seek %s joined by %s FEN:%s 960:%s",
        seek.id,
        user.username,
        seek.fen,
        seek.chess960,
    )

    if is_anon_restricted_seek(user, seek.variant, seek.chess960, seek.day):
        return {"type": "error", "message": ANON_RESTRICTED_SEEK_MESSAGE}

    if seek.is_expired():
        if game_id is None:
            game_id = seek.game_id
        if game_id is not None:
            app_state.invites.pop(game_id, None)
        remove_seek(app_state.seeks, seek)
        return {
            "type": "error",
            "message": "Invitation expired"
            if seek.target == "Invite-friend"
            else "Challenge expired",
        }

    if user is seek.player1 or user is seek.player2:
        response: SeekStatusMessage = {"type": "seek_yourself", "seekID": seek.id}
        return response

    joined_slot: str | None = None
    if join_as == "player1":
        if seek.player1 is None:
            seek.player1 = user
            joined_slot = "player1"
        else:
            response: SeekStatusMessage = {"type": "seek_occupied", "seekID": seek.id}
            return response
    elif join_as == "player2":
        if seek.player2 is None:
            seek.player2 = user
            joined_slot = "player2"
        else:
            response: SeekStatusMessage = {"type": "seek_occupied", "seekID": seek.id}
            return response
    else:
        if seek.player1 is None:
            seek.player1 = user
            joined_slot = "player1"
        elif seek.player2 is None:
            seek.player2 = user
            joined_slot = "player2"
        else:
            response: SeekStatusMessage = {"type": "seek_occupied", "seekID": seek.id}
            return response

    if seek.player1 is not None and seek.player2 is not None:
        response = await new_game(app_state, seek, game_id)
        if response["type"] == "error" and joined_slot is not None:
            setattr(seek, joined_slot, None)
        return response
    else:
        response: SeekStatusMessage = {"type": "seek_joined", "seekID": seek.id}
        return response


async def new_game(
    app_state: PychessGlobalAppState, seek: Seek, game_id: str | None = None
) -> NewGameMessage | ErrorMessage:
    fen_valid = True
    if seek.fen:
        fen_valid, sanitized_fen = sanitize_fen(seek.variant, seek.fen, seek.chess960)
        if not fen_valid:
            message = "Failed to create game. Invalid FEN %s" % seek.fen
            log.debug(message)
            remove_seek(app_state.seeks, seek)
            return {"type": "error", "message": message}
    else:
        sanitized_fen = ""

    if seek.fen and not get_server_variant(seek.variant, seek.chess960).two_boards:
        board = FairyBoard(seek.variant, sanitized_fen, bool(seek.chess960))
        if not board.has_legal_move():
            message = NO_LEGAL_MOVES_START_FEN_MESSAGE
            log.debug(message)
            remove_seek(app_state.seeks, seek)
            return {"type": "error", "message": message}

    color = random.choice(("w", "b")) if seek.color == "r" else seek.color
    wplayer = seek.player1 if color == "w" else seek.player2
    bplayer = seek.player1 if color == "b" else seek.player2
    if TYPE_CHECKING:
        assert wplayer is not None
        assert bplayer is not None
        assert seek.chess960 is not None

    if game_id is None:
        game_id = await new_id(None if app_state.db is None else app_state.db.game)

    realtime_locked = seek.day == 0
    if realtime_locked:
        await app_state.realtime_game_creation_lock.acquire()
    try:
        if realtime_locked:
            conflict = realtime_game_conflict(app_state, (wplayer, bplayer))
            if conflict is not None:
                player, active_game = conflict
                log.info(
                    "Rejecting realtime game creation for %s; active game %s is still running",
                    player.username,
                    active_game.id,
                )
                return {"type": "error", "message": REALTIME_GAME_IN_PROGRESS_MESSAGE}

        # print("new_game", game_id, seek.variant, seek.fen, wplayer, bplayer, seek.base, seek.inc, seek.level, seek.rated, seek.chess960)
        catalogued_casual = is_catalogued_variant(seek.variant)
        any_bot_player = wplayer.bot or bplayer.bot
        rated = (
            CASUAL
            if catalogued_casual or any_bot_player
            else RATED
            if (seek.rated and (not wplayer.anon) and (not bplayer.anon))
            else CASUAL
        )

        game = Game(
            app_state,
            game_id,
            seek.variant,
            sanitized_fen,
            wplayer,
            bplayer,
            base=seek.base if seek.day == 0 else seek.day,
            inc=seek.inc,
            byoyomi_period=seek.byoyomi_period,
            level=seek.level,
            rated=rated,
            chess960=seek.chess960,
            corr=seek.day > 0,
            create=True,
            tournamentId=seek.tournament_id,
            tournamentArrangementId=seek.rr_arrangement_id,
            new_960_fen_needed_for_rematch=seek.reused_fen,
            is_rematch=seek.is_rematch,
        )
        app_state.games[game_id] = game
    except Exception:
        log.exception(
            "Creating new game %s failed! %s 960:%s FEN:%s %s vs %s",
            game_id,
            seek.variant,
            seek.chess960,
            seek.fen,
            wplayer,
            bplayer,
        )
        remove_seek(app_state.seeks, seek)
        return {"type": "error", "message": "Failed to create game"}
    finally:
        if realtime_locked:
            app_state.realtime_game_creation_lock.release()

    if seek.game_id is not None:
        # game invitation; only consume it after admission succeeded
        app_state.invites.pop(seek.game_id, None)

    if seek.is_direct_challenge:
        seek.set_challenge_status(DIRECT_CHALLENGE_ACCEPTED)
    else:
        remove_seek(app_state.seeks, seek)

    await insert_game_to_db(game, app_state)

    if game.corr:
        game.wplayer.correspondence_games.append(game)
        game.bplayer.correspondence_games.append(game)

    if game.has_crosstable:
        doc = await app_state.db.crosstable.find_one({"_id": game.ct_id})
        if doc is not None:
            game.crosstable = doc

    response: NewGameMessage = {
        "type": "new_game",
        "gameId": game_id,
        "wplayer": wplayer.username,
        "bplayer": bplayer.username,
    }
    return response


async def insert_game_to_db(game, app_state: PychessGlobalAppState):
    # unit test app may have no db. Private/unlisted catalogued variant
    # games are test games and intentionally stay in memory only.
    if app_state.db is None or not game.persist_to_db:
        return

    document = {
        "_id": game.id,
        "us": [game.wplayer.username, game.bplayer.username],
        "p0": {"e": game.wrating},
        "p1": {"e": game.brating},
        "v": game.variant if is_catalogued_variant(game.variant) else game.server_variant.code,
        "b": game.base,
        "i": game.inc,
        "bp": game.byoyomi_period,
        "m": [],
        "d": game.date,
        "f": game.board.initial_fen,
        "p": game.board.ply,
        "s": game.status,
        "r": R2C["*"],
        "x": game.level,
        "y": int(game.rated),
        "z": int(game.chess960),
        "c": game.corr,
    }

    if game.tournamentId is not None:
        document["tid"] = game.tournamentId
        round_no = getattr(game, "round", None)
        if round_no is not None:
            document["rn"] = round_no
    if game.tournamentArrangementId is not None:
        document["aid"] = game.tournamentArrangementId
    if game.simulId is not None:
        document["sid"] = game.simulId
        if game.simulHostColor not in ("w", "b"):
            raise ValueError(f"Simul game {game.id} is missing host side")
        document["sh"] = game.simulHostColor

    if game.variant.endswith("shogi") or game.variant in (
        "dobutsu",
        "gorogoro",
        "gorogoroplus",
    ):
        document["uci"] = 1

    if game.variant == "janggi":
        document["ws"] = game.wsetup
        document["bs"] = game.bsetup
        document["if"] = game.board.initial_fen
    elif game.variant == "jieqi":
        document["wj"] = "".join(game.board.red_pieces)
        document["bj"] = "".join(game.board.black_pieces)

    if is_catalogued_variant(game.variant):
        catalogued_doc = app_state.catalogued_variants.get(game.variant, {})
        if catalogued_doc.get("ini"):
            document["vini"] = catalogued_doc["ini"]
            document["vd"] = catalogued_doc.get("displayName", game.variant)
            document["vby"] = catalogued_doc.get("author", "")

    if game.clocks_w[0] != game.clocks_b[0]:
        document["cw0"] = int(game.clocks_w[0])
        document["cb0"] = int(game.clocks_b[0])

    if game.persist_clock_history:
        # Initialize clock arrays so load_game_from_doc() can always find
        # both keys together. This is required for rated games and for casual
        # tournament games, whose clocks must also survive a restart.
        document["cw"] = []
        document["cb"] = []

    if game.initial_fen or game.chess960:
        document["if"] = game.initial_fen

    result = await app_state.db.game.insert_one(document)
    if result.inserted_id != game.id:
        log.error("db insert game result %s failed !!!", game.id)

    # No corr and Fog of War games to TV
    if (not game.corr) and (game.variant != "fogofwar"):
        app_state.tv = game.id
        await app_state.lobby.lobby_broadcast(game.tv_game_json)
        game.wplayer.tv = game.id
        game.bplayer.tv = game.id


def remove_seek(seeks: dict[str, Seek], seek: Seek) -> None:
    log.debug("Seeks now contains: [%s]" % " ".join(seeks))
    log.debug("Removing seek: %s" % seek)

    if (not seek.creator.bot) and seek.id in seeks:
        del seeks[seek.id]
        if seek.id in seek.creator.seeks:
            del seek.creator.seeks[seek.id]

    log.debug("Removed seek. Seeks now contains: [%s]" % " ".join(seeks))


async def analysis_move(user: User, game: Game, move: str, fen: str, ply: int) -> None:
    invalid_move = False

    chess960 = game.chess960
    if TYPE_CHECKING:
        assert chess960 is not None
    board = FairyBoard(game.variant, fen, chess960)

    try:
        # san = board.get_san(move)
        lastmove = move
        board.push(move)
        check = board.is_checked()
    except Exception:
        invalid_move = True
        log.exception("!!! analysis_move() exception occurred")

    analysis_board_response: GameBoardResponse | AnalysisBoardMessage
    if invalid_move:
        analysis_board_response = game.get_board(full=True)
    else:
        analysis_board_response = {
            "type": "analysis_board",
            "gameId": game.id,
            "fen": board.fen,
            "ply": ply,
            "lastMove": lastmove,
            "check": check,
        }
    await user.send_game_message(game.id, analysis_board_response)


async def play_move(
    app_state: PychessGlobalAppState,
    user: User,
    game: Game,
    move: str,
    clocks: ClockValues | None = None,
    ply: int | None = None,
    position_id: str | None = None,
) -> None:
    gameId = game.id
    users = app_state.users
    invalid_move = False
    play_color = game.board.color
    player_color = (
        WHITE
        if user.username == game.wplayer.username
        else BLACK
        if user.username == game.bplayer.username
        else None
    )
    # log.info("%s move %s %s %s - %s" % (user.username, move, gameId, game.wplayer.username, game.bplayer.username))

    async def send_human_resync(reason: str) -> None:
        if user.bot or player_color is None:
            return
        log.info(
            "Sending board resync in %s to %s after %s (move=%s ply=%s fen=%s)",
            gameId,
            user.username,
            reason,
            move,
            ply,
            game.board.fen,
        )
        board_response = game.get_board(full=True, persp_color=player_color)
        await user.send_game_message(gameId, board_response)

    if game.status <= STARTED:
        fen_turn = WHITE if game.board.fen.split()[1] == "w" else BLACK
        if game.board.color != fen_turn:
            log.error(
                "Repairing board color mismatch in %s before move %s by %s (board.color=%s fen_turn=%s fen=%s)",
                gameId,
                move,
                user.username,
                game.board.color,
                fen_turn,
                game.board.fen,
            )
            game.board.color = fen_turn
            play_color = game.board.color

        current_position_id = game.position_id()
        if position_id is not None and position_id != current_position_id:
            log.info(
                "Rejecting stale position move in %s by %s (move=%s ply=%s position_id=%s current_position_id=%s fen=%s)",
                gameId,
                user.username,
                move,
                ply,
                position_id,
                current_position_id,
                game.board.fen,
            )
            await send_human_resync("stale-position")
            return

        if (ply is not None and game.ply + 1 != ply) or (
            game.ply > 0 and move == game.board.move_stack[-1]
        ):
            log.info(
                "invalid ply received - probably a re-sent move that has already been processed"
            )
            await send_human_resync("invalid-ply")
            return

        cur_player = game.bplayer if game.board.color == BLACK else game.wplayer
        if not game.is_player(user):
            log.info(
                "Ignoring move from non-player %s in %s (turn=%s, move=%s)",
                user.username,
                gameId,
                cur_player.username,
                move,
            )
            return
        if user.username != cur_player.username:
            log.info(
                "Ignoring out-of-turn move in %s by %s (turn=%s, move=%s)",
                gameId,
                user.username,
                cur_player.username,
                move,
            )
            await send_human_resync("out-of-turn")
            return
        if user.bot and not cur_player.bot:
            log.info("BOT move %s arrived probably while human player takeback happened" % move)
            return

        realtime_restart_clock_expired = (
            not user.bot
            and isinstance(game.stopwatch, Clock)
            and not game.server_variant.two_boards
            and game.persist_clock_history
            and game.restart_elapsed_ms > 0
            and game.stopwatch.running
            and game.stopwatch.secs <= 0
        )
        correspondence_clock_expired = (
            not user.bot
            and isinstance(game.stopwatch, CorrClock)
            and game.stopwatch.running
            and game.stopwatch.mins <= 0
        )
        if realtime_restart_clock_expired or correspondence_clock_expired:
            # A player cannot have made a move while this process was offline.
            # Reject an already-expired restored clock before the background
            # countdown task gets its next scheduling turn. The explicit
            # isinstance checks also keep real-time and correspondence clock
            # state type-safe and independent of how a game was created.
            log.info(
                "Rejecting move because restored clock expired in %s by %s",
                gameId,
                user.username,
            )
            await game.game_ended(user, first_move_timeout_reason(game, game.ply))
            invalid_move = True

        if not user.bot and not invalid_move:
            legal_moves = game.board.legal_moves()
            if move not in legal_moves:
                log.warning(
                    "Rejecting illegal human move in %s by %s (move=%s ply=%s turn=%s fen=%s)",
                    gameId,
                    user.username,
                    move,
                    ply,
                    cur_player.username,
                    game.board.fen,
                )
                await send_human_resync("illegal-human-move")
                return

        if not invalid_move:
            try:
                await game.play_move(move, clocks, ply)
            except StaleMovePersistenceError:
                log.warning(
                    "Rejecting stale move after persistence conflict in %s by %s (move=%s)",
                    gameId,
                    user.username,
                    move,
                )
                cached_game = app_state.games.get(gameId)
                if cached_game is game:
                    app_state.games.pop(gameId, None)
                    await game.cancel_clocks_for_eviction()
                    cached_game = None

                authoritative_game = (
                    cached_game
                    if isinstance(cached_game, Game)
                    else await load_game(app_state, gameId)
                )
                if not isinstance(authoritative_game, Game):
                    log.error("Unable to reload %s after a persistence conflict", gameId)
                    return

                game = authoritative_game
                await send_human_resync("stale-persistence")
                return
            except SystemError:
                invalid_move = True
                log.exception(
                    "Game %s aborted because invalid move %s by %s !!!",
                    gameId,
                    move,
                    user.username,
                )
                game.status = INVALIDMOVE
                game.result = "0-1" if user.username == game.wplayer.username else "1-0"
    else:
        # never play moves in finished games!
        log.info(
            "Ignoring move for finished game %s from %s (status=%s, move=%s)",
            gameId,
            user.username,
            game.status,
            move,
        )
        return

    if not invalid_move:
        # Default board response is from the mover's perspective.
        board_response = game.get_board(full=game.board.ply == 1, persp_color=play_color)

        if not user.bot:
            if game.variant == "jieqi" and game.last_jieqi_capture:
                # Send captured fake identity only to the capturer via a move message.
                # This avoids leaking the info through shared board payloads.
                if TYPE_CHECKING:
                    assert game.lastmove is not None
                jieqi_capture_response: JieqiCaptureMoveMessage = {
                    "type": "move",
                    "gameId": gameId,
                    "move": game.lastmove,
                    "jieqiCapture": game.last_jieqi_capture,
                }
                await user.send_game_message(gameId, jieqi_capture_response)
            await user.send_game_message(gameId, board_response)
        if game.variant == "jieqi":
            # Clear the one-shot capture hint after each move to avoid reuse.
            game.last_jieqi_capture = None

    if user.bot:
        if game.status > STARTED:
            await put_bot_game_queue(user, gameId, game.game_end)
        elif not invalid_move:
            await put_bot_game_queue(user, gameId, game.game_state)

    opp_name = (
        game.wplayer.username if user.username == game.bplayer.username else game.bplayer.username
    )
    game_end_response: GameEndResponse | None = None
    if game.status > STARTED:
        game_end_response = {
            "type": "gameEnd",
            "status": game.status,
            "result": game.result,
            "gameId": gameId,
            "pgn": game.pgn,
        }
        # Invalid moves skip the normal board push path, so notify the mover
        # explicitly to avoid round clients waiting forever for terminal state.
        if invalid_move and not user.bot:
            await user.send_game_message(gameId, game_end_response)

    # Hidden-info variants require perspective-specific board payloads.
    # For all other variants we reuse the mover perspective response.
    if game.server_variant.hidden_info:
        board_response = game.get_board(full=game.board.ply == 1, persp_color=1 - play_color)

    if users[opp_name].bot:
        if game.status > STARTED:
            await put_bot_game_queue(users[opp_name], gameId, game.game_end)
        else:
            # Fallback for built-in bots under heavy load: ensure the bot loop
            # receives a gameStart trigger even if the ready/gameStart path was delayed.
            queue_ready = gameId in users[opp_name].game_queues
            if (
                queue_ready
                and game.board.ply == 1
                and users[opp_name].username
                in (
                    "Random-Mover",
                    "Fairy-Stockfish",
                    "Alice-Stockfish",
                )
            ):
                await send_bot_game_start_unless_streaming(users[opp_name], game)
            await put_bot_game_queue(users[opp_name], gameId, game.game_state)
    else:
        if not invalid_move:
            await users[opp_name].send_game_message(gameId, board_response)
        if game_end_response is not None:
            await users[opp_name].send_game_message(gameId, game_end_response)

    if invalid_move and game_end_response is not None:
        # Spectators/embedded viewers need an explicit terminal event in the
        # invalid-move path because we intentionally do not broadcast a board.
        await round_broadcast(game, game_end_response, channels=app_state.game_channels)
        return

    if not invalid_move:
        # Spectators must not see hidden info in hidden-information variants.
        if game.server_variant.hidden_info:
            board_response = game.get_board(full=game.board.ply == 1, persp_color=None)

        await round_broadcast(game, board_response, channels=app_state.game_channels)

        if game.tournamentId is not None:
            # Arena games can continue after the finished tournament is evicted.
            tournament = app_state.tournaments.get(game.tournamentId)
            if (
                tournament is not None
                and tournament.status == T_STARTED
                and tournament.top_game is not None
                and tournament.top_game.id == gameId
            ):
                await tournament.broadcast(board_response)

        if app_state.tv == gameId:
            await app_state.lobby.lobby_broadcast(board_response)


def pgn(doc):
    if doc.get("vini") and doc["v"] not in C2V:
        # Export helpers may run outside normal startup caches. Load the inline
        # rules saved with the game so the move decoder and FSF replay can work.
        class _NoState:
            catalogued_variants: ClassVar[dict] = {}

        from catalogued_variants import ensure_catalogued_variant_from_game_doc

        ensure_catalogued_variant_from_game_doc(_NoState(), doc)
    variant = C2V[doc["v"]]
    chess960 = bool(int(doc.get("z"))) if "z" in doc else False

    decode_method = get_server_variant(variant, chess960).move_decoding
    mlist = [*map(decode_method, doc["m"])]
    if len(mlist) == 0:
        return None

    initial_fen = doc.get("if")
    usi_format = variant.endswith("shogi") and doc.get("uci") is None

    # wplayer, bplayer = bplayer, wplayer
    if usi_format and initial_fen:
        # print("load_game() USI SFEN was:", initial_fen)
        parts = initial_fen.split()
        if len(parts) > 3 and parts[1] in "wb":
            pockets = "[%s]" % parts[2] if parts[2] not in "-0" else ""
            initial_fen = (
                parts[0] + pockets + (" w" if parts[1] == "b" else " b") + " 0 " + parts[3]
            )
        else:
            initial_fen = parts[0] + (" w" if parts[1] == "b" else " b") + " 0"
        # print("   changed to:", initial_fen)

    if usi_format and variant in ("shogi", "shoshogi"):
        mirror = mirror9
        mlist = list(map(mirror, mlist))

    elif usi_format and (variant in ("minishogi", "kyotoshogi")):
        mirror = mirror5
        mlist = list(map(mirror, mlist))

    elif variant in GRANDS:
        mlist = list(map(zero2grand, mlist))

    fen = initial_fen if initial_fen is not None else FairyBoard.start_fen(variant)
    # print(variant, fen, mlist)
    # Try SAN conversion in stored variant first for backward compatibility.
    # If that fails, retry with modded castling semantics (capablanca->embassy).
    san_variants = [variant]
    variant_fallback = modded_variant(variant, chess960, fen)
    if variant_fallback != variant:
        san_variants.append(variant_fallback)

    for san_variant in san_variants:
        try:
            mlist = get_san_moves(san_variant, fen, mlist, chess960, NOTATION_SAN)
            break
        except Exception:
            log.error("%s %s %s movelist contains invalid move", doc["_id"], san_variant, doc["d"])
    else:
        for san_variant in san_variants:
            try:
                mlist = get_san_moves(san_variant, fen, mlist[:-1], chess960, NOTATION_SAN)
                break
            except Exception:
                log.error(
                    "%s %s %s movelist contains invalid move", doc["_id"], san_variant, doc["d"]
                )
        else:
            mlist = mlist[0]

    moves = " ".join(
        (
            move if ind % 2 == 1 else "%s. %s" % (((ind + 1) // 2) + 1, move)
            for ind, move in enumerate(mlist)
        )
    )
    if not get_server_variant(variant, chess960).two_boards and any(
        row and row.get("advice") for row in doc.get("a", [])
    ):
        from game_analysis import annotated_game_moves

        moves = annotated_game_moves(mlist, fen, doc["a"])
    no_setup = fen == STANDARD_FEN and not chess960
    # Use lichess format for crazyhouse games to support easy import
    setup_fen = fen if variant != "crazyhouse" else fen.replace("[]", "")

    return '[Event "{}"]\n[Site "{}"]\n[Date "{}"]\n[Round "-"]\n[White "{}"]\n[Black "{}"]\n[Result "{}"]\n[TimeControl "{}+{}"]\n[WhiteElo "{}"]\n[BlackElo "{}"]\n[Variant "{}"]\n{fen}{setup}\n{} {}\n'.format(
        "PyChess " + ("rated" if "y" in doc and doc["y"] == 1 else "casual") + " game",
        URI + "/" + doc["_id"],
        doc["d"].strftime("%Y.%m.%d"),
        doc["us"][0],
        doc["us"][1],
        C2R[doc["r"]],
        int(doc["b"] * 60),
        doc["i"],
        doc["p0"]["e"] if "p0" in doc else "?",
        doc["p1"]["e"] if "p1" in doc else "?",
        variant.capitalize()
        if not chess960 or is_catalogued_variant(variant)
        else VARIANT_960_TO_PGN[variant],
        moves,
        C2R[doc["r"]],
        fen="" if no_setup else '[FEN "%s"]\n' % setup_fen,
        setup="" if no_setup else '[SetUp "1"]\n',
    )


def fen_board_width(placement: str) -> int:
    board = placement.split("[", maxsplit=1)[0]
    first_rank = board.split("/", maxsplit=1)[0]
    width = 0
    index = 0
    while index < len(first_rank):
        char = first_rank[index]
        if char.isdigit():
            end = index + 1
            while end < len(first_rank) and first_rank[end].isdigit():
                end += 1
            width += int(first_rank[index:end])
            index = end
            continue
        if char not in "+~|":
            width += 1
        index += 1
    return width


def _fen_material_counts(placement: str) -> tuple[dict[str, int], int]:
    counts: dict[str, int] = {}
    total = 0
    for index, char in enumerate(placement):
        if not char.isascii() or not char.isalpha():
            continue
        # In capture-to-hand variants, "~" marks a promoted pawn that returns
        # to its base type when captured.
        role = "p" if index + 1 < len(placement) and placement[index + 1] == "~" else char.lower()
        counts[role] = counts.get(role, 0) + 1
        total += 1

    return counts, total


def pocket_variant_material_fits_engine(initial_fen: str, start_fen: str) -> bool:
    """Bound pocket and active material before initializing a native position."""
    placement = initial_fen.split(maxsplit=1)[0]
    start_placement = start_fen.split(maxsplit=1)[0]
    if "[" in placement:
        pocket = placement.split("[", maxsplit=1)[1].split("]", maxsplit=1)[0]
    elif placement.count("/") > start_placement.count("/"):
        pocket = placement.rsplit("/", maxsplit=1)[1]
    else:
        pocket = ""

    pocket_counts: dict[str, int] = {}
    for char in pocket:
        if char.isascii() and char.isalpha():
            pocket_counts[char] = pocket_counts.get(char, 0) + 1

    pocket_slots_per_role = FAIRY_STOCKFISH_POCKET_SLOTS_PER_FILE * fen_board_width(start_placement)
    if any(count > pocket_slots_per_role for count in pocket_counts.values()):
        return False

    counts, total = _fen_material_counts(placement)
    if total > FAIRY_STOCKFISH_MAX_ACTIVE_PIECES:
        return False

    start_counts, _ = _fen_material_counts(start_placement)
    return all(
        count <= max(pocket_slots_per_role, start_counts.get(role, 0))
        for role, count in counts.items()
    )


def sanitize_fen(variant, initial_fen, chess960, base=False):
    if len(initial_fen) > MAX_CUSTOM_FEN_LENGTH:
        return False, ""

    server_variant = get_server_variant(variant, chess960)
    if server_variant.two_boards and not base:
        fens = initial_fen.split(" | ")
        fen_a = fens[0]
        fen_b = fens[1]
        fen_valid_a, sanitized_fen_a = sanitize_fen(
            server_variant.base_variant, fen_a, chess960, base=True
        )
        fen_valid_b, sanitized_fen_b = sanitize_fen(
            server_variant.base_variant, fen_b, chess960, base=True
        )
        return fen_valid_a and fen_valid_b, sanitized_fen_a + " | " + sanitized_fen_b

    # Prevent alternate FENs to fail on our general castling check
    if variant in VALID_FEN and initial_fen in VALID_FEN[variant]:
        return True, initial_fen

    start_fen = FairyBoard.start_fen(variant)
    start_placement = start_fen.split(maxsplit=1)[0]
    if "[" in start_placement and not pocket_variant_material_fits_engine(initial_fen, start_fen):
        return False, ""

    sf_validate = validate_fen(initial_fen, variant, chess960)
    if sf_validate != FEN_OK and not chess960 and variant in ("seirawan", "shouse"):
        # Fairy-Stockfish's non-960 FEN validator treats the remaining file-letter
        # gating rights like castling rights once the king has moved. That rejects
        # legal mid-game S-Chess positions generated by the engine itself, such as
        # a position with a castled king and an unmoved bishop still eligible to
        # gate. Re-validating the same FEN in 960 mode keeps the engine's syntax,
        # material and gating-square safety checks without changing how the
        # position is subsequently played (the chapter remains non-960).
        sf_validate = validate_fen(initial_fen, variant, True)
    if sf_validate != FEN_OK and variant != "duck":
        return False, ""

    if is_catalogued_variant(variant):
        # Community rules can allow no kings, different royal pieces, or pieces
        # absent from the starting position. After the engine safety checks,
        # trust the loaded definition instead of applying first-class rules.
        return True, initial_fen

    # Initial_fen needs validation to prevent segfaulting in pyffish
    sanitized_fen = initial_fen

    start_fen_length = len(start_fen)
    start = start_fen.split()
    init = initial_fen.split()

    # Cut off tail
    if len(init) > start_fen_length:
        init = init[:start_fen_length]
        sanitized_fen = " ".join(init)

    # We need starting color
    invalid0 = len(init) < 2

    # Only piece types listed in variant start position can be used later
    if variant == "dobutsu":
        non_piece = "~+0123456789[]hH-"
    elif variant == "alice":
        # pyffish-alice uses ``|`` in the placement field to mark pieces that
        # currently occupy the mirror board.
        non_piece = "~+0123456789[]-|"
    elif variant == "orda":
        non_piece = "~+0123456789[]qH-"
    elif variant == "duck":
        non_piece = "~+0123456789[]*-"
    elif variant == "ataxx":
        non_piece = "0123456789*-"
    else:
        non_piece = "~+0123456789[]-"
    invalid1 = any(c not in start[0] + non_piece for c in init[0])

    # Required number of rows
    invalid2 = start[0].count("/") != init[0].count("/")

    # Accept zh FEN in lichess format (they use / instead if [] for pockets)
    if (
        invalid2
        and variant == "crazyhouse"
        and (init[0].count("/") == 8)
        and ("[" not in init[0])
        and ("]" not in init[0])
    ):
        k = init[0].rfind("/")
        init[0] = init[0][:k] + "[" + init[0][k + 1 :] + "]"
        sanitized_fen = " ".join(init)
        invalid2 = False

    # Allowed starting colors
    invalid3 = len(init) > 1 and init[1] not in "bw"

    # ataxx has no kings at all
    if variant in ("ataxx", "borderlands"):
        return True, sanitized_fen

    # Castling rights (and piece virginity) check
    invalid4 = False
    if len(init) > 2:
        if variant in ("seirawan", "shouse"):
            invalid4 = any(c not in "KQABCDEFGHkqabcdefgh-" for c in init[2])
        elif chess960:
            if all(c in "KQkq-" for c in init[2]):
                chess960 = False
            else:
                invalid4 = any(c not in "ABCDEFGHIJabcdefghij-" for c in init[2])
        elif variant[-5:] != "shogi" and variant not in (
            "dobutsu",
            "gorogoro",
            "gorogoroplus",
        ):
            invalid4 = any(c not in start[2] + "-" for c in init[2])

        # Castling right need rooks and king placed in starting square
        if (
            (not invalid2)
            and (not invalid4)
            and not (chess960 and (variant in ("seirawan", "shouse")))
        ):
            rows = init[0].split("/")
            backRankB = rows[1] if (variant == "shako") else rows[0]
            backRankW = rows[-2] if (variant == "shako") else rows[-1]
            # cut off pockets
            k = backRankW.rfind("[")
            if k > 0:
                backRankW = backRankW[:k]
            rookPosQ = 1 if (variant == "shako") else 0
            rookPosK = -2 if (variant == "shako") else -1
            if (
                ("q" in init[2] and backRankB[rookPosQ] != "r")
                or ("k" in init[2] and backRankB[rookPosK] != "r")
                or ("Q" in init[2] and backRankW[rookPosQ] != "R")
                or ("K" in init[2] and backRankW[rookPosK] != "R")
            ):
                invalid4 = True

    # Number of kings
    if variant == "dobutsu":
        bking = "l"
    elif variant == "xiangfu":
        bking = "g"
    else:
        bking = "k"

    if variant == "dobutsu":
        wking = "L"
    elif variant == "xiangfu":
        wking = "+G"
    else:
        wking = "K"

    bK = init[0].count(bking)
    wK = init[0].count(wking)
    if variant == "spartan":
        invalid5 = bK == 0 or bK > 2 or wK != 1
    elif variant == "xiangfu":
        invalid5 = bK == 0 or bK > 2 or wK == 0 or wK > 2
    elif variant == "horde":
        invalid5 = bK != 1 or wK != 0
    else:
        invalid5 = bK != 1 or wK != 1

    # Opp king already in check
    invalid6 = False
    if variant == "racingkings":
        board = FairyBoard(variant, " ".join(init), chess960)
        invalid6 = board.is_checked()
    if not (invalid0 or invalid1 or invalid2 or invalid3 or invalid4 or invalid5 or invalid6):
        curr_color = init[1]
        opp_color = "w" if curr_color == "b" else "b"
        init[1] = init[1].replace(curr_color, opp_color)
        board = FairyBoard(variant, " ".join(init), chess960)
        invalid6 = board.is_checked()

    if invalid0 or invalid1 or invalid2 or invalid3 or invalid4 or invalid5 or invalid6:
        log.debug(
            "%r %r %r %r %r %r %r",
            invalid0,
            invalid1,
            invalid2,
            invalid3,
            invalid4,
            invalid5,
            invalid6,
        )
        return False, ""
    return True, sanitized_fen


async def get_names(request):
    app_state = get_app_state(request.app)
    names = []
    prefix = request.rel_url.query.get("p")
    if prefix is None:
        return json_response(names)

    prefix = prefix.strip()
    if not USERNAME_PREFIX_RE.fullmatch(prefix):
        return json_response(names)

    # case insensitive _id prefix search
    cursor = app_state.db.user.find(
        {"_id": {"$regex": "^%s" % re.escape(prefix), "$options": "i"}},
        limit=12,
    )
    async for doc in cursor:
        names.append((doc["_id"], doc["title"]))
    return json_response(names)


async def get_blogs(request, tag=None, limit=0):
    app_state = get_app_state(request.app)
    if app_state.db is None:
        return []

    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    user = await app_state.users.get(session_user) if session_user else None
    game_category = effective_game_category(session, user)

    async def enrich_author_titles(blogs: list[dict]) -> list[dict]:
        titles = await app_state.public_users.get_titles(
            str(doc.get("author") or "") for doc in blogs
        )
        for doc in blogs:
            author = str(doc.get("author") or "")
            title = titles.get(author, str(doc.get("author_title") or ""))
            doc["author_title"] = title
            doc["atitle"] = title or str(doc.get("atitle") or "")
        return blogs

    # Prefer migrated site blogs from ublog_post.
    tag_filter = tag.casefold() if isinstance(tag, str) and tag.strip() != "" else None
    site_query: dict[str, object] = {"live": True, "blogType": "site"}
    site_cursor = app_state.db.ublog_post.find(site_query).sort(
        [("sticky", -1), ("publishedAt", -1), ("createdAt", -1)]
    )
    site_blogs: list[dict] = []
    async for raw_doc in site_cursor:
        author = str(raw_doc.get("author") or "")
        author_profile = await app_state.public_users.get_profile(author)
        if author_profile is None or not author_profile.enabled:
            continue

        category = raw_doc.get("category", "all")
        if not category_matches(game_category, category):
            continue
        intro = str(raw_doc.get("intro") or raw_doc.get("subtitle") or "")
        image_alt = str(raw_doc.get("imageAlt") or raw_doc.get("alt") or "")
        tags_raw = raw_doc.get("tags")
        tags = [str(tag) for tag in tags_raw] if isinstance(tags_raw, list) else []
        topics_raw = raw_doc.get("topics")
        topics = (
            [str(topic) for topic in topics_raw]
            if isinstance(topics_raw, list)
            else [tag.lower() for tag in tags]
        )
        if tag_filter is not None:
            tag_match = any(isinstance(t, str) and t.casefold() == tag_filter for t in tags)
            topic_match = any(isinstance(t, str) and t.casefold() == tag_filter for t in topics)
            if not (tag_match or topic_match):
                continue
        site_blogs.append(
            {
                "_id": str(raw_doc.get("legacyBlogId") or raw_doc.get("_id") or ""),
                "post_id": str(raw_doc.get("_id") or ""),
                "title": str(raw_doc.get("title") or ""),
                "intro": intro,
                "subtitle": intro,
                "author": author,
                "date": display_date(raw_doc),
                "image": str(raw_doc.get("image") or ""),
                "image_src": image_src(raw_doc),
                "imageAlt": image_alt,
                "alt": image_alt,
                "tags": tags,
                "topics": topics,
                "category": category,
                "categoryList": category if isinstance(category, list) else [category],
                "isOfficial": bool(raw_doc.get("isOfficial", True)),
                "blogType": "site",
                "url": post_url(raw_doc),
            }
        )
        if limit > 0 and len(site_blogs) >= limit:
            break
    if len(site_blogs) > 0:
        return await enrich_author_titles(site_blogs)

    return []


async def get_notifications(request):
    app_state = get_app_state(request.app)
    page_num = int(request.rel_url.query.get("p", 0))

    # Who made the request?
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({})

    user = await app_state.users.get(session_user)

    notifications = await notification_items_for_user(app_state, user, page_num)

    return json_response(notifications)


async def notification_items_for_user(app_state, user: User, page_num: int = 0):
    if user.notifications is None:
        cursor = app_state.db.notify.find({"notifies": user.username})
        user.notifications = await cursor.to_list(length=100)
    if TYPE_CHECKING:
        assert user.notifications is not None

    if page_num > 0:
        return user.notifications[-(page_num + 1) * NOTIFY_PAGE_SIZE : -page_num * NOTIFY_PAGE_SIZE]

    notifications = user.notifications[-NOTIFY_PAGE_SIZE:]
    if app_state.db is None:
        return notifications

    cursor = app_state.db.inbox_thread.find(
        {
            "users": user.username,
            "deletedBy": {"$ne": user.username},
            "lastMsg.user": {"$ne": user.username},
            "readBy": {"$ne": user.username},
        }
    )
    cursor.sort("updatedAt", -1)
    cursor.limit(NOTIFY_PAGE_SIZE)
    unread_threads = await cursor.to_list(length=NOTIFY_PAGE_SIZE)

    inbox_notifications = []
    for doc in unread_threads:
        users = doc.get("users", [])
        opp = next((u for u in users if u != user.username), None)
        if not opp:
            continue
        last_msg = doc.get("lastMsg", {}) or {}
        created_at = last_msg.get("createdAt") or doc.get("updatedAt") or datetime.now(UTC)
        inbox_notifications.append(
            {
                "type": "inboxMsg",
                "read": False,
                "createdAt": created_at,
                "content": {"id": opp, "opp": opp},
            }
        )

    combined = notifications + inbox_notifications
    combined.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    return combined[:NOTIFY_PAGE_SIZE]


async def notified(request):
    app_state = get_app_state(request.app)

    # Who made the request?
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({})

    user = await app_state.users.get(session_user)
    await user.notified()
    return json_response({})


async def subscribe_notify(request):
    # Compatibility for tabs running the pre-multiplexing client.
    app_state = get_app_state(request.app)
    # Who made the request?
    session = await aiohttp_session.get_session(request)
    session_user = session.get("user_name")
    if session_user is None:
        return json_response({})

    user = await app_state.users.get(session_user)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SSE_SNAPSHOT_QUEUE_MAXSIZE)
    user.notify_channels.add(queue)
    response: web.StreamResponse = web.Response(status=200)
    try:
        async with session_expiry_timeout(session, user), sse_response(request) as response:
            await consume_sse_queue(response, queue)
    except Exception:
        pass
    finally:
        user.notify_channels.discard(queue)
        queue.shutdown(immediate=True)
    return response


def corr_games(games):
    now = datetime.now(UTC)
    return [
        {
            "gameId": game.id,
            "variant": game.variant,
            "fen": DARK_FEN if game.variant == "fogofwar" else game.board.fen,
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
            "date": (now + timedelta(minutes=game.stopwatch.mins)).isoformat(),
        }
        for game in games
    ]


def simul_games(games):
    return [
        {
            "gameId": game.id,
            "variant": game.variant,
            "fen": DARK_FEN if game.variant == "fogofwar" else game.board.fen,
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
            "status": game.status,
            "result": game.result,
            "date": "",
            "mins": 0,
        }
        for game in games
    ]
