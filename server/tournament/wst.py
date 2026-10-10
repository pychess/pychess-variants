from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp_session
import logger
from admin import set_shadowban
from aiohttp import web
from chat import chat_response
from const import ANON_PREFIX, SHIELD
from link_filter import sanitize_user_message
from public_chat_moderation import timeout_public_chat_user

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from user import User
    from ws_types import (
        TournamentAbortMessage,
        TournamentGetGamesMessage,
        TournamentGetPlayersMessage,
        TournamentInboundMessage,
        TournamentJoinMessage,
        TournamentLobbyChatMessage,
        TournamentMyPageMessage,
        TournamentPauseMessage,
        TournamentRRAnnulGameMessage,
        TournamentRRArrangementsMessage,
        TournamentRRChallengeMessage,
        TournamentRRManagementMessage,
        TournamentRRManagePlayerMessage,
        TournamentRRSetJoiningMessage,
        TournamentRRSetTimeMessage,
        TournamentStartNextRoundMessage,
        TournamentUserConnectedRequest,
        TournamentWithdrawMessage,
    )
from const import RR
from pychess_global_app_state_utils import get_app_state
from session_security import GAMEPLAY_EXPIRY_GRACE_KEY
from settings import ADMINS
from tournament_director import is_tournament_director
from websocket_utils import get_user, process_ws, ws_send_json
from ws_types import ChatLine, FullChatMessage, TournamentUserConnectedMessage

from tournament.rr import RRTournament
from tournament.tournament import T_CREATED, T_STARTED
from tournament.tournaments import creator_can_manage_tournament, load_tournament

TOURNAMENT_LIFECYCLE_COMMANDS_RETIRED_MESSAGE = (
    "Tournament lifecycle commands moved to the tournament controls."
)


async def tournament_socket_handler(request):
    app_state = get_app_state(request.app)
    session = await aiohttp_session.get_session(request)
    user = await get_user(session, request)
    logger.set_log_context("username", user.username)
    logger.set_log_context(
        "gameId", "arena"
    )  # todo: we don't have tournamentId at this point, otherwise could put it here
    ws = await process_ws(session, request, user, None, process_message)
    if ws is None:
        return web.HTTPFound("/")
    await finally_logic(app_state, ws, user)
    return ws


async def load_rr_tournament(
    app_state: PychessGlobalAppState, tournament_id: str
) -> RRTournament | None:
    tournament = await load_tournament(app_state, tournament_id)
    if tournament is None or tournament.system != RR:
        return None
    assert isinstance(tournament, RRTournament)
    return tournament


async def finally_logic(app_state: PychessGlobalAppState, ws, user):
    if user is not None:
        for tournamentId, ws_set in tuple(user.tournament_sockets.items()):
            if ws in ws_set:
                ws_set.remove(ws)

                if len(ws_set) == 0:
                    user.tournament_sockets.pop(tournamentId, None)
                    user.update_online()

                    if tournamentId in app_state.tourneysockets:
                        app_state.tourneysockets[tournamentId].pop(user.username, None)
                        tournament = await load_tournament(app_state, tournamentId)
                        if tournament is not None:
                            tournament.spactator_leave(user)
                            await tournament.broadcast(tournament.spectator_list)

                    if not user.online:
                        await app_state.lobby.lobby_broadcast_u_cnt()
                break


async def process_message(
    app_state: PychessGlobalAppState, user: User, ws, data: TournamentInboundMessage
) -> None:
    if data["type"] == "get_players":
        await handle_get_players(app_state, ws, user, data)
    elif data["type"] == "my_page":
        await handle_my_page(app_state, ws, user, data)
    elif data["type"] == "get_games":
        await handle_get_games(app_state, ws, data)
    elif data["type"] == "get_rr_arrangements":
        await handle_get_rr_arrangements(app_state, ws, user, data)
    elif data["type"] == "get_rr_management":
        await handle_get_rr_management(app_state, ws, user, data)
    elif data["type"] == "rr_set_joining_closed":
        await handle_rr_set_joining_closed(app_state, ws, user, data)
    elif data["type"] == "join":
        await handle_join(app_state, ws, user, data)
    elif data["type"] == "pause":
        await handle_pause(app_state, ws, user, data)
    elif data["type"] == "withdraw":
        await handle_withdraw(app_state, ws, user, data)
    elif data["type"] == "start_next_round":
        await handle_start_next_round(app_state, ws, user, data)
    elif data["type"] == "abort_tournament":
        await handle_abort_tournament(app_state, ws, user, data)
    elif data["type"] == "tournament_user_connected":
        await handle_user_connected(app_state, ws, user, data)
    elif data["type"] == "rr_challenge":
        await handle_rr_challenge(app_state, ws, user, data)
    elif data["type"] == "rr_accept_challenge":
        await handle_rr_accept_challenge(app_state, ws, user, data)
    elif data["type"] == "rr_annul_game":
        await handle_rr_annul_game(app_state, ws, user, data)
    elif data["type"] == "rr_set_time":
        await handle_rr_set_time(app_state, ws, user, data)
    elif (
        data["type"] == "rr_approve_player"
        or data["type"] == "rr_deny_player"
        or data["type"] == "rr_kick_player"
    ):
        await handle_rr_manage_player(app_state, ws, user, data)
    elif data["type"] == "lobbychat":
        await handle_lobbychat(app_state, user, data)


async def handle_get_players(
    app: PychessGlobalAppState, ws, user: User, data: TournamentGetPlayersMessage
) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is not None:
        page = data["page"]
        player_data = tournament.player_data_by_name(user.username)
        if player_data is not None and player_data.page != page:
            player_data.page = page
        response = tournament.players_json(page=page)
        await ws_send_json(ws, response)


async def handle_my_page(
    app: PychessGlobalAppState, ws, user: User, data: TournamentMyPageMessage
) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is not None:
        player_data = tournament.player_data_by_name(user.username)
        if player_data is not None:
            # force to get users current page by leaderboard status
            player_data.page = -1
        response = tournament.players_json(user=user)
        await ws_send_json(ws, response)


async def handle_get_games(app: PychessGlobalAppState, ws, data: TournamentGetGamesMessage) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is not None:
        response = await tournament.games_json(data["player"])
        await ws_send_json(ws, response)


async def handle_get_rr_arrangements(
    app: PychessGlobalAppState, ws, user: User, data: TournamentRRArrangementsMessage
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return
    await ws_send_json(ws, rr_tournament.arrangement_payload(user=user))


async def handle_get_rr_management(
    app: PychessGlobalAppState, ws, user: User, data: TournamentRRManagementMessage
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return
    if not await creator_can_manage_tournament(app, rr_tournament, user.username):
        await ws_send_json(ws, {"type": "error", "message": "Permission denied"})
        return
    await ws_send_json(ws, rr_tournament.rr_management_payload(requested_by=user.username))


async def handle_rr_set_joining_closed(
    app: PychessGlobalAppState, ws, user: User, data: TournamentRRSetJoiningMessage
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return
    if not await creator_can_manage_tournament(app, rr_tournament, user.username):
        await ws_send_json(ws, {"type": "error", "message": "Permission denied"})
        return
    result = await rr_tournament.rr_set_joining_closed(data["closed"])
    if result is not None:
        await ws_send_json(ws, {"type": "error", "message": result})


async def handle_join(
    app: PychessGlobalAppState, ws, user: User, data: TournamentJoinMessage
) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is not None:
        password = data.get("password")
        result = await tournament.join(user, password)
        if result == "401":
            response = {"type": "error", "message": "Incorrect password"}
            await ws_send_json(ws, response)
            return
        if result == "LATE_JOIN_CLOSED":
            response = {
                "type": "error",
                "message": "Late join is closed for this Swiss tournament",
            }
            await ws_send_json(ws, response)
            return
        if result in ("JOIN_REQUESTED", "JOIN_REQUEST_PENDING"):
            await ws_send_json(
                ws,
                {
                    "type": "ustatus",
                    "username": user.username,
                    "ustatus": tournament.user_status(user),
                },
            )
            return
        if result is not None:
            response = {"type": "error", "message": result}
            await ws_send_json(ws, response)
            return

        response = {
            "type": "ustatus",
            "username": user.username,
            "ustatus": tournament.user_status(user),
        }
        await ws_send_json(ws, response)


async def handle_pause(
    app: PychessGlobalAppState, ws, user: User, data: TournamentPauseMessage
) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is not None:
        await tournament.pause(user)
        response = {
            "type": "ustatus",
            "username": user.username,
            "ustatus": tournament.user_status(user),
        }
        await ws_send_json(ws, response)


async def handle_withdraw(
    app: PychessGlobalAppState, ws, user: User, data: TournamentWithdrawMessage
) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is not None:
        await tournament.withdraw(user)
        response = {
            "type": "ustatus",
            "username": user.username,
            "ustatus": tournament.user_status(user),
        }
        await ws_send_json(ws, response)


async def handle_start_next_round(
    app: PychessGlobalAppState,
    ws,
    user: User,
    data: TournamentStartNextRoundMessage,
) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is None:
        await ws_send_json(ws, {"type": "error", "message": "Tournament not found"})
        return

    can_control_rounds = is_tournament_director(user, app) or await creator_can_manage_tournament(
        app, tournament, user.username
    )
    if not can_control_rounds:
        await ws_send_json(ws, {"type": "error", "message": "Permission denied"})
        return

    if not await tournament.start_next_round_now():
        await ws_send_json(
            ws,
            {"type": "error", "message": "The next round is not ready to start"},
        )


async def handle_abort_tournament(
    app: PychessGlobalAppState,
    ws,
    user: User,
    data: TournamentAbortMessage,
) -> None:
    tournament = await load_tournament(app, data["tournamentId"])
    if tournament is None:
        await ws_send_json(ws, {"type": "error", "message": "Tournament not found"})
        return

    if user.username not in ADMINS:
        await ws_send_json(ws, {"type": "error", "message": "Permission denied"})
        return

    if tournament.status not in (T_CREATED, T_STARTED):
        await ws_send_json(ws, {"type": "error", "message": "Tournament has already ended"})
        return

    await tournament.abort()


async def handle_user_connected(
    app_state: PychessGlobalAppState, ws, user: User, data: TournamentUserConnectedRequest
) -> None:
    tournamentId = data["tournamentId"]
    tournament = await load_tournament(app_state, tournamentId)
    if tournament is None:
        return

    # update websocket
    if tournamentId not in user.tournament_sockets:
        user.tournament_sockets[tournamentId] = set()
    user.tournament_sockets[tournamentId].add(ws)

    user.update_online()

    app_state.tourneysockets[tournamentId][user.username] = user.tournament_sockets[tournamentId]

    now = datetime.now(UTC)
    creator_can_manage = not ws.get(
        GAMEPLAY_EXPIRY_GRACE_KEY, False
    ) and await creator_can_manage_tournament(app_state, tournament, user.username)
    response: TournamentUserConnectedMessage = {
        "type": "tournament_user_connected",
        "username": user.username,
        "ustatus": tournament.user_status(user),
        "urating": tournament.user_rating(user),
        "tstatus": tournament.status,
        "tsystem": tournament.system,
        "tminutes": tournament.minutes,
        "rounds": tournament.rounds,
        "startsAt": tournament.starts_at.isoformat(),
        "startFen": tournament.fen,
        "description": tournament.description,
        "frequency": tournament.frequency,
        "createdBy": tournament.created_by,
        "secondsToStart": (
            (tournament.starts_at - now).total_seconds() if tournament.starts_at > now else 0
        ),
        "secondsToFinish": (
            max(0.0, (tournament.ends_at - now).total_seconds())
            if tournament.starts_at < now
            else 0
        ),
        "chatClosed": tournament.status > T_STARTED
        and (now - tournament.ends_at).total_seconds() > 60 * 60,
        "private": bool(tournament.password),
        "creatorCanManage": creator_can_manage,
    }
    round_ongoing_games, seconds_to_next_round = tournament.round_status(now)
    response["currentRound"] = tournament.current_round
    response["roundOngoingGames"] = round_ongoing_games
    response["secondsToNextRound"] = seconds_to_next_round
    response["manualNextRound"] = tournament.manual_next_round_pending
    if tournament.system == RR:
        response["rrRequiresApproval"] = tournament.rr_requires_approval
        response["rrJoiningClosed"] = tournament.rr_joining_closed
    if tournament.frequency == SHIELD:
        variant_name = tournament.variant + ("960" if tournament.chess960 else "")
        defender = await app_state.users.get(app_state.shield_owners[variant_name])
        response["defender_title"] = defender.title
        response["defender_name"] = defender.username

    await ws_send_json(ws, response)

    if tournament.status > T_STARTED:
        await ws_send_json(ws, tournament.summary)
    elif tournament.top_game is not None:
        await ws_send_json(ws, tournament.top_game_json)

    fullchat_response: FullChatMessage = {
        "type": "fullchat",
        "lines": list(tournament.tourneychat),
    }
    await ws_send_json(ws, fullchat_response)

    await ws_send_json(ws, tournament.duels_json)
    if tournament.system == RR:
        assert isinstance(tournament, RRTournament)
        rr_tournament = tournament
        await ws_send_json(ws, rr_tournament.arrangement_payload(user=user))
        if creator_can_manage:
            await ws_send_json(ws, rr_tournament.rr_management_payload(requested_by=user.username))

    if user.username not in tournament.spectators:
        tournament.spactator_join(user)
        await tournament.broadcast(tournament.spectator_list)

    if not user.is_user_active_in_game() and len(user.lobby_sockets) == 0:
        await app_state.lobby.lobby_broadcast_u_cnt()


async def handle_rr_challenge(
    app: PychessGlobalAppState, ws, user: User, data: TournamentRRChallengeMessage
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return
    result = await rr_tournament.create_arrangement_challenge(user, data["arrangementId"])
    if result is not None:
        await ws_send_json(ws, {"type": "error", "message": result})


async def handle_rr_accept_challenge(
    app: PychessGlobalAppState, ws, user: User, data: TournamentRRChallengeMessage
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return
    result = await rr_tournament.accept_arrangement_challenge(user, data["arrangementId"])
    await ws_send_json(ws, result)


async def handle_rr_annul_game(
    app: PychessGlobalAppState,
    ws,
    user: User,
    data: TournamentRRAnnulGameMessage,
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return

    can_annul = is_tournament_director(user, app) or await creator_can_manage_tournament(
        app, rr_tournament, user.username
    )
    if not can_annul:
        await ws_send_json(ws, {"type": "error", "message": "Permission denied"})
        return

    result = await rr_tournament.annul_arrangement_game(
        data["arrangementId"],
        data["gameId"],
    )
    if result is not None:
        await ws_send_json(ws, {"type": "error", "message": result})


async def handle_rr_set_time(
    app: PychessGlobalAppState, ws, user: User, data: TournamentRRSetTimeMessage
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return

    raw_date = data.get("date")
    try:
        if raw_date:
            parsed_date = datetime.fromisoformat(raw_date)
            parsed_date = (
                parsed_date.replace(tzinfo=UTC)
                if parsed_date.tzinfo is None
                else parsed_date.astimezone(UTC)
            )
        else:
            parsed_date = None
    except (TypeError, ValueError):
        await ws_send_json(ws, {"type": "error", "message": "Invalid round-robin schedule date."})
        return

    result = await rr_tournament.set_arrangement_time(user, data["arrangementId"], parsed_date)
    if result is not None:
        await ws_send_json(ws, {"type": "error", "message": result})


async def handle_rr_manage_player(
    app: PychessGlobalAppState, ws, user: User, data: TournamentRRManagePlayerMessage
) -> None:
    rr_tournament = await load_rr_tournament(app, data["tournamentId"])
    if rr_tournament is None:
        return
    if not await creator_can_manage_tournament(app, rr_tournament, user.username):
        await ws_send_json(ws, {"type": "error", "message": "Permission denied"})
        return

    if data["type"] == "rr_approve_player":
        result = await rr_tournament.rr_approve_player(data["username"])
    elif data["type"] == "rr_deny_player":
        result = await rr_tournament.rr_deny_player(data["username"])
    else:
        result = await rr_tournament.rr_kick_player(data["username"])

    if result is not None:
        await ws_send_json(ws, {"type": "error", "message": result})


async def handle_lobbychat(
    app_state: PychessGlobalAppState, user: User, data: TournamentLobbyChatMessage
) -> None:
    if user.username.startswith(ANON_PREFIX):
        return

    tournamentId = data["tournamentId"]
    tournament = await load_tournament(app_state, tournamentId)
    if TYPE_CHECKING:
        assert tournament is not None
    message = sanitize_user_message(data["message"])
    response: ChatLine | FullChatMessage | None = None
    is_shadowbanned = bool(getattr(user, "shadowban", False))

    director = is_tournament_director(user, app_state)

    if message.startswith(("/startround", "/abort")):
        for socket in tuple(user.tournament_sockets.get(tournamentId, ())):
            await ws_send_json(
                socket,
                {"type": "error", "message": TOURNAMENT_LIFECYCLE_COMMANDS_RETIRED_MESSAGE},
            )
        return

    if director:
        if message.startswith("/silence"):
            parts = message.split()
            if len(parts) >= 2:
                await timeout_public_chat_user(
                    app_state,
                    parts[1],
                    source_chan="tournament",
                    source_room_id=tournamentId,
                    source_room=tournament,
                )
                # timeout_public_chat_user broadcasts the cleaned chat itself.
                return

        elif message.startswith("/shadowban"):
            parts = message.split()
            if len(parts) == 2:
                await set_shadowban(app_state, parts[1], True)

        elif message.startswith("/unshadowban"):
            parts = message.split()
            if len(parts) == 2:
                await set_shadowban(app_state, parts[1], False)

        else:
            if app_state.chat_flood.allow_message(f"public:{user.username}", message):
                lobby_response = chat_response("lobbychat", user.username, message)
                if is_shadowbanned:
                    for ws in tuple(user.tournament_sockets.get(tournamentId, ())):
                        await ws_send_json(ws, lobby_response)
                else:
                    response = lobby_response
                    await tournament.tourney_chat_save(response)

    elif user.anon:
        pass

    else:
        if user.silence == 0 and app_state.chat_flood.allow_message(
            f"public:{user.username}", message
        ):
            lobby_response = chat_response("lobbychat", user.username, message)
            if is_shadowbanned:
                for ws in tuple(user.tournament_sockets.get(tournamentId, ())):
                    await ws_send_json(ws, lobby_response)
            else:
                response = lobby_response
                await tournament.tourney_chat_save(response)

    if response is not None:
        await tournament.broadcast(response)
