from __future__ import annotations

import logging
import random
from collections.abc import Mapping
from datetime import UTC
from time import time_ns
from typing import TYPE_CHECKING

from compress import C2R, R2C
from const import (
    CASUAL,
    RATED,
    STARTED,
)
from convert import zero2grand
from fairy import BLACK, WHITE
from glicko2.glicko2 import gl2
from newid import new_id
from pychess_global_app_state import PychessGlobalAppState
from seek import ANON_RESTRICTED_SEEK_MESSAGE, is_anon_restricted_seek
from utils import (
    REALTIME_GAME_IN_PROGRESS_MESSAGE,
    realtime_game_conflict,
    remove_seek,
    round_broadcast,
    sanitize_fen,
)
from variants import C2V, GRANDS
from websocket_utils import ws_send_json_many

from bug.game_bug import GameBug
from bug.history import replay_history

if TYPE_CHECKING:
    from user import User

log = logging.getLogger(__name__)


async def send_to_team(game: GameBug, team: list[str], response: Mapping[str, object]) -> None:
    """Deliver to the two players on one team and to nobody else.

    Deliberately not round_broadcast: that reaches the opposing team and the spectators,
    and a pending resignation is the resigning team's own business. Knowing that your
    opponents are considering resignation is information about how they judge the
    position, and handing it over mid-game changes the game.
    """
    for player in game.non_bot_players:
        if player.username in team:
            await player.send_game_message(game.id, response)


async def cancel_team_offers_on_move(game: GameBug, user: User) -> None:
    """Playing on is an answer, and it answers both kinds of offer.

    A move by either teammate cancels their pending resignation — the player who asked has
    changed their mind, the partner has declined without needing a control for it. A move
    by either opponent declines an outstanding draw offer on behalf of their team.

    Done here rather than in the client so it holds however the move arrived, and so all
    four windows learn of it from one broadcast instead of each deciding for itself.
    """
    team = game.team_of(user.username)
    if team is None:
        return

    if game.resign_offer is not None and game.resign_offer in team:
        game.resign_offer = None
        await send_to_team(
            game, team, {"type": "resign_cancelled", "message": "Resignation cancelled"}
        )

    if game.draw_offer_team is not None and game.draw_offer_team is not team:
        game.draw_offer_team = None
        await round_broadcast(
            game, {"type": "draw_rejected", "message": "Draw offer rejected"}, full=True
        )


async def init_players(app_state: PychessGlobalAppState, wp_a, bp_a, wp_b, bp_b):
    wplayer_a = await app_state.users.get(wp_a)
    wplayer_b = await app_state.users.get(wp_b)
    bplayer_a = await app_state.users.get(bp_a)
    bplayer_b = await app_state.users.get(bp_b)
    return [wplayer_a, bplayer_a, wplayer_b, bplayer_b]


async def load_game_bug_from_doc(
    app_state: PychessGlobalAppState, doc, *, cache_finished: bool = True
):
    """Return GameBug object from app cache or an already fetched document."""
    game_id = doc["_id"]
    if game_id in app_state.games:
        return app_state.games[game_id]

    log.debug("load_game_bug parse START")

    wp, bp, wp_b, bp_b = doc["us"]
    wplayer, bplayer, wplayer_b, bplayer_b = await init_players(app_state, wp, bp, wp_b, bp_b)

    variant = C2V[doc["v"]]

    initial_fen = doc.get("if")

    game = GameBug(
        app_state,
        game_id,
        variant,
        initial_fen,
        wplayer,
        bplayer,
        wplayer_b,
        bplayer_b,
        base=doc["b"],
        inc=doc["i"],
        level=doc.get("x"),
        rated=doc.get("y"),
        chess960=bool(doc.get("z")),
        create=False,
        tournamentId=doc.get("tid"),
    )

    decode_method = game.server_variant.move_decoding
    mlist = [*map(decode_method, doc["m"])]

    if variant in GRANDS:
        mlist = [*map(zero2grand, mlist)]

    # `doc["s"] > STARTED` GOVERNS BOTH SIDES, as it does on the one-board path (`utils.py`). The
    # brackets used to sit the other way round, so a non-empty move list ALONE marked the game
    # saved. That was harmless only because bughouse never persisted moves mid-game: `doc["m"]` was
    # always `[]` for a game in progress, so the first clause was never true for one.
    #
    # Per-ply persistence makes it true for every restored game, and `save_game()` opens with
    # `if self.saved: return` — so a game that came back from a restart would silently refuse to
    # write its own ending: no result, no ratings, no final clock arrays. Found by asking what else
    # changes meaning once `m` is non-empty mid-game, not by seeing it happen.
    if (mlist or game.tournamentId is not None) and doc["s"] > STARTED:
        game.saved = True

    if doc.get("a"):
        game.steps[0]["analysis"] = doc["a"][0]
    root_chat = (doc.get("c") or {}).get("m0")
    if root_chat is not None:
        game.steps[0]["chat"] = [
            {"message": entry["m"], "username": entry["u"], "time": entry["t"]}
            for entry in root_chat
        ]

    final_fen = doc.get("f")
    if doc["s"] > STARTED and isinstance(final_fen, str) and "|" in final_fen:
        # A finished archive needs only its final authoritative state on the server.
        # Native history replay is reserved for explicit backend consumers.
        game._history_doc = {
            key: doc[key]
            for key in ("o", "s", "a", "c", "cw", "cb", "cwB", "cbB", "ts")
            if key in doc
        }
        game._history_moves = mlist
        for board_name, fen in zip(("a", "b"), final_fen.split("|"), strict=True):
            board = game.boards[board_name]
            board.fen = fen.strip()
            board.move_stack = [
                move
                for index, move in enumerate(mlist)
                if ("a" if doc["o"][index] == 0 else "b") == board_name
            ]
            board.ply = len(board.move_stack)
            board.color = WHITE if board.fen.split()[1] == "w" else BLACK
        game.checkA = game.boards["a"].is_checked()
        game.checkB = game.boards["b"].is_checked()
        game.lastmove = mlist[-1] if mlist else None
    else:
        # Active games and archives without a stored final position require replay.
        restored_last_move_clocks, restored_last_move_ts = replay_history(game, doc, mlist)

    level = doc.get("x")
    game.date = doc["d"]
    if game.date.tzinfo is None:
        game.date = game.date.replace(tzinfo=UTC)
    game.status = doc["s"]
    game.level = level if level is not None else 0
    game.result = C2R[doc["r"]]
    if game.status <= STARTED:
        # Hand the rebuilt clock state back to the game and start both boards ticking, charging
        # each side to move for the wall-clock time that passed while the server was down. Done
        # here rather than at the caller so that EVERY load path gets it — the startup restore of
        # active games and an on-demand load from a game URL alike. Must come after `game.date` is
        # read above, which is the fallback turn start for a board nobody has moved on.
        game.gameClocks.last_move_clocks["a"] = restored_last_move_clocks["a"]
        game.gameClocks.last_move_clocks["b"] = restored_last_move_clocks["b"]
        game.gameClocks.restore_after_load(restored_last_move_ts, time_ns())

        for player in game.non_bot_players:
            player.game_in_progress = game.id
    else:
        for player in game.non_bot_players:
            if player.game_in_progress == game.id:
                player.game_in_progress = None

    try:
        game.wrating_a = doc["p0"]["e"]
        game.brating_a = doc["p1"]["e"]
        game.wrating_b = doc["p2"]["e"]
        game.brating_b = doc["p3"]["e"]
    except KeyError:
        game.wrating_a = "1500?"
        game.brating_a = "1500?"
        game.wrating_b = "1500?"
        game.brating_b = "1500?"

    game.white_rating = gl2.create_rating(int(game.wrating.rstrip("?")))
    game.black_rating = gl2.create_rating(int(game.brating.rstrip("?")))

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

    if doc.get("by") is not None:
        game.imported_by = doc.get("by")

    if game.status > STARTED:
        # Finished bughouse games loaded from DB should not keep their clock
        # tasks running; cancel them immediately to prevent leaks.
        await game.gameClocks.cancel_stopwatches()

    if game.status <= STARTED or cache_finished:
        app_state.games[game_id] = game
        if game.status > STARTED:
            app_state.schedule_game_cache_removal(game)
    log.debug("load_game_bug parse DONE")

    return game


async def new_game_bughouse(app_state: PychessGlobalAppState, seek_id, game_id=None):
    seek = app_state.seeks[seek_id]

    if seek.fen:
        fen_valid, sanitized_fen = sanitize_fen(seek.variant, seek.fen, seek.chess960)
        if not fen_valid:
            message = "Failed to create game. Invalid FEN %s" % seek.fen
            log.debug(message)
            remove_seek(app_state.seeks, seek)
            return {"type": "error", "message": message}
    else:
        sanitized_fen = ""

    color = random.choice(("w", "b")) if seek.color == "r" else seek.color
    wplayer, bug_bplayer = (
        (seek.player1, seek.bugPlayer1) if color == "w" else (seek.player2, seek.bugPlayer2)
    )
    bplayer, bug_wplayer = (
        (seek.player1, seek.bugPlayer1) if color == "b" else (seek.player2, seek.bugPlayer2)
    )

    await app_state.realtime_game_creation_lock.acquire()
    try:
        conflict = realtime_game_conflict(app_state, (wplayer, bplayer, bug_wplayer, bug_bplayer))
        if conflict is not None:
            return {"type": "error", "message": REALTIME_GAME_IN_PROGRESS_MESSAGE}

        if game_id is not None:
            # game invitation
            app_state.invites.pop(game_id, None)
        else:
            game_id = await new_id(None if app_state.db is None else app_state.db.game)

        # print("new_game", game_id, seek.variant, seek.fen, wplayer, bplayer, seek.base, seek.inc, seek.level, seek.rated, seek.chess960)
        if TYPE_CHECKING:
            assert seek.chess960 is not None
        any_bot_player = wplayer.bot or bplayer.bot or bug_wplayer.bot or bug_bplayer.bot
        game = GameBug(
            app_state,
            game_id,
            seek.variant,
            sanitized_fen,
            wplayer,
            bplayer,
            bug_wplayer,
            bug_bplayer,
            base=seek.base,
            inc=seek.inc,
            level=seek.level,
            rated=(
                CASUAL
                if any_bot_player
                else RATED
                if (seek.rated and (not wplayer.anon) and (not bplayer.anon))
                else CASUAL
            ),
            chess960=seek.chess960,
            create=True,
            new_960_fen_needed_for_rematch=seek.reused_fen,
        )
        app_state.games[game_id] = game
    except Exception:
        log.exception(
            "Creating new BugHouse game %s failed! %s 960:%s FEN:%s %s+%s vs %s+%s",
            game_id,
            seek.variant,
            seek.chess960,
            seek.fen,
            wplayer,
            bug_bplayer,
            bug_wplayer,
            bplayer,
        )

        remove_seek(app_state.seeks, seek)
        return {"type": "error", "message": "Failed to create game"}
    finally:
        app_state.realtime_game_creation_lock.release()

    remove_seek(app_state.seeks, seek)

    await insert_game_to_db_bughouse(game, app_state)

    return {
        "type": "new_game",
        "gameId": game_id,
        "wplayer": wplayer.username,
        "bplayer": bplayer.username,
        "bug_wplayer": bug_wplayer.username,
        "bug_bplayer": bug_bplayer.username,
    }


async def insert_game_to_db_bughouse(game: GameBug, app_state: PychessGlobalAppState):
    # unit test app may have no db
    if app_state.db is None:
        return

    document = {
        "_id": game.id,
        "us": [
            game.wplayerA.username,
            game.bplayerA.username,
            game.wplayerB.username,
            game.bplayerB.username,
        ],
        "p0": {"e": game.wrating_a},
        "p1": {"e": game.brating_a},
        "p2": {"e": game.wrating_b},
        "p3": {"e": game.brating_b},
        "v": game.server_variant.code,
        "b": game.base,
        "i": game.inc,
        # "bp": game.byoyomi_period,
        "m": [],
        # SEEDED SO THE PER-PLY WRITER CAN JUST $push. `o` is index-for-index with `m`; the four
        # clock arrays and `ts` each carry one extra leading entry for the initial position, which
        # is the offset `load_game_bug_from_doc()` relies on when it reads `clocktimes[ply + 1]`.
        # Written from the same sources `save_game()` uses, so an in-progress document has the
        # exact shape a finished one does.
        "o": [],
        "ts": [x["ts"] for x in game.steps],
        "cw": game.gameClocks.get_ply_clocks_for_board_and_color("a", WHITE),
        "cb": game.gameClocks.get_ply_clocks_for_board_and_color("a", BLACK),
        "cwB": game.gameClocks.get_ply_clocks_for_board_and_color("b", WHITE),
        "cbB": game.gameClocks.get_ply_clocks_for_board_and_color("b", BLACK),
        "d": game.date,
        "f": game.initial_fen,
        "s": game.status,
        "r": R2C["*"],
        "x": game.level,
        "y": int(game.rated),
        "z": int(game.chess960),
    }

    if game.tournamentId is not None:
        document["tid"] = game.tournamentId

    if game.initial_fen or game.chess960:
        document["if"] = game.initial_fen

    # if game.variant.endswith("shogi") or game.variant in (
    #     "dobutsu",
    #     "gorogoro",
    #     "gorogoroplus",
    # ):
    #     document["uci"] = 1

    result = await app_state.db.game.insert_one(document)
    if not result:
        log.error("db insert game result %s failed !!!", game.id)

    app_state.tv = game.id
    game.wplayerA.tv = game.id
    game.bplayerA.tv = game.id
    game.wplayerB.tv = game.id
    game.bplayerB.tv = game.id


async def join_seek_bughouse(
    app_state: PychessGlobalAppState, user, seek_id, game_id=None, join_as="any"
):
    seek = app_state.seeks[seek_id]

    conflict = realtime_game_conflict(
        app_state,
        (seek.player1, seek.player2, seek.bugPlayer1, seek.bugPlayer2, user),
    )
    if conflict is not None:
        return {"type": "error", "message": REALTIME_GAME_IN_PROGRESS_MESSAGE}

    log.info(
        "+++ BUGHOUSE Seek %s joined by %s FEN:%s 960:%s",
        seek_id,
        user.username if user else None,
        seek.fen,
        seek.chess960,
    )

    if user is not None and is_anon_restricted_seek(user, seek.variant, seek.chess960, seek.day):
        return {"type": "error", "message": ANON_RESTRICTED_SEEK_MESSAGE}

    if (
        join_as == "player1"
    ):  # todo: not really possible at the moment - should implement possibility of unseating a slot and somehow
        #       allowing the player who created the challenge to sit back in another slot or just remove this case and
        #       dont bother supporting such complex scenarios
        if seek.player1 is None:
            seek.player1 = user
        else:
            return {"type": "seek_occupied", "seekID": seek_id}
    elif join_as == "player2":
        if seek.player2 is None:
            seek.player2 = user
        else:
            return {"type": "seek_occupied", "seekID": seek_id}
    elif join_as == "bugPlayer1":
        if seek.bugPlayer1 is None:
            seek.bugPlayer1 = user
        else:
            return {"type": "seek_occupied", "seekID": seek_id}
    elif join_as == "bugPlayer2":
        if seek.bugPlayer2 is None:
            seek.bugPlayer2 = user
        else:
            return {"type": "seek_occupied", "seekID": seek_id}

    if (
        seek.player1 is not None
        and seek.player2 is not None
        and seek.bugPlayer1 is not None
        and seek.bugPlayer2 is not None
    ):
        return await new_game_bughouse(app_state, seek_id, game_id)
    else:
        return {"type": "seek_joined", "seekID": seek_id}


async def play_move(
    app_state: PychessGlobalAppState,
    user,
    game,
    move,
    clocks=None,
    clocks_b=None,
    board=None,
):
    log.debug(
        "play_move %r %r %r %r %r %r",
        user,
        game,
        move,
        clocks,
        clocks_b,
        board,
    )
    gameId = game.id
    # log.info("%s move %s %s %s - %s" % (user.username, move, gameId, game.wplayer.username, game.bplayer.username))

    # Playing on answers any offer this player's move speaks to — their team's pending
    # resignation, or the other team's draw offer. Before the move is applied, so a move
    # that ends the game still leaves no offer outstanding behind it.
    await cancel_team_offers_on_move(game, user)

    if game.status <= STARTED:
        try:
            if (
                game.lastmovePerBoardAndUser[board].get(user.username) != move
            ):  # in case of resending after reconnect we can get same move sent multiple times from client
                await game.play_move(move, clocks, clocks_b, board)
            else:
                log.debug("move already played - probably resent twice after multiple reconnects")
                return
        # BARE `Exception`, NOT `SystemError`. `GameBug.play_move()` re-raises whatever the engine
        # threw, and that is a `ValueError` for an unparseable move with a `SystemError` chained
        # behind it — catching only the latter let a live illegal move fall through to the caller
        # while every automated test passed.
        except Exception:  # noqa: BLE001 - the engine's refusals are not one exception type
            # A MOVE THE ENGINE REFUSES NO LONGER ENDS THE GAME. It ends the disagreement instead:
            # the sender is handed the position as the server holds it, and their client resets to
            # it, which is what stops a second impossible move following the first.
            #
            # Ending the game was a heavy answer to a light problem. A player whose move is refused
            # is a player whose picture of the position is stale — after a reconnection, after a
            # move that crossed with someone else's, after a page that came back holding a move it
            # had not sent. None of that is cheating and none of it is worth a loss.
            #
            # WHAT THIS GIVES UP: nothing now costs anything to a client that sends refused moves in
            # a loop, where before the first one stopped the game. The client is expected to drop a
            # waiting move it can see is not playable in the position it has just been given; a
            # client that does not is merely noisy.
            #
            # Only the sender is told. Nobody else's picture changed — the move was not played.
            log.warning(
                "Game %s refused invalid move %s by %s; resyncing that client",
                gameId,
                move,
                user.username,
            )
            await user.send_game_message(gameId, game.get_board(full=True))
            return
    else:
        # never play moves in finished games!
        return

    board_response = game.get_board()
    await round_broadcast(game, board_response, full=True, channels=app_state.game_channels)

    if game.status > STARTED:
        response = {
            "type": "gameEnd",
            "status": game.status,
            "result": game.result,
            "gameId": gameId,
            "pgn": game.pgn,
        }
        for u in set(game.non_bot_players):
            await u.send_game_message(gameId, response)

        if app_state.tv == gameId:
            await app_state.lobby.lobby_broadcast(board_response)


async def handle_accept_seek_bughouse(app_state: PychessGlobalAppState, user, data, seek):
    if user.anon:
        return
    response = await join_seek_bughouse(app_state, user, data["seekID"], None, data["joinAs"])
    bug_users = set(
        filter(
            lambda item: item is not None,
            [seek.player1, seek.player2, seek.bugPlayer1, seek.bugPlayer2],
        )
    )
    for u in bug_users:
        await ws_send_json_many(u.lobby_sockets, response)
    await app_state.lobby.lobby_broadcast_seeks()


async def handle_leave_seek_bughouse(app_state: PychessGlobalAppState, user, seek):
    if seek.player2 == user:
        seek.player2 = None
    if seek.bugPlayer1 == user:
        seek.bugPlayer1 = None
    if seek.bugPlayer2 == user:
        seek.bugPlayer2 = None
    await app_state.lobby.lobby_broadcast_seeks()
