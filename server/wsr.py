from __future__ import annotations

import asyncio
import random
import string
from collections.abc import Mapping
from typing import TYPE_CHECKING

import aiohttp_session
import game
from aiohttp import web
from aiohttp.web_ws import WebSocketResponse
from broadcast import round_broadcast
from bug.wsr_bug import (
    handle_draw_bughouse,
    handle_reconnect_bughouse,
    handle_reject_draw_bughouse,
    handle_reject_rematch_bughouse,
    handle_rematch_bughouse,
    handle_resign_bughouse,
)
from catalogued_variants import catalogued_variant_allows_fishnet
from chat import chat_response
from cheat_report import (
    CEVAL_REPORT_ACTION_AUTO_FORFEIT,
    CEVAL_REPORT_ACTION_REPORTED_ONLY,
    append_ceval_cheat_report,
    ceval_auto_lose_enabled,
)
from const import ANALYSIS, ANON_PREFIX, CASUAL, IMPORTED, STARTED
from draw import draw, reject_draw
from fairy import BLACK, WHITE, FairyBoard
from fishnet import (
    drop_stale_analysis_work,
    fishnet_variant_requires_capability,
    has_available_fishnet_worker,
    has_pending_analysis_work_for_game,
)
from link_filter import sanitize_user_message
from newid import new_id

if TYPE_CHECKING:
    from bug.game_bug import GameBug
    from clock import Clock
    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
    from pymongo.asynchronous.database import AsyncDatabase
    from user import User
    from users import Users
    from ws_types import (
        AbortResignMessage,
        AnalysisMessage,
        AnalysisMoveMessage,
        BerserkMessage,
        BugRoundChatMessage,
        ByoyomiMessage,
        CevalDetectedMessage,
        ChatMessage,
        CountMessage,
        CountResponse,
        DeletedMessage,
        DrawMessage,
        EmbedUserConnectedMessage,
        FullChatMessage,
        GameStartMessage,
        GameUserConnectedMessage,
        LeaveMessage,
        MoreTimeMessage,
        MoreTimeRequest,
        MoveMessage,
        ReadyMessage,
        RematchMessage,
        RematchOfferMessage,
        RematchRejectedMessage,
        RequestAnalysisMessage,
        RoundChatMessage,
        RoundInboundMessage,
        SetupMessage,
        SetupResponse,
        UpdateTVMessage,
        UserPresenceMessage,
        ViewRematchMessage,
    )
import logging

import logger
from bug.utils_bug import play_move as play_move_bug
from json_utils import json_dumps
from pychess_global_app_state_utils import get_app_state
from seek import Seek
from utils import (
    analysis_move,
    join_seek,
    load_game,
    play_move,
    remove_seek,
    send_bot_game_start_unless_streaming,
    tv_game,
    tv_game_user,
)
from websocket_utils import get_user, process_ws, ws_send_json
from ws_structs import ROUND_TYPED_DECODERS
from ws_types import BughouseMoveMessage, MoveMessage, RoundInboundMessage

log = logging.getLogger(__name__)

MORE_TIME = 15 * 1000
# NOTE ABOUT FLAG CLAIM TIMING:
# - The browser clock is continuous and can hit 0 between server updates.
# - The server countdown clock is quantized (updated in 1s steps in Clock.countdown()).
# - Therefore a valid client "flag" claim may arrive while server stopwatch.secs
#   is still slightly positive (typically < 1 second) until the next server tick.
# We accept a small tolerance window ONLY to avoid rejecting such legitimate claims.
# This does not allow arbitrary early flags because _flag_claim_allowed() also
# enforces that the claimant is the side to move and verifies server-side timing.
CLIENT_FLAG_TOLERANCE_MS = 1000
MIN_CEVAL_REPORT_PLY = 6
MIN_CEVAL_REPORT_PLY_CHESS960 = 1


def min_ceval_report_ply(game: game.Game) -> int:
    return MIN_CEVAL_REPORT_PLY_CHESS960 if bool(game.chess960) else MIN_CEVAL_REPORT_PLY


def _flag_claim_allowed(game: game.Game, user: User) -> bool:
    # Only players can claim flag, and only for the side to move.
    if user.username == game.wplayer.username:
        user_color = WHITE
    elif user.username == game.bplayer.username:
        user_color = BLACK
    else:
        return False

    if game.board.color != user_color:
        return False

    # Client "flag" claims are only meaningful for real-time games.
    if game.corr:
        return False

    # In first-move timeout and byoyomi, rely on the live stopwatch state.
    # For these modes we cannot reliably reconstruct elapsed-time from the
    # saved move clocks alone, so we read stopwatch.secs directly.
    #
    # We intentionally allow a small positive remainder (<= tolerance) because
    # of the 1s server tick granularity explained above. Also require the
    # stopwatch to be running, so casual first-move games (no running timeout)
    # cannot be spuriously flagged.
    if TYPE_CHECKING:
        assert isinstance(game.stopwatch, Clock)
    if game.ply < 2 or game.byoyomi:
        return game.stopwatch.running and game.stopwatch.secs <= CLIENT_FLAG_TOLERANCE_MS

    # In normal increment games we compute authoritative remaining time from:
    #   remaining = saved_clock_after_last_move - elapsed_since_last_move
    # where elapsed uses durable wall-clock restart time plus the current
    # process's monotonic time when exact clock history is available. This
    # avoids trusting client clock values and tolerance-based false positives.
    saved = game.clocks_w[-1] if user_color == WHITE else game.clocks_b[-1]
    elapsed = game.authoritative_clock_elapsed_ms()
    return (saved - elapsed) <= 0


async def round_socket_handler(request: web.Request) -> web.StreamResponse:
    gameId = request.match_info["gameId"]
    app_state = get_app_state(request.app)
    game = await load_game(app_state, gameId)
    if game is None:
        return web.HTTPNotFound()
    if TYPE_CHECKING:
        assert isinstance(game, Game)

    session = await aiohttp_session.get_session(request)
    user = await get_user(session, request)
    logger.set_log_context("username", user.username)
    logger.set_log_context("gameId", game.id)

    async def process_message_wrapper(
        app_state: PychessGlobalAppState,
        user: User,
        ws: WebSocketResponse,
        data: RoundInboundMessage,
    ) -> None:
        await process_message(app_state, user, ws, data, game)

    ws = await process_ws(
        session,
        request,
        user,
        lambda app_state, ws, user: init_ws(app_state, ws, user, game),
        process_message_wrapper,
        typed_decoders=ROUND_TYPED_DECODERS,
    )
    if ws is None:
        return web.HTTPFound("/")
    await finally_logic(app_state, ws, user, game)
    return ws


async def init_ws(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    game: game.Game,
) -> None:
    for p in game.non_bot_players:
        if p.username != user.username:
            await handle_is_user_present(ws, app_state.users, p.username, game)
    await handle_game_user_connected(app_state, ws, user, game)
    await handle_board(ws, user, game)


async def process_message(
    app_state: PychessGlobalAppState,
    user: User,
    ws: WebSocketResponse,
    data: RoundInboundMessage,
    game: game.Game,
) -> None:
    if data["type"] == "move":
        await handle_move(app_state, user, data, game)
    elif data["type"] == "reconnect":
        if TYPE_CHECKING:
            assert isinstance(game, GameBug)
        await handle_reconnect_bughouse(app_state, user, data, game)
    elif data["type"] == "berserk":
        await handle_berserk(data, game)
    elif data["type"] == "analysis_move":
        await handle_analysis_move(user, data, game)
    elif data["type"] == "ready":
        await handle_ready(ws, app_state.users, user, data, game)
    elif data["type"] == "board":
        await handle_board(ws, user, game)
    elif data["type"] == "setup":
        await handle_setup(ws, app_state.users, user, data, game)
    elif data["type"] == "analysis":
        await handle_analysis(app_state, ws, data, game)
    elif data["type"] == "rematch":
        if not game.server_variant.two_boards and game.simulId is not None:
            await ws_send_json(ws, {"type": "error", "message": "Rematches are disabled in simuls"})
            return
        await handle_rematch(app_state, ws, user, data, game)
    elif data["type"] == "reject_rematch":
        # In bughouse this means "take my own offer back", not "decline yours" — the
        # answering side has a single ACCEPT control and declining is just not pressing it.
        if game.server_variant.two_boards:
            if TYPE_CHECKING:
                assert isinstance(game, GameBug)
            await handle_reject_rematch_bughouse(game, user)
        else:
            await handle_reject_rematch(user, game)
    elif data["type"] == "draw":
        # Bughouse branch, the same shape abort/resign use below. A draw there is offered
        # to the opposing TEAM and answerable by either of its members, which the shared
        # handler cannot express: it derives one opponent from wplayer/bplayer — board A's
        # two seats — and broadcasts without full=True, so two of the four players never
        # heard the offer at all.
        if game.server_variant.two_boards:
            if TYPE_CHECKING:
                assert isinstance(game, GameBug)
            await handle_draw_bughouse(game, user)
        else:
            await handle_draw(ws, app_state.users, user, data, game)
    elif data["type"] == "reject_draw":
        if game.server_variant.two_boards:
            if TYPE_CHECKING:
                assert isinstance(game, GameBug)
            await handle_reject_draw_bughouse(game, user)
        else:
            await handle_reject_draw(user, game)
    elif data["type"] == "byoyomi":
        await handle_byoyomi(user, data, game)
    elif data["type"] == "takeback":
        if not game.server_variant.two_boards and game.simulId is not None:
            await ws_send_json(ws, {"type": "error", "message": "Takebacks are disabled in simuls"})
            return
        await handle_takeback(ws, user, game)
    elif data["type"] == "reject_takeback":
        await handle_reject_takeback(user, game)
    elif (
        data["type"] == "abort"
        or data["type"] == "resign"
        or data["type"] == "abandon"
        or data["type"] == "flag"
    ):
        if game.server_variant.two_boards:
            if TYPE_CHECKING:
                assert isinstance(game, GameBug)
            await handle_resign_bughouse(data, game, user)
        else:
            await handle_abort_resign_abandon_flag(ws, app_state.users, user, data, game)
    elif data["type"] == "embed_user_connected":
        await handle_embed_user_connected(ws)
    elif data["type"] == "is_user_present":
        await handle_is_user_present(ws, app_state.users, data["username"], game)
    elif data["type"] == "moretime":
        if not game.server_variant.two_boards and game.simulId is not None:
            await ws_send_json(
                ws, {"type": "error", "message": "Adding time is disabled in simuls"}
            )
            return
        await handle_moretime(app_state.users, user, data, game)
    elif data["type"] == "bugroundchat":
        if TYPE_CHECKING:
            assert isinstance(game, GameBug)
        await handle_bugroundchat(app_state.users, user, data, game)
    elif data["type"] == "roundchat":
        await handle_roundchat(app_state, ws, user, data, game)
    elif data["type"] == "leave":
        await handle_leave(user, data, game)
    elif data["type"] == "updateTV":
        await handle_updateTV(app_state, ws, data)
    elif data["type"] == "ceval_detected":
        await handle_ceval_detected(ws, app_state.users, user, data, game)
    elif data["type"] == "count":
        await handle_count(ws, user, data, game)
    elif data["type"] == "delete":
        await handle_delete(app_state.db, ws, user, game)


async def finally_logic(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    game: game.Game,
) -> None:
    if game is not None and user is not None and not user.bot:
        if user.remove_ws_for_game(game.id, ws):
            user.update_online()

        # "Is this user a player here?" — `non_bot_players` answers it for both game types:
        # two entries for one board, and for bughouse a SET of the four seats' users, so a simul's
        # doubled seat collapses to one. The old test named `game.wplayer`/`game.bplayer`, which on
        # a GameBug are board A's pair, so a board B player was misfiled as a departing spectator
        # and NO abandon task was ever created — the game simply never ended. Bots cannot reach
        # here (the enclosing `not user.bot`), so excluding them changes nothing for one board.
        if user in game.non_bot_players and (not game.corr):
            task = asyncio.create_task(
                user.abandon_game(game), name="abandone-game-%s-%s" % (user.username, game.id)
            )
            user.abandon_game_tasks[game.id] = task
            task.add_done_callback(lambda task: user.abandon_task_done(task, game.id))
        else:
            game.spectators.discard(user)
            user.watched_games.discard(game.id)
            # The disconnecting websocket handler can be cancelled before this broadcast
            # finishes. A user-owned background task keeps it alive so remaining viewers
            # receive the updated spectator list.
            user.create_background_task(
                round_broadcast(game, game.spectator_list, full=True),
                name="spectators-left-%s-%s" % (user.username, game.id),
            )

        # not connected to any other game socket after we closed this one. maybe we havae a change of online users count
        if not user.is_user_active_in_game() and not user.is_user_active_in_lobby():
            await app_state.lobby.lobby_broadcast_u_cnt()

    if game is not None and user is not None:
        response: UserPresenceMessage = {"type": "user_disconnected", "username": user.username}
        await round_broadcast(game, response, full=True)

    if game is not None:
        await app_state.maybe_remove_finished_game_from_cache_now(game)


async def handle_move(
    app_state: PychessGlobalAppState,
    user: User,
    data: MoveMessage | BughouseMoveMessage,
    game: game.Game,
) -> None:
    log.debug("Got USER move %s %s %s" % (user.username, data["gameId"], data["move"]))
    async with game.move_lock:
        if game.server_variant.two_boards:
            try:
                if TYPE_CHECKING:
                    assert "board" in data
                    assert "clocksB" in data
                bug_data: BughouseMoveMessage = data  # type: ignore[assignment]
                await play_move_bug(
                    app_state,
                    user,
                    game,
                    bug_data["move"],
                    bug_data["clocks"],
                    bug_data["clocksB"],
                    # data["ply"],todo:dont even send it maybe
                    bug_data["board"],
                )
            except Exception:
                log.exception(
                    "ERROR: Exception in play_move() in %s by %s. data %r ",
                    data["gameId"],
                    user.username,
                    data,
                )
        else:
            try:
                await play_move(
                    app_state,
                    user,
                    game,
                    data["move"],
                    data["clocks"],
                    data["ply"],
                    data.get("positionId"),
                )
            except Exception:
                log.exception(
                    "ERROR: Exception in play_move() in %s by %s ",
                    data["gameId"],
                    user.username,
                )


async def handle_berserk(data: BerserkMessage, game: game.Game) -> None:
    # Berserk can race with the first move. Serialize both operations and make
    # the durable write happen before clients are told that berserk succeeded.
    # A process death after the broadcast can therefore never make an
    # acknowledged berserk disappear after restart.
    async with game.move_lock:
        # If the first move won the lock, the berserk request is too late. This
        # mirrors the client rule (berserk is offered only before game start)
        # and makes the move/berserk race deterministic in either order.
        if game.status >= STARTED:
            return
        game.berserk(data["color"])
        await game.save_berserk()
        response: BerserkMessage = {"type": "berserk", "color": data["color"]}
        await round_broadcast(game, response, full=True)


async def handle_analysis_move(user: User, data: AnalysisMoveMessage, game: game.Game) -> None:
    await analysis_move(
        user,
        game,
        data["move"],
        data["fen"],
        data["ply"],
    )


async def handle_ready(
    ws: WebSocketResponse,
    users: Users,
    user: User,
    data: ReadyMessage,
    game: game.Game,
) -> None:
    opp_name = (
        game.wplayer.username if user.username == game.bplayer.username else game.bplayer.username
    )
    opp_player = await users.get(opp_name)
    response: GameStartMessage = {"type": "gameStart", "gameId": data["gameId"]}
    if opp_player is not None and opp_player.bot:
        # Do NOT send game.game_start here!
        # Bot games are already started by challenge_accept/create-ai/rematch/etc.
        # Sending it again starts a second pychess-bot worker for the same game.
        # if should_send_game_start_to_bot(game):
        #     await opp_player.event_queue.put(game.game_start)

        await ws_send_json(ws, response)
    else:
        await ws_send_json(ws, response)

        await round_broadcast(game, game.spectator_list, full=True)


async def handle_board(ws: WebSocketResponse, user: User, game: game.Game) -> None:
    if game.server_variant.two_boards:
        user_color = WHITE if user == game.wplayer else BLACK if user == game.bplayer else None
        board_response = game.get_board(full=True, persp_color=user_color, client_history=True)
        await ws_send_json(ws, board_response)
    elif game.variant == "janggi":
        # print("JANGGI", ws, game.bsetup, game.wsetup, game.status)
        if (game.bsetup or game.wsetup) and game.status <= STARTED:
            setup_response: SetupResponse
            if game.bsetup:
                setup_response = {
                    "type": "setup",
                    "color": "black",
                    "fen": game.board.initial_fen,
                }
                await ws_send_json(
                    ws,
                    setup_response,
                )
            elif game.wsetup:
                setup_response = {
                    "type": "setup",
                    "color": "white",
                    "fen": game.board.initial_fen,
                }
                await ws_send_json(
                    ws,
                    setup_response,
                )
        else:
            board_response = game.get_board(full=True, client_history=True)
            await ws_send_json(ws, board_response)
    else:
        user_color = WHITE if user == game.wplayer else BLACK if user == game.bplayer else None
        board_response = game.get_board(full=True, persp_color=user_color, client_history=True)
        await ws_send_json(ws, board_response)

    if game.corr and game.status <= STARTED and len(game.draw_offers) > 0:
        offerer = game.wplayer if game.wplayer.username in game.draw_offers else game.bplayer
        response = await draw(game, offerer)
        await ws_send_json(ws, response)

    if game.is_player(user) and game.takeback_offer is not None:
        offerer_name, _offer_ply = game.takeback_offer
        await ws_send_json(
            ws,
            {
                "type": "takeback_offer",
                "username": offerer_name,
                "message": "Takeback offer sent",
            },
        )


async def handle_setup(
    ws: WebSocketResponse,
    users: Users,
    user: User,
    data: SetupMessage,
    game: game.Game,
) -> None:
    # Janggi game starts with a prelude phase to set up horses and elephants
    # First the second player (Red) chooses his setup! Then the first player (Blue)
    async with game.move_lock:
        if not game.is_player(user):
            log.info("Ignoring setup from non-player %s in %s", user.username, game.id)
            return

        if game.variant != "janggi":
            log.info("Ignoring setup for non-janggi game %s by %s", game.id, user.username)
            await handle_board(ws, user, game)
            return

        if user.username == game.wplayer.username:
            user_color = "white"
        elif user.username == game.bplayer.username:
            user_color = "black"
        else:
            log.info("Ignoring setup from unknown player %s in %s", user.username, game.id)
            return

        if data["color"] != user_color:
            log.info(
                "Ignoring setup with mismatched color in %s by %s (payload=%s expected=%s)",
                game.id,
                user.username,
                data["color"],
                user_color,
            )
            await handle_board(ws, user, game)
            return

        if game.status > STARTED or game.ply > 0:
            log.info(
                "Ignoring stale setup in %s by %s (status=%s ply=%s)",
                game.id,
                user.username,
                game.status,
                game.ply,
            )
            await handle_board(ws, user, game)
            return

        if data["color"] == "black":
            if not game.bsetup:
                log.info("Ignoring duplicate black setup in %s by %s", game.id, user.username)
                await handle_board(ws, user, game)
                return
        elif data["color"] == "white":
            if game.bsetup or not game.wsetup:
                log.info(
                    "Ignoring out-of-order/duplicate white setup in %s by %s (bsetup=%s wsetup=%s)",
                    game.id,
                    user.username,
                    game.bsetup,
                    game.wsetup,
                )
                await handle_board(ws, user, game)
                return
        else:
            log.info("Ignoring setup with unknown color %s in %s", data["color"], game.id)
            await handle_board(ws, user, game)
            return

        game.board.initial_fen = data["fen"]
        game.initial_fen = game.board.initial_fen
        game.board.fen = game.board.initial_fen

        opp_name = (
            game.wplayer.username
            if user.username == game.bplayer.username
            else game.bplayer.username
        )
        # Users.get() is async and may load from MongoDB; this must remain a cache-only lookup.
        opp_player = users[opp_name] if opp_name in users else None  # noqa: SIM401

        game.steps[0]["fen"] = data["fen"]

        if data["color"] == "black":
            game.bsetup = False
            if opp_player is not None and opp_player.bot:
                game.board.janggi_setup("w")
                game.initial_fen = game.board.initial_fen
                game.steps[0]["fen"] = game.board.initial_fen

                if game.wsetup:
                    setup_response: SetupResponse = {
                        "type": "setup",
                        "color": "white",
                        "fen": data["fen"],
                    }
                    await ws_send_json(ws, setup_response)
                else:
                    game.status = STARTED
                    board_response = game.get_board(full=True)
                    await ws_send_json(ws, board_response)
            else:
                setup_response = {
                    "type": "setup",
                    "color": "white",
                    "fen": data["fen"],
                }
                await ws_send_json(ws, setup_response)
                if opp_player is not None:
                    await opp_player.send_game_message(game.id, setup_response)
        else:
            game.wsetup = False
            game.status = STARTED

            board_response = game.get_board(full=True)
            await ws_send_json(ws, board_response)

            if (opp_player is not None) and (not opp_player.bot):
                await opp_player.send_game_message(data["gameId"], board_response)

        # Setup can change Janggi's initial position, so refresh cached move state.
        game.has_legal_move = game.board.has_legal_move()
        if game.random_mover:
            game.legal_moves = game.board.legal_moves()

        await game.save_setup()

        if opp_player is not None and opp_player.bot:
            await send_bot_game_start_unless_streaming(opp_player, game)

        # restart expiration time after setup phase
        if TYPE_CHECKING:
            assert isinstance(game.stopwatch, Clock)
        game.stopwatch.restart(game.stopwatch.time_for_first_move)


async def handle_analysis(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    data: AnalysisMessage,
    game: game.Game,
) -> None:
    # fishnet_analysis() wants to inject analysis data into game.steps.
    # Older games can be loaded without caching for plain HTML rendering, so pin
    # the websocket's reconstructed instance before queueing server-side analysis.
    if game.id not in app_state.games:
        app_state.games[data["gameId"]] = game
        # TODO: maybe we have to schedule game.remove() ?

    analysis_requested = False

    dropped_stale_work = drop_stale_analysis_work(app_state)
    if dropped_stale_work:
        log.warning("Dropped %s stale fishnet analysis work items", dropped_stale_work)

    if has_pending_analysis_work_for_game(app_state, game.id):
        await ws_send_json(
            ws,
            chat_response(
                "roundchat",
                "",
                "Analysis already requested...",
                room="spectator",
            ),
        )
        return

    # Prefer fishnet when a worker explicitly supports this variant. Optional
    # engine capabilities (currently Alice) must not fall through to the legacy
    # BOT websocket merely because other fishnet workers are online.
    has_any_fishnet_worker = has_available_fishnet_worker(app_state)
    has_fishnet_worker = has_available_fishnet_worker(app_state, variant=game.variant)

    if has_fishnet_worker and catalogued_variant_allows_fishnet(app_state, game.variant):
        # Fishnet advice needs authoritative parent positions, independently of
        # the browser display. Reconstruct only when queueing requested analysis.
        if len(game.steps) == 1 and game.ply > 0:
            game.ensure_steps()
        work_id = "".join(random.choice(string.ascii_letters + string.digits) for x in range(6))
        work = {
            "work": {
                "type": "analysis",
                "id": work_id,
            },
            # or:
            # "work": {
            #   "type": "move",
            #   "id": "work_id",
            #   "level": 5 // 1 to 8
            # },
            "username": data["username"],
            "game_id": data["gameId"],  # optional
            "position": game.board.initial_fen,  # start position (X-FEN)
            "variant": game.board.variant,
            "chess960": game.chess960,
            "moves": " ".join(game.board.move_stack),  # moves of the game (UCI)
            "nnue": game.board.nnue,
            "nodes": 500000,  # optional limit
            #  "skipPositions": [1, 4, 5]  # 0 is the first position
        }
        app_state.fishnet_works[work_id] = work
        app_state.fishnet_queue.put_nowait((ANALYSIS, work_id))
        analysis_requested = True
    elif has_fishnet_worker and not catalogued_variant_allows_fishnet(app_state, game.variant):
        log.warning(
            "Skipping analysis request for %s because Fairy-Stockfish AI is temporarily disabled for variant %s",
            game.id,
            game.variant,
        )
    elif has_any_fishnet_worker or fishnet_variant_requires_capability(game.variant):
        log.warning(
            "Skipping analysis request for %s because no active fishnet worker supports variant %s",
            game.id,
            game.variant,
        )
    else:
        engine = app_state.users["Fairy-Stockfish"]

        if (engine is not None) and engine.online:
            if data["gameId"] in engine.game_queues:
                await ws_send_json(
                    ws,
                    chat_response(
                        "roundchat",
                        "",
                        "Analysis already requested...",
                        room="spectator",
                    ),
                )
                return
            engine.game_queues[data["gameId"]] = asyncio.Queue()
            if len(game.steps) == 1 and game.ply > 0:
                game.ensure_steps()
            await engine.event_queue.put(game.analysis_start(data["username"]))
            analysis_requested = True

    response: ChatMessage = chat_response(
        "roundchat",
        "",
        "Analysis request sent..." if analysis_requested else "Analysis unavailable right now.",
        room="spectator",
    )
    await ws_send_json(ws, response)


async def handle_rematch(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    data: RematchMessage,
    game: game.Game,
) -> Mapping[str, object] | None:
    if game.server_variant.two_boards:
        if TYPE_CHECKING:
            assert isinstance(game, GameBug)
        await handle_rematch_bughouse(app_state, game, user)
        return None

    # Use the game's move_lock to ensure atomic operations for rematch functionality
    async with game.move_lock:
        if game.rematch_id is not None:
            view_response: ViewRematchMessage = {"type": "view_rematch", "gameId": game.rematch_id}
            await ws_send_json(ws, view_response)
            return view_response

        rematch_id = None

        opp_name = (
            game.wplayer.username
            if user.username == game.bplayer.username
            else game.bplayer.username
        )
        opp_player = app_state.users[opp_name]
        handicap = data["handicap"]
        fen = "" if game.variant == "janggi" else game.initial_fen

        chess960 = game.chess960
        if TYPE_CHECKING:
            assert chess960 is not None
        reused_fen = True
        if (chess960 or game.random_only) and game.new_960_fen_needed_for_rematch:
            fen = FairyBoard.start_fen(game.variant, chess960, disabled_fen=game.initial_fen)
            reused_fen = False

        if opp_player.bot:
            engine = opp_player

            if not engine.online:
                if engine.username in ("Fairy-Stockfish", "Alice-Stockfish", "Random-Mover"):
                    # Preserve old built-in-AI fallback behavior.
                    engine = app_state.users["Random-Mover"]
                else:
                    error_response = {
                        "type": "error",
                        "message": f"{engine.username} BOT is offline",
                    }
                    await ws_send_json(ws, error_response)
                    return error_response

            color = "w" if game.wplayer.username == opp_name else "b"
            if handicap:
                color = "w" if color == "b" else "b"
            seek_id = await new_id(None if app_state.db is None else app_state.db.seek)
            seek = Seek(
                seek_id,
                user,
                game.variant,
                fen=fen,
                color=color,
                base=game.base,
                inc=game.inc,
                byoyomi_period=game.byoyomi_period,
                day=game.base if game.corr else 0,
                level=game.level,
                rated=game.rated,
                player1=user,
                chess960=chess960,
                reused_fen=reused_fen,
                is_rematch=True,
            )
            app_state.seeks[seek.id] = seek

            response = await join_seek(app_state, engine, seek)
            await ws_send_json(ws, response)
            if response["type"] != "new_game":
                remove_seek(app_state.seeks, seek)
                return response

            gameId = response["gameId"]
            rematch_id = gameId
            game.rematch_id = rematch_id
            engine.game_queues[gameId] = asyncio.Queue()
            rematch_game = app_state.games[gameId]
            await send_bot_game_start_unless_streaming(engine, rematch_game)
        else:
            if opp_name in game.rematch_offers:
                color = "w" if game.wplayer.username == opp_name else "b"
                if handicap:
                    color = "w" if color == "b" else "b"
                seek_id = await new_id(None if app_state.db is None else app_state.db.seek)
                seek = Seek(
                    seek_id,
                    user,
                    game.variant,
                    fen=fen,
                    color=color,
                    base=game.base,
                    inc=game.inc,
                    byoyomi_period=game.byoyomi_period,
                    day=game.base if game.corr else 0,
                    level=game.level,
                    rated=game.rated,
                    player1=user,
                    chess960=chess960,
                    reused_fen=reused_fen,
                    is_rematch=True,
                )
                app_state.seeks[seek.id] = seek

                response = await join_seek(app_state, opp_player, seek)
                if response["type"] != "new_game":
                    remove_seek(app_state.seeks, seek)
                    await ws_send_json(ws, response)
                    return response
                rematch_id = response["gameId"]
                game.rematch_id = rematch_id
                await ws_send_json(ws, response)
                await app_state.users[opp_name].send_game_message(data["gameId"], response)
            else:
                game.rematch_offers.add(user.username)
                offer_response: RematchOfferMessage = {
                    "type": "rematch_offer",
                    "username": user.username,
                    "message": "Rematch offer sent",
                    "room": "player",
                    "user": "",
                }
                response = offer_response
                game.messages.append(response)
                await ws_send_json(ws, response)
                await app_state.users[opp_name].send_game_message(data["gameId"], response)
        if rematch_id:
            view_response: ViewRematchMessage = {"type": "view_rematch", "gameId": rematch_id}
            await round_broadcast(game, view_response)

    return response


async def handle_reject_rematch(user: User, game: game.Game) -> None:
    opp_name = (
        game.wplayer.username if user.username == game.bplayer.username else game.bplayer.username
    )

    if opp_name in game.rematch_offers:
        response: RematchRejectedMessage = {
            "type": "rematch_rejected",
            "message": "Rematch offer rejected",
        }
        await round_broadcast(
            game,
            response,
            full=True,
        )


async def handle_draw(
    ws: WebSocketResponse,
    users: Users,
    user: User,
    data: DrawMessage,
    game: game.Game,
) -> None:
    color = WHITE if user.username == game.wplayer.username else BLACK
    opp_name = game.wplayer.username if color == BLACK else game.bplayer.username

    if opp_name not in game.draw_offers:
        game.draw_offers.add(user.username)

    response = await draw(game, user, agreement=opp_name in game.draw_offers)
    await ws_send_json(ws, response)

    if opp_name in users:
        opp_player = users[opp_name]
        if opp_player.bot:
            if game.status > STARTED and data["gameId"] in opp_player.game_queues:
                await opp_player.game_queues[data["gameId"]].put(game.game_end)
        else:
            try:
                await opp_player.send_game_message(data["gameId"], response)
            except KeyError:
                log.error("handle_draw() KeyError. Opp %s disconnected", opp_name)

    await round_broadcast(game, response)


async def handle_reject_draw(user: User, game: game.Game) -> None:
    color = WHITE if user.username == game.wplayer.username else BLACK
    opp_user = game.wplayer if color == BLACK else game.bplayer

    response = await reject_draw(game, opp_user)
    if response is not None:
        await round_broadcast(game, response, full=True)


async def handle_byoyomi(user: User, data: ByoyomiMessage, game: game.Game) -> None:
    async with game.move_lock:
        if not game.is_player(user) or not game.byoyomi or game.status > STARTED:
            return

        if data["color"] not in ("white", "black"):
            return
        user_color = WHITE if user.username == game.wplayer.username else BLACK
        payload_color = WHITE if data["color"] == "white" else BLACK
        if payload_color != user_color:
            log.info("Ignoring byoyomi update with mismatched color in %s", game.id)
            return

        position_id = data.get("positionId")
        if not isinstance(position_id, str):
            log.info("Ignoring byoyomi update without position id in %s", game.id)
            return
        if position_id != game.position_id():
            log.info("Ignoring stale byoyomi update in %s", game.id)
            return

        period = data["period"]
        current_period = game.byoyomi_periods[user_color]
        if period < 0 or period >= current_period:
            return

        game.byo_correction += (current_period - period) * game.inc * 1000
        game.byoyomi_periods[user_color] = period
        await game.save_byoyomi_state()


def takeback_allowed(game: game.Game, user: User) -> bool:
    return (
        game.is_player(user)
        and game.rated == CASUAL
        and game.status == STARTED
        and game.board.ply >= 2
        and game.tournamentId is None
        and game.simulId is None
        and not game.server_variant.two_boards
        and (not game.byoyomi or len(game.byoyomi_state_stack) == game.board.ply + 1)
    )


async def handle_takeback(ws: WebSocketResponse, user: User, game: game.Game) -> None:
    async with game.move_lock:
        # Recheck under the move lock so a concurrent move or game end cannot
        # turn an earlier eligibility result into a stale takeback.
        if not takeback_allowed(game, user):
            await ws_send_json(
                ws, {"type": "error", "message": "Takebacks are not allowed in this game"}
            )
            return

        if game.bot_game:
            await game.takeback(user)
            board_response = game.get_board(full=True)
            board_response["takeback"] = True
            await round_broadcast(game, board_response, full=True)
            return

        offer = game.takeback_offer
        if offer is None:
            game.takeback_offer = (user.username, game.board.ply)
            await round_broadcast(
                game,
                {
                    "type": "takeback_offer",
                    "username": user.username,
                    "message": "Takeback offer sent",
                },
                full=True,
            )
            return

        offerer_name, offer_ply = offer
        if offerer_name == user.username:
            return
        if offer_ply != game.board.ply:
            game.takeback_offer = None
            await ws_send_json(ws, {"type": "error", "message": "Takeback offer expired"})
            return

        offerer = game.wplayer if offerer_name == game.wplayer.username else game.bplayer
        game.takeback_offer = None
        await game.takeback(offerer)
        board_response = game.get_board(full=True)
        board_response["takeback"] = True
        await round_broadcast(game, board_response, full=True)


async def handle_reject_takeback(user: User, game: game.Game) -> None:
    if not game.is_player(user):
        return
    async with game.move_lock:
        if game.takeback_offer is None:
            return
        game.takeback_offer = None
        await round_broadcast(
            game,
            {"type": "takeback_rejected", "message": "Takeback offer rejected"},
            full=True,
        )


async def handle_abort_resign_abandon_flag(
    ws: WebSocketResponse,
    users: Users,
    user: User,
    data: AbortResignMessage,
    game: game.Game,
) -> None:
    if data["type"] == "abort" and (game is not None) and game.board.ply > 2:
        return

    if game.status > STARTED:
        # game was already finished!
        # see  https://github.com/pychess/pychess-variants/issues/675
        return

    async with game.move_lock:
        if data["type"] == "flag" and not _flag_claim_allowed(game, user):
            log.info(
                "Ignoring invalid flag claim in %s by %s (turn=%s, ply=%s)",
                game.id,
                user.username,
                game.board.color,
                game.ply,
            )
            return
        response = await game.game_ended(user, data["type"])

    await ws_send_json(ws, response)

    opp_name = (
        game.wplayer.username if user.username == game.bplayer.username else game.bplayer.username
    )
    if opp_name in users:
        opp_player = users[opp_name]
        if opp_player.bot:
            if data["gameId"] in opp_player.game_queues:
                await opp_player.game_queues[data["gameId"]].put(game.game_end)
        else:
            await opp_player.send_game_message(data["gameId"], response)

    await round_broadcast(game, response)


async def handle_ceval_detected(
    ws: WebSocketResponse,
    users: Users,
    user: User,
    data: CevalDetectedMessage,
    game: game.Game,
) -> None:
    if not game.is_player(user):
        log.info("Ignoring ceval self-report in %s from spectator %s", game.id, user.username)
        return

    async with game.move_lock:
        if not game.ceval_detection_allowed():
            log.info(
                "Ignoring ceval self-report in %s by %s (ineligible game)",
                game.id,
                user.username,
            )
            return

        min_report_ply = min_ceval_report_ply(game)
        if game.board.ply < min_report_ply:
            log.info(
                "Ignoring ceval self-report in %s by %s (ply=%s, min=%s)",
                game.id,
                user.username,
                game.board.ply,
                min_report_ply,
            )
            return

        if not game.ceval_detection_matches(
            variant=data["variant"],
            chess960=data["chess960"],
            fen=data["fen"],
        ):
            log.info(
                "Ignoring ceval self-report in %s by %s (position mismatch)",
                game.id,
                user.username,
            )
            return

        auto_lose = await ceval_auto_lose_enabled(game.app_state.db)
        action = (
            CEVAL_REPORT_ACTION_AUTO_FORFEIT if auto_lose else CEVAL_REPORT_ACTION_REPORTED_ONLY
        )
        await append_ceval_cheat_report(
            game.app_state.db,
            game=game,
            user=user,
            reported_fen=data["fen"],
            reported_variant=data["variant"],
            reported_chess960=data["chess960"],
            min_report_ply=min_report_ply,
            action=action,
        )

        log.warning(
            "Ceval self-report matched live game %s for %s action=%s",
            game.id,
            user.username,
            action,
        )
        if not auto_lose:
            return

        response = await game.cheat_by_ceval(user)

    await ws_send_json(ws, response)

    opp_name = (
        game.wplayer.username if user.username == game.bplayer.username else game.bplayer.username
    )
    if opp_name in users:
        await users[opp_name].send_game_message(data["gameId"], response)

    await round_broadcast(game, response)


async def handle_embed_user_connected(ws: WebSocketResponse) -> None:
    response: EmbedUserConnectedMessage = {"type": "embed_user_connected"}
    await ws_send_json(ws, response)


async def handle_game_user_connected(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    game: game.Game,
) -> None:
    # update websocket
    log.debug("Addings ws %r to user %r for game%s", id(ws), user, game)

    was_user_playing_another_game_before_connect = user.is_user_active_in_game()
    user.add_ws_for_game(game.id, ws)
    user.update_online()

    if game.simulId is not None:
        from simul.simuls import load_simul, set_simul_host_game

        simul = app_state.simuls.get(game.simulId)
        if simul is None:
            simul = await load_simul(app_state, game.simulId)
        if simul is not None and user.username == simul.created_by:
            await set_simul_host_game(simul, game.id)

    # remove user seeks — for every player in the game, not just board A's two. The old form
    # named `game.wplayer`/`game.bplayer`, so on a bughouse game a board B player was neither
    # recognised as a player here nor had their seeks cleared when the game began.
    if len(user.lobby_sockets) == 0 or (game.status <= STARTED and user in game.non_bot_players):
        for player in game.non_bot_players:
            await player.clear_seeks()

    if not game.is_player(user):
        game.spectators.add(user)
        user.watched_games.add(game.id)
        await round_broadcast(game, game.spectator_list, full=True)

    stopwatch_secs = 0
    if not game.corr and not game.server_variant.two_boards:
        if TYPE_CHECKING:
            assert isinstance(game.stopwatch, Clock)
        stopwatch_secs = game.stopwatch.secs
    response: GameUserConnectedMessage = {
        "type": "game_user_connected",
        "username": user.username,
        "gameId": game.id,
        "ply": game.ply,
        "firstmovetime": stopwatch_secs,
    }
    await ws_send_json(ws, response)

    if game.id in user.abandon_game_tasks:
        task = user.abandon_game_tasks[game.id]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        user.abandon_task_done(task, game.id)

    fullchat_response: FullChatMessage = {"type": "fullchat", "lines": list(game.messages)}
    await ws_send_json(ws, fullchat_response)

    presence_response: UserPresenceMessage = {
        "type": "user_present",
        "username": user.username,
    }
    await round_broadcast(game, presence_response, full=True)

    # if this is the first game socket for this user, and they not in lobby maybe we have a change in what
    # we considered online user count. todo: also tournament sockets maybe should be checked here
    if not was_user_playing_another_game_before_connect and not user.is_user_active_in_lobby():
        await app_state.lobby.lobby_broadcast_u_cnt()


async def handle_is_user_present(
    ws: WebSocketResponse,
    users: Users,
    player_name: str,
    game: game.Game,
) -> None:
    player = await users.get(player_name)
    response: UserPresenceMessage
    if (
        player is not None and (game.id in player.game_queues)
        if player.bot
        else player.is_user_active_in_game(game.id)
    ):
        response = {"type": "user_present", "username": player_name}
    else:
        response = {
            "type": "user_disconnected",
            "username": player_name,
        }
    await ws_send_json(ws, response)


async def handle_moretime(users: Users, user: User, data: MoreTimeRequest, game: game.Game) -> None:
    opp_color = WHITE if user.username == game.bplayer.username else BLACK
    if (not game.corr) and opp_color == game.stopwatch.color:
        if TYPE_CHECKING:
            assert isinstance(game.stopwatch, Clock)
        opp_time = game.stopwatch.stop()
        game.stopwatch.restart(opp_time + MORE_TIME)

    opp_name = (
        game.wplayer.username if user.username == game.bplayer.username else game.bplayer.username
    )
    if opp_name in users:
        opp_player = users[opp_name]
        if not opp_player.bot:
            response: MoreTimeMessage = {"type": "moretime", "username": opp_name}
            await users[opp_name].send_game_message(data["gameId"], response)
            await round_broadcast(game, response)


async def handle_bugroundchat(
    users: Users, user: User, data: BugRoundChatMessage, game: GameBug
) -> None:
    if getattr(user, "silence", 0) != 0:
        return

    gameId = data["gameId"]
    message = sanitize_user_message(data["message"])
    room = data["room"]
    if bool(getattr(user, "shadowban", False)):
        elapsed = 0
        if hasattr(game, "gameClocks") and hasattr(game.gameClocks, "elapsed_since_last_move"):
            elapsed = game.gameClocks.elapsed_since_last_move()
        await user.send_game_message(
            gameId,
            {
                "type": "bugroundchat",
                "username": user.username,
                "message": message,
                "room": room,
                "time": elapsed,
            },
        )
        return

    # response = chat_response(
    #     "bugroundchat",
    #     user.username,
    #     message,
    #     room=room,
    # )
    response = game.handle_chat_message(user, message, room)
    response["type"] = "bugroundchat"

    if room == "spectator":
        recipients = []  # just the spectators. should be equivalent to room="spectator"
    elif game.ply < 4 or game.status > STARTED:
        # Let all 4 players communicate in the beginning of the game and when it is over
        recipients = [
            game.wplayerA.username,
            game.bplayerA.username,
            game.wplayerB.username,
            game.bplayerB.username,
        ]
    elif user.username in [game.wplayerA.username, game.bplayerB.username]:
        recipients = [game.wplayerA.username, game.bplayerB.username]
    elif user.username in [game.bplayerA.username, game.wplayerB.username]:
        recipients = [game.bplayerA.username, game.wplayerB.username]
    else:
        recipients = []  # just the spectators. should be equivalent to room="spectator"
    recipients = list(
        dict.fromkeys(recipients)
    )  # remove duplicates - can have if simuling (not that it makes sense to have this chat in simul mode but anyway)
    for name in recipients:
        player = users[name]
        await player.send_game_message(gameId, response)

    await round_broadcast(game, response)


async def handle_roundchat(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    data: RoundChatMessage,
    game: game.Game,
) -> None:
    if user.username.startswith(ANON_PREFIX) or getattr(user, "silence", 0) != 0:
        return

    gameId = data["gameId"]
    message = sanitize_user_message(data["message"])
    room = data["room"]

    # Users running a fishnet worker can ask server side analysis with chat message: !analysis
    if data["message"] == "!analysis" and user.username in app_state.fishnet_versions:
        for step in game.steps:
            if "analysis" in step:
                del step["analysis"]
        analysis_response: RequestAnalysisMessage = {"type": "request_analysis"}
        await ws_send_json(ws, analysis_response)
        return

    if not app_state.chat_flood.allow_message(f"game:{gameId}:{room}:{user.username}", message):
        return

    response: ChatMessage = chat_response(
        "roundchat",
        user.username,
        message,
        room=room,
    )
    if bool(getattr(user, "shadowban", False)):
        await user.send_game_message(gameId, response)
        return

    game.handle_chat_message(response)

    for name in (game.wplayer.username, game.bplayer.username):
        player = app_state.users[name]
        if player.bot:
            if gameId in player.game_queues:
                await player.game_queues[gameId].put(
                    json_dumps(
                        {
                            "type": "chatLine",
                            "username": user.username,
                            "room": room,
                            "text": message,
                        }
                    )
                    + "\n"
                )
        else:
            await player.send_game_message(gameId, response)

    await round_broadcast(game, response)


async def handle_leave(user: User, data: LeaveMessage, game: game.Game) -> None:
    gameId = data["gameId"]

    response_chat = chat_response(
        "roundchat",
        "",
        "%s left the game" % user.username,
        room="player",
    )
    game.messages.append(response_chat)
    response: UserPresenceMessage = {
        "type": "user_disconnected",
        "username": user.username,
    }

    other_players = filter(lambda p: p.username != user.username, game.non_bot_players)
    for p in other_players:
        await p.send_game_message(gameId, response_chat)
        await p.send_game_message(gameId, response)

    await round_broadcast(game, response)


async def handle_updateTV(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, data: UpdateTVMessage
) -> None:
    if "profileId" in data and data["profileId"] != "":
        gameId = await tv_game_user(app_state.db, app_state.users, data["profileId"])
    else:
        gameId = await tv_game(app_state)

    if gameId != data["gameId"] and gameId is not None:
        response: UpdateTVMessage = {"type": "updateTV", "gameId": gameId}
        await ws_send_json(ws, response)


async def handle_count(
    ws: WebSocketResponse, user: User, data: CountMessage, game: game.Game
) -> None:
    cur_player = game.bplayer if game.board.color == BLACK else game.wplayer

    response: CountResponse
    if user.username == cur_player.username:
        if data["mode"] == "start":
            game.start_manual_count()
            await game.save_manual_count_state()
            response = {
                "type": "count",
                "message": "Board's honor counting started",
                "room": "player",
                "user": "",
            }
        elif data["mode"] == "stop":
            game.stop_manual_count()
            await game.save_manual_count_state()
            response = {
                "type": "count",
                "message": "Board's honor counting stopped",
                "room": "player",
                "user": "",
            }
        await round_broadcast(game, response, full=True)
    else:
        response = {
            "type": "count",
            "message": "You can only start/stop board's honor counting on your own turn!",
            "room": "player",
            "user": "",
        }
        await ws_send_json(ws, response)


async def handle_delete(
    db: AsyncDatabase, ws: WebSocketResponse, user: User, game: game.Game
) -> None:
    if game.rated != IMPORTED or game.imported_by != user.username:
        await ws_send_json(
            ws,
            {"type": "error", "message": "You are not allowed to delete this game."},
        )
        return

    result = await db.game.delete_one(
        {
            "_id": game.id,
            "y": IMPORTED,
            "by": user.username,
        }
    )
    if result.deleted_count != 1:
        await ws_send_json(
            ws,
            {"type": "error", "message": "Game could not be deleted."},
        )
        return

    response: DeletedMessage = {"type": "deleted"}
    await ws_send_json(ws, response)
