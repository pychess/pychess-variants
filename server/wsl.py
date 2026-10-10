from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp_session
from aiohttp import web
from aiohttp.web_ws import WebSocketResponse
from auto_pair import (
    add_to_auto_pairings,
    auto_pair,
    find_matching_user_for_seek,
)
from const import STARTED, SYSTEM_USER
from fishnet import has_available_fishnet_worker
from header_challenges import (
    broadcast_challenge_state,
    challenge_participants,
    reactivate_direct_challenges,
    schedule_direct_challenge_offline,
    set_direct_challenge_status,
)
from newid import new_id

if TYPE_CHECKING:
    from typing import Literal

    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
    from user import User
    from ws_types import (
        AcceptSeekMessage,
        AutoPairingStatusMessage,
        BotChallengeCreatedMessage,
        CancelAutoPairingMessage,
        CreateAiChallengeMessage,
        CreateAutoPairingMessage,
        CreateBotChallengeMessage,
        CreateHostMessage,
        CreateInviteMessage,
        CreateSeekMessage,
        DeleteSeekMessage,
        DirectChallengeCreatedMessage,
        GameInProgressMessage,
        HostCreatedMessage,
        InviteCreatedMessage,
        LeaveSeekMessage,
        LobbyCountMessage,
        LobbyInboundMessage,
        LobbyLeaderboardMessage,
        LobbySeeksMessage,
        LobbyUserConnectedMessage,
        SpotlightsMessage,
        StreamsMessage,
        TournamentWinnersMessage,
    )
import logging

import logger
from bug.utils_bug import handle_accept_seek_bughouse, handle_leave_seek_bughouse
from catalogued_variants import can_create_catalogued_seek, catalogued_variant_games_are_persisted
from lobby_spotlights import lobby_spotlights
from pychess_global_app_state_utils import get_app_state
from seek import (
    ACTIVE_DIRECT_CHALLENGE_STATUSES,
    ANON_RESTRICTED_SEEK_MESSAGE,
    DIRECT_CHALLENGE_BLOCKED_MESSAGE,
    DIRECT_CHALLENGE_CANCELED,
    SEEK_LIMIT_REACHED_MESSAGE,
    TWO_BOARD_TARGETED_SEEK_MESSAGE,
    Seek,
    SeekCreateData,
    challenge,
    create_seek,
    get_seeks,
    is_anon_restricted_seek,
    is_direct_challenge_target,
    is_targeted_two_board_seek,
    user_reached_seek_limit,
)
from tournament_director import is_tournament_director
from utils import (
    active_realtime_game_for_user,
    join_seek,
    load_game,
    remove_seek,
    send_bot_game_start_unless_streaming,
)
from variants import get_server_variant, is_catalogued_variant
from websocket_utils import get_user, process_ws, ws_send_json, ws_send_json_many
from ws_structs import LOBBY_TYPED_DECODERS

log = logging.getLogger(__name__)

UNSUPPORTED_FSF_AI_VARIANTS = ("fogofwar", "jieqi")
BOT_LOBBY_ACTION_MESSAGE = "BOT accounts cannot create or join lobby games."
BOT_UNSUPPORTED_VARIANT_MESSAGE = "This BOT does not support the selected variant."
CATALOGUED_CASUAL_ONLY_MESSAGE = (
    "Catalogued variants are casual-only and not available for auto-pairing."
)


async def _reject_bot_lobby_action(ws: WebSocketResponse, user: User) -> bool:
    if not user.bot:
        return False
    await ws_send_json(ws, {"type": "error", "message": BOT_LOBBY_ACTION_MESSAGE})
    return True


async def _reject_inaccessible_catalogued_variant(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    variant: str,
) -> bool:
    if not is_catalogued_variant(variant):
        return False
    if can_create_catalogued_seek(app_state, variant, None if user.anon else user.username):
        return False
    await ws_send_json(
        ws, {"type": "error", "message": "This user-defined variant is not available."}
    )
    return True


def get_create_seek_error_message(user: User, data: SeekCreateData) -> str:
    day = data.get("day", 0)
    chess960 = False if is_catalogued_variant(data["variant"]) else data.get("chess960")
    try:
        get_server_variant(data["variant"], chess960)
    except KeyError:
        return "This variant is not available."
    if is_anon_restricted_seek(user, data["variant"], chess960, day):
        return ANON_RESTRICTED_SEEK_MESSAGE
    if (
        is_catalogued_variant(data["variant"])
        and day > 0
        and not catalogued_variant_games_are_persisted(user.app_state, data["variant"])
    ):
        return "Only public user-defined variants can be used for correspondence games."
    if user_reached_seek_limit(user, day):
        return SEEK_LIMIT_REACHED_MESSAGE
    if is_targeted_two_board_seek(data["variant"], chess960, data.get("target", "")):
        return TWO_BOARD_TARGETED_SEEK_MESSAGE
    return "Failed to create seek"


async def direct_challenge_block_message(
    app_state: PychessGlobalAppState, user: User, target: str | None
) -> str | None:
    if not is_direct_challenge_target(target):
        return None
    challenge_target = target or ""
    if challenge_target == SYSTEM_USER:
        return DIRECT_CHALLENGE_BLOCKED_MESSAGE
    target_profile = await app_state.public_users.get_profile(challenge_target)
    if target_profile is None:
        return None
    if challenge_target in user.blocked or user.username in target_profile.blocked:
        return DIRECT_CHALLENGE_BLOCKED_MESSAGE
    return None


async def lobby_socket_handler(request: web.Request) -> web.StreamResponse:
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    user = await get_user(session, request)
    logger.set_log_context("username", user.username)
    logger.set_log_context("gameId", "lobby")

    ws = await process_ws(
        session, request, user, init_ws, process_message, typed_decoders=LOBBY_TYPED_DECODERS
    )
    if ws is None:
        return web.HTTPFound("/")
    await finally_logic(app_state, ws, user)
    return ws


async def init_ws(app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User) -> None:
    user.last_seen = datetime.now(UTC)
    await send_game_in_progress_if_any(app_state, user, ws)
    await send_lobby_user_connected(app_state, ws, user)
    await send_get_seeks(app_state, ws, user)


async def finally_logic(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User
) -> None:
    async def schedule_abandon_if_waiting_for_round_socket() -> None:
        game_id = user.game_in_progress
        if game_id is None or len(user.lobby_sockets) > 0:
            return
        if user.is_user_active_in_game(game_id):
            return
        if game_id in user.abandon_game_tasks:
            return

        game = await load_game(app_state, game_id)
        if game is None or game.status > STARTED or getattr(game, "corr", False):
            return
        if game.server_variant.two_boards:
            return
        if not game.is_player(user):
            return
        if TYPE_CHECKING:
            assert isinstance(game, Game)

        task = asyncio.create_task(
            user.abandon_game(game), name="abandon-game-%s-%s" % (user.username, game.id)
        )
        user.abandon_game_tasks[game.id] = task
        task.add_done_callback(lambda task: user.abandon_task_done(task, game.id))

    if user is not None:
        if ws in user.lobby_sockets:
            user.lobby_sockets.remove(ws)
            user.update_online()
            if len(user.lobby_sockets) == 0:
                app_state.lobby.lobbysockets.pop(user.username, None)

        await schedule_abandon_if_waiting_for_round_socket()

        # not connected to lobby socket and not connected to game socket
        if user.is_user_active_in_game() and len(user.lobby_sockets) == 0:
            await app_state.lobby.lobby_broadcast_u_cnt()

        if (user.game_in_progress is not None) or len(user.lobby_sockets) == 0:
            user.update_auto_pairing(ready=False)
            await user.update_seeks(pending=True)
            if not user.online:
                schedule_direct_challenge_offline(app_state, user.username)

            if (not user.anon) and len(user.lobby_sockets) == 0:
                for seek in tuple(app_state.seeks.values()):
                    try:
                        server_variant = get_server_variant(seek.variant, seek.chess960)
                    except KeyError:
                        log.warning(
                            "Removing stale seek %s for unavailable variant %s",
                            seek.id,
                            seek.variant,
                        )
                        app_state.seeks.pop(seek.id, None)
                        seek.creator.seeks.pop(seek.id, None)
                        if seek.game_id is not None:
                            app_state.invites.pop(seek.game_id, None)
                        if app_state.db is not None:
                            await app_state.db.seek.delete_one({"_id": seek.id})
                        continue
                    if server_variant.two_boards:
                        await handle_leave_seek_bughouse(app_state, user, seek)


async def process_message(
    app_state: PychessGlobalAppState,
    user: User,
    ws: WebSocketResponse,
    data: LobbyInboundMessage,
) -> None:
    log.debug("message from %s: %r", user.username, data)
    if data["type"] == "create_ai_challenge":
        await handle_create_ai_challenge(app_state, ws, user, data)
    elif data["type"] == "create_seek":
        await handle_create_seek(app_state, ws, user, data)
    elif data["type"] == "create_invite":
        await handle_create_invite(app_state, ws, user, data)
    elif data["type"] == "create_bot_challenge":
        await handle_create_bot_challenge(app_state, ws, user, data)
    elif data["type"] == "create_host":
        await handle_create_host(app_state, ws, user, data)
    elif data["type"] == "delete_seek":
        await handle_delete_seek(app_state, user, data)
    elif data["type"] == "leave_seek":
        await handle_leave_seek(app_state, ws, user, data)
    elif data["type"] == "accept_seek":
        await handle_accept_seek(app_state, ws, user, data)
    elif data["type"] == "create_auto_pairing":
        await handle_create_auto_pairing(app_state, ws, user, data)
    elif data["type"] == "cancel_auto_pairing":
        await handle_cancel_auto_pairing(app_state, ws, user, data)


async def send_get_seeks(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User
) -> None:
    # We will need all the seek users blocked info
    seeks = app_state.seeks.values()
    for seek in seeks:
        await app_state.users.get(seek.creator.username)

    response: LobbySeeksMessage = {"type": "get_seeks", "seeks": get_seeks(user, seeks)}
    await ws_send_json(ws, response)


async def handle_create_ai_challenge(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    data: CreateAiChallengeMessage,
) -> None:
    if await _reject_bot_lobby_action(ws, user):
        return

    if data.get("day", 0) == 0:
        no = await send_game_in_progress_if_any(app_state, user, ws)
        if no:
            return

    variant = data["variant"]
    profileid = data["profileid"]
    engine = app_state.users[profileid]
    force_random_mover = (
        variant in UNSUPPORTED_FSF_AI_VARIANTS
        or data["rm"]
        or (engine is None)
        or (not engine.online)
        or (
            profileid == "Fairy-Stockfish"
            and not has_available_fishnet_worker(app_state, variant=variant)
        )
    )

    if force_random_mover:
        # TODO: message that engine is offline, but Random-Mover BOT will play instead
        engine = app_state.users["Random-Mover"]
    elif variant == "alice" and profileid == "Fairy-Stockfish":
        if "Alice-Stockfish" in app_state.users:
            engine = app_state.users["Alice-Stockfish"]
        else:
            log.warning(
                "Alice-Stockfish BOT account is unavailable; using Random-Mover for Alice AI game"
            )
            force_random_mover = True
            engine = app_state.users["Random-Mover"]

    seek_id = await new_id(None if app_state.db is None else app_state.db.seek)
    seek = Seek(
        seek_id,
        user,
        variant,
        fen=data["fen"],
        color=data["color"],
        base=data["minutes"],
        inc=data["increment"],
        byoyomi_period=data["byoyomiPeriod"],
        level=0 if force_random_mover else data["level"],
        player1=user,
        rated=False,
        chess960=data["chess960"],
    )
    log.debug("adding seek: %s" % seek)

    response = await join_seek(app_state, engine, seek)
    await ws_send_json(ws, response)

    if response["type"] != "error":
        gameId = response["gameId"]
        engine.game_queues[gameId] = asyncio.Queue()
        game = app_state.games[gameId]
        await send_bot_game_start_unless_streaming(engine, game)


async def handle_create_seek(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User, data: CreateSeekMessage
) -> None:
    if await _reject_bot_lobby_action(ws, user):
        return

    if data.get("day", 0) == 0:
        no = await send_game_in_progress_if_any(app_state, user, ws)
        if no:
            return

    if await _reject_inaccessible_catalogued_variant(app_state, ws, user, data["variant"]):
        return

    log.debug("Creating seek from request: %s", data)
    seek_data: SeekCreateData = data
    if is_catalogued_variant(seek_data["variant"]):
        seek_data = dict(seek_data)  # type: ignore[assignment]
        seek_data["rated"] = False
        seek_data["chess960"] = False
    block_message = await direct_challenge_block_message(app_state, user, seek_data.get("target"))
    if block_message is not None:
        await ws_send_json(ws, {"type": "error", "message": block_message})
        return
    seek = await create_seek(app_state.db, app_state.invites, app_state.seeks, user, seek_data)
    if seek is None:
        await ws_send_json(
            ws, {"type": "error", "message": get_create_seek_error_message(user, seek_data)}
        )
        return
    if TYPE_CHECKING:
        assert seek is not None
    seek_value: Seek = seek
    log.debug("Created seek: %s", seek_value)

    matching_user = None
    # auto pairing games are never corr and always rated, so anon seek will never match!
    if (
        seek_value.day == 0
        and not seek_value.fen
        and not user.anon
        and not is_catalogued_variant(seek_value.variant)
    ):
        variant_tc = (
            seek_value.variant,
            seek_value.chess960,
            seek_value.base,
            seek_value.inc,
            seek_value.byoyomi_period,
        )
        if variant_tc in app_state.auto_pairings:
            matching_user = find_matching_user_for_seek(app_state, seek_value, variant_tc)

    auto_paired = False
    if matching_user is not None:
        # Try to create a new game
        auto_paired = await auto_pair(app_state, matching_user, variant_tc, user, seek_value)

    if not auto_paired:
        await app_state.lobby.lobby_broadcast_seeks()
        if getattr(seek_value, "is_direct_challenge", False):
            response: DirectChallengeCreatedMessage = {
                "type": "direct_challenge_created",
                "seekId": seek_value.id,
            }
            await ws_send_json(ws, response)
            await broadcast_challenge_state(app_state, challenge_participants(seek_value))
        if (seek is not None) and seek_value.target == "":
            try:
                await app_state.discord.send_to_discord("create_seek", seek_value.discord_msg)
            except Exception:
                log.exception("Failed to send Discord seek notification for %s", seek_value.id)


async def handle_create_invite(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User, data: CreateInviteMessage
) -> None:
    if await _reject_bot_lobby_action(ws, user):
        return

    if data.get("day", 0) == 0:
        no = await send_game_in_progress_if_any(app_state, user, ws)
        if no:
            return

    if await _reject_inaccessible_catalogued_variant(app_state, ws, user, data["variant"]):
        return

    log.debug("Creating seek invite from request: %s", data)
    seek_data: SeekCreateData = data
    if is_catalogued_variant(seek_data["variant"]):
        seek_data = dict(seek_data)  # type: ignore[assignment]
        seek_data["rated"] = False
        seek_data["chess960"] = False
    seek = await create_seek(app_state.db, app_state.invites, app_state.seeks, user, seek_data)
    if seek is None:
        await ws_send_json(
            ws, {"type": "error", "message": get_create_seek_error_message(user, seek_data)}
        )
        return
    if TYPE_CHECKING:
        assert seek is not None
    seek_value: Seek = seek
    log.debug("Created seek invite: %s", seek_value)

    invite_game_id = seek_value.game_id
    if TYPE_CHECKING:
        assert invite_game_id is not None
    response: InviteCreatedMessage = {"type": "invite_created", "gameId": invite_game_id}
    await ws_send_json(ws, response)


async def handle_create_bot_challenge(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    data: CreateBotChallengeMessage,
) -> None:
    if await _reject_bot_lobby_action(ws, user):
        return

    no = await send_game_in_progress_if_any(app_state, user, ws)
    if no:
        return

    if await _reject_inaccessible_catalogued_variant(app_state, ws, user, data["variant"]):
        return

    profileid = data["profileid"]
    engine = await app_state.users.get(profileid)

    if (engine is None) or (not engine.online):
        return

    bot_variant = data["variant"] + ("960" if data["chess960"] else "")
    if engine.username not in ("Fairy-Stockfish", "Random-Mover") and (
        engine.bot_supported_variants is None or bot_variant not in engine.bot_supported_variants
    ):
        await ws_send_json(ws, {"type": "error", "message": BOT_UNSUPPORTED_VARIANT_MESSAGE})
        return

    log.debug("Creating BOT challenge from request: %s", data)
    seek_data: SeekCreateData = {
        "variant": data["variant"],
        "fen": data["fen"],
        "color": data["color"],
        "minutes": data["minutes"],
        "increment": data["increment"],
        "byoyomiPeriod": data["byoyomiPeriod"],
        "rated": False,
        "chess960": data["chess960"],
        "target": data["target"],
    }
    seek = await create_seek(
        app_state.db, app_state.invites, app_state.seeks, user, seek_data, engine=engine
    )
    if seek is None:
        await ws_send_json(
            ws, {"type": "error", "message": get_create_seek_error_message(user, seek_data)}
        )
        return
    if TYPE_CHECKING:
        assert seek is not None
    seek_value: Seek = seek
    log.debug("Created BOT challenge: %s", seek_value)
    if TYPE_CHECKING:
        assert seek_value.game_id is not None

    engine.game_queues[seek_value.game_id] = asyncio.Queue()
    bot_challenge = challenge(seek_value)
    await engine.event_queue.put(bot_challenge)

    bot_game_id = seek_value.game_id
    if TYPE_CHECKING:
        assert bot_game_id is not None
    response: BotChallengeCreatedMessage = {
        "type": "bot_challenge_created",
        "gameId": bot_game_id,
    }
    await ws_send_json(ws, response)


async def handle_create_host(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User, data: CreateHostMessage
) -> None:
    if await _reject_bot_lobby_action(ws, user):
        return

    no = not is_tournament_director(user, app_state)
    if no:
        return

    seek_data: SeekCreateData = data
    seek = await create_seek(
        app_state.db,
        app_state.invites,
        app_state.seeks,
        user,
        seek_data,
        empty=True,
    )
    if seek is None:
        await ws_send_json(
            ws, {"type": "error", "message": get_create_seek_error_message(user, seek_data)}
        )
        return
    if TYPE_CHECKING:
        assert seek is not None
    seek_value: Seek = seek

    host_game_id = seek_value.game_id
    if TYPE_CHECKING:
        assert host_game_id is not None
    response: HostCreatedMessage = {"type": "host_created", "gameId": host_game_id}
    await ws_send_json(ws, response)


async def handle_delete_seek(
    app_state: PychessGlobalAppState, user: User, data: DeleteSeekMessage
) -> None:
    seek_id = data["seekID"]
    seek = app_state.seeks.get(seek_id)
    if seek is None:
        log.debug("handle_delete_seek() ignored duplicate delete for seek %s", seek_id)
        await app_state.lobby.lobby_broadcast_seeks()
        return

    if getattr(seek, "is_direct_challenge", False):
        if getattr(seek, "challenge_status", None) in ACTIVE_DIRECT_CHALLENGE_STATUSES:
            challenge_users = challenge_participants(seek)
            set_direct_challenge_status(seek, DIRECT_CHALLENGE_CANCELED)
            await app_state.lobby.lobby_broadcast_seeks()
            await broadcast_challenge_state(app_state, challenge_users)
            return
        app_state.seeks.pop(seek_id, None)
    else:
        seek = app_state.seeks.pop(seek_id, None)
        if seek is None:
            log.debug("handle_delete_seek() ignored duplicate delete for seek %s", seek_id)
            await app_state.lobby.lobby_broadcast_seeks()
            return

    challenge_users = (
        challenge_participants(seek) if getattr(seek, "is_direct_challenge", False) else ()
    )

    if seek.game_id is not None:
        # Delete the invite if it still exists; duplicate cleanup is expected.
        app_state.invites.pop(seek.game_id, None)

    seek.creator.seeks.pop(seek_id, None)
    if user is not seek.creator:
        user.seeks.pop(seek_id, None)
    log.debug("handle_delete_seek() deleted seek %s", seek_id)
    await app_state.lobby.lobby_broadcast_seeks()
    if challenge_users:
        await broadcast_challenge_state(app_state, challenge_users)


async def handle_leave_seek(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User, data: LeaveSeekMessage
) -> None:
    if data["seekID"] not in app_state.seeks:
        return

    seek = app_state.seeks[data["seekID"]]

    server_variant = get_server_variant(seek.variant, seek.chess960)
    if server_variant.two_boards:
        await handle_leave_seek_bughouse(app_state, user, seek)


async def handle_accept_seek(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User, data: AcceptSeekMessage
) -> None:
    if await _reject_bot_lobby_action(ws, user):
        return

    if data["seekID"] not in app_state.seeks:
        return

    seek = app_state.seeks[data["seekID"]]
    if (
        getattr(seek, "is_direct_challenge", False)
        and getattr(seek, "challenge_status", None) not in ACTIVE_DIRECT_CHALLENGE_STATUSES
    ):
        return

    if getattr(seek, "day", 0) == 0:
        no = await send_game_in_progress_if_any(app_state, user, ws)
        if no:
            return

    # print("accept_seek", seek.seek_json)
    server_variant = get_server_variant(seek.variant, seek.chess960)
    if server_variant.two_boards:
        await handle_accept_seek_bughouse(app_state, user, data, seek)
    else:
        response = await join_seek(app_state, user, seek)
        await ws_send_json(ws, response)
        if response["type"] == "error":
            return

        if seek.creator.bot:
            gameId = response["gameId"]
            seek.creator.game_queues[gameId] = asyncio.Queue()
            game = app_state.games[gameId]
            await send_bot_game_start_unless_streaming(seek.creator, game)
        else:
            ws_set = tuple(seek.creator.lobby_sockets)
            if len(ws_set) == 0:
                if not getattr(seek, "is_direct_challenge", False):
                    remove_seek(app_state.seeks, seek)
                    await app_state.lobby.lobby_broadcast_seeks()
            else:
                await ws_send_json_many(ws_set, response)

        # Inform others about the accepted challenge / seek removal.
        await app_state.lobby.lobby_broadcast_seeks()
        if getattr(seek, "is_direct_challenge", False):
            game_ids = None
            if response["type"] == "new_game" and len(seek.creator.lobby_sockets) == 0:
                game_ids = {seek.creator.username: response["gameId"]}
            await broadcast_challenge_state(
                app_state, challenge_participants(seek), game_ids=game_ids
            )

    if (seek is not None) and seek.target == "":
        msg = "%s accepted by %s" % (seek.discord_msg, user.username)
        await app_state.discord.send_to_discord("accept_seek", msg)


async def send_lobby_user_connected(
    app_state: PychessGlobalAppState, ws: WebSocketResponse, user: User
) -> None:
    # update websocket
    user.lobby_sockets.add(ws)
    user.update_online()
    await reactivate_direct_challenges(app_state, user.username)
    app_state.lobby.lobbysockets[user.username] = user.lobby_sockets

    lobby_response: LobbyUserConnectedMessage = {
        "type": "lobby_user_connected",
        "username": user.username,
    }
    await ws_send_json(ws, lobby_response)

    # send game count
    game_count_response: LobbyCountMessage = {"type": "g_cnt", "cnt": app_state.g_cnt[0]}
    await ws_send_json(ws, game_count_response)

    # send user count
    if user.is_user_active_in_game() == 0:
        await app_state.lobby.lobby_broadcast_u_cnt()
    else:
        user_count_response: LobbyCountMessage = {
            "type": "u_cnt",
            "cnt": app_state.online_count(),
        }  # todo: duplicated message definition also in lobby_broadcast_u_cnt
        await ws_send_json(ws, user_count_response)

    # send auto pairing count
    auto_pairing_count: LobbyCountMessage = {
        "type": "ap_cnt",
        "cnt": app_state.auto_pairing_count(),
    }
    await ws_send_json(ws, auto_pairing_count)

    spotlights = lobby_spotlights(app_state)
    if len(spotlights) > 0:
        spotlights_response: SpotlightsMessage = {"type": "spotlights", "items": spotlights}
        await ws_send_json(ws, spotlights_response)

    streams = app_state.twitch.live_streams + app_state.youtube.live_streams
    if len(streams) > 0:
        streams_response: StreamsMessage = {"type": "streams", "items": streams}
        await ws_send_json(ws, streams_response)

    leaderboard_response: LobbyLeaderboardMessage = {
        "type": "leaderboard",
        "items": app_state.lobby_leaderboard,
    }
    await ws_send_json(ws, leaderboard_response)

    winners_response: TournamentWinnersMessage = {
        "type": "tournament_winners",
        "items": app_state.lobby_tournament_winners,
    }
    await ws_send_json(ws, winners_response)

    if app_state.tv is not None and app_state.tv in app_state.games:
        game = app_state.games[app_state.tv]
        if hasattr(game, "tv_game_json"):
            if TYPE_CHECKING:
                assert isinstance(game, Game)
            await ws_send_json(ws, game.tv_game_json)

    user.update_auto_pairing(ready=True)
    await user.update_seeks(pending=False)

    auto_pairing: Literal["auto_pairing_on", "auto_pairing_off"] = (
        "auto_pairing_on" if user in app_state.auto_pairing_users else "auto_pairing_off"
    )
    auto_pairing_response: AutoPairingStatusMessage = {"type": auto_pairing}
    await ws_send_json(ws, auto_pairing_response)


async def handle_cancel_auto_pairing(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    data: CancelAutoPairingMessage,
) -> None:
    user.remove_from_auto_pairings()
    response: AutoPairingStatusMessage = {"type": "auto_pairing_off"}
    await ws_send_json_many(user.lobby_sockets, response)

    await app_state.lobby.lobby_broadcast_ap_cnt()


async def handle_create_auto_pairing(
    app_state: PychessGlobalAppState,
    ws: WebSocketResponse,
    user: User,
    data: CreateAutoPairingMessage,
) -> None:
    if await _reject_bot_lobby_action(ws, user):
        return

    no = await send_game_in_progress_if_any(app_state, user, ws)
    if no:
        return

    if any(is_catalogued_variant(variant) for variant, _chess960 in data["variants"]):
        await ws_send_json(ws, {"type": "error", "message": CATALOGUED_CASUAL_ONLY_MESSAGE})
        return

    auto_variant_tc, matching_user, matching_seek = add_to_auto_pairings(app_state, user, data)

    auto_paired = False
    if (matching_user is not None) or (matching_seek is not None):
        # Try to create a new game
        auto_paired = await auto_pair(
            app_state, user, auto_variant_tc, matching_user, matching_seek
        )

    if not auto_paired:
        response: AutoPairingStatusMessage = {"type": "auto_pairing_on"}
        await ws_send_json_many(user.lobby_sockets, response)

    await app_state.lobby.lobby_broadcast_ap_cnt()

    # print("AUTO_PAIRING USERS", [item for item in app_state.auto_pairing_users.items()])
    # for key, value in app_state.auto_pairings.items():
    #     print(key, [user.username for user in app_state.auto_pairings[key]])


async def send_game_in_progress_if_any(
    app_state: PychessGlobalAppState, user: User | None, ws: WebSocketResponse
) -> bool:
    # Prevent None user to handle seeks
    if user is None:
        return True
    # ``game_in_progress`` is only a navigation hint; it cannot represent a
    # simul host's multiple boards. The live game cache is authoritative for
    # realtime admission.
    game = active_realtime_game_for_user(app_state, user)
    if game is not None:
        user.game_in_progress = game.id
        response: GameInProgressMessage = {
            "type": "game_in_progress",
            "gameId": game.id,
        }
        await ws_send_json(ws, response)
        return True

    # Clear a stale navigation hint when no active realtime game exists.
    if user.game_in_progress is not None:
        stale = await load_game(app_state, user.game_in_progress)
        if stale is None or stale.status > STARTED or getattr(stale, "corr", False):
            user.game_in_progress = None
        else:
            response: GameInProgressMessage = {
                "type": "game_in_progress",
                "gameId": stale.id,
            }
            await ws_send_json(ws, response)
            return True
    return False
