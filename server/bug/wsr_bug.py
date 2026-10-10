from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING

from broadcast import round_broadcast
from const import STARTED
from fairy import FairyBoard
from newid import new_id
from pychess_global_app_state import PychessGlobalAppState
from seek import Seek

from bug.game_bug import GameBug
from bug.utils_bug import join_seek_bughouse, play_move, send_to_team

if TYPE_CHECKING:
    from user import User
    from ws_types import AbortResignMessage, ReconnectMessage

log = logging.getLogger(__name__)


async def handle_reconnect_bughouse(
    app_state: PychessGlobalAppState, user: User, data: ReconnectMessage, game: GameBug
) -> None:
    log.info("Got RECONNECT message %s %r" % (user.username, data))
    moves_queued = data.get("movesQueued")
    # on reconnect use server time. Might be good to log the difference here to see how long a player was disconnected
    game_clocks = game.gameClocks.get_clocks_for_board_msg(full=True)
    # dataA = data.get("lastMaybeSentMsgMoveA")
    # dataB = data.get("lastMaybeSentMsgMoveB")
    async with game.move_lock:
        for move_queued in moves_queued or []:
            if move_queued is None:
                continue
            try:
                await play_move(
                    app_state,
                    user,
                    game,
                    move_queued["move"],
                    game_clocks[0],  # move_queued["clocks"],
                    game_clocks[1],  # move_queued["clocksB"],
                    move_queued["board"],
                )
            except Exception:
                log.exception(
                    "ERROR: Exception in play_move() in %s by %s ",
                    move_queued["gameId"],
                    user.username,
                )


async def handle_draw_bughouse(game: GameBug, user: User) -> None:
    """A draw is offered to the opposing TEAM and answered by either of its members.

    The shared handle_draw() cannot express this. It derives one opponent from
    wplayer/bplayer — board A's two seats — so the other two players are never addressed,
    and it broadcasts without full=True, which reaches spectators only. Both are why a
    bughouse draw offer used to arrive at exactly one of the three other players.
    """
    if game.status > STARTED:
        return

    team = game.team_of(user.username)
    if team is None:
        return  # a spectator cannot offer or accept

    response: Mapping[str, object]
    async with game.move_lock:
        if game.draw_offer_team is None:
            game.draw_offer_team = team
            response = {
                "type": "draw_offer",
                "username": user.username,
                "message": "Draw offered by %s" % user.username,
                "room": "player",
                "user": "",
            }
            game.messages.append(response)
        elif game.draw_offer_team is team:
            # The offering player's partner. They see the offer but do not answer it —
            # a team cannot accept its own draw.
            return
        else:
            game.draw_offer_team = None
            response = await game.game_drawn()

    # Broadcast with full=True so all four players hear it, the offerer included: a
    # player who cannot see that their own offer was sent has no way to tell whether
    # their press registered.
    await round_broadcast(game, response, full=True)


async def handle_reject_draw_bughouse(game: GameBug, user: User) -> None:
    """Only the team being asked can decline, and declining clears the offer for both."""
    team = game.team_of(user.username)
    if team is None or game.draw_offer_team is None or game.draw_offer_team is team:
        return

    game.draw_offer_team = None
    await round_broadcast(
        game, {"type": "draw_rejected", "message": "Draw offer rejected"}, full=True
    )


async def handle_reject_rematch_bughouse(game: GameBug, user: User) -> None:
    """Withdraw this player's own rematch offer.

    With a single ACCEPT control on the answering side there is nothing left to
    "reject" — declining a rematch is simply not accepting it. What this message means
    now is the offerer taking their own offer back, which is the one thing that had no
    way to happen: the button went inert the moment it was pressed and stayed that way
    until somebody else answered.

    The shared handle_reject_rematch() cannot serve. It derives an opponent from
    wplayer/bplayer — board A's two seats — and it never clears `rematch_offers` at all,
    so the offer it announced as rejected was still standing and still counted towards
    the all-four total that starts the rematch.
    """
    if user.username not in game.rematch_offers:
        return

    game.rematch_offers.discard(user.username)
    await round_broadcast(
        game,
        {
            "type": "rematch_rejected",
            # The remaining offers, for the same reason handle_rematch_bughouse sends
            # them: everyone repaints from the set, so a withdrawal that empties it puts
            # every control back to REMATCH, and one that does not leaves the players who
            # are still in it showing CANCEL.
            "offers": sorted(game.rematch_offers),
            "message": "%s withdrew from the rematch" % user.username,
        },
        full=True,
    )


async def handle_resign_bughouse(data: AbortResignMessage, game: GameBug, user: User) -> None:
    # Keep prior behavior tied to board A ply, but avoid calling GameBug.board
    # (a compatibility shim that logs when accidentally used).
    if data["type"] == "abort" and (game is not None) and game.boards["a"].ply > 2:
        return

    if game.status > STARTED:
        # game was already finished!
        # see  https://github.com/pychess/pychess-variants/issues/675
        return

    # Resigning takes both teammates; abort, flag and abandon do not and still end the
    # game where they stand.
    if data["type"] == "resign":
        await handle_resign_request_bughouse(game, user)
        return

    async with game.move_lock:
        response = await game.game_ended(user, data["type"])

    await round_broadcast(game, response, full=True)


async def handle_resign_request_bughouse(game: GameBug, user: User) -> None:
    """Resigning is a two-step decision taken by a team, not by a player.

    A resignation ends the game for both teammates, so one of them should not be able to
    end it alone. The first press asks the partner and changes nothing else; the game ends
    only when the partner presses their own resign control.

    ONE MESSAGE TYPE, not two. The client sends `resign` for both steps and the server
    decides which one this is, so a client cannot confirm a resignation that was never
    asked for and the two steps cannot arrive out of order.

    IN A SIMUL the team is one person holding both seats, so `partner_of()` is None and
    "wait for your partner" would mean waiting for nobody: the game could not be resigned at
    all, which is what it did until 2026-08-30. There the second press IS the partner's press,
    because that player is the whole team. This cannot loosen anything for a normal team: there
    `partner` is a real name, `team_is_one_user` is False, and an offerer pressing twice still
    changes nothing.
    """
    team = game.team_of(user.username)
    if team is None:
        return

    partner = game.partner_of(user.username)
    pending = game.resign_offer
    team_is_one_user = len(set(team)) == 1

    if pending is not None and (
        pending == partner or (team_is_one_user and pending == user.username)
    ):
        async with game.move_lock:
            game.resign_offer = None
            response = await game.game_ended(user, "resign")
        # game_ended() resolves the result by team, so it does not matter which of the two
        # teammates is the one who confirmed.
        await round_broadcast(game, response, full=True)
        return

    if pending is not None:
        # Already asked, by this player or by the other team. Pressing again is not a
        # second question.
        return

    game.resign_offer = user.username
    await send_to_team(
        game,
        team,
        {
            "type": "resign_offer",
            "username": user.username,
            "message": "%s wants to resign" % user.username,
        },
    )


async def handle_rematch_bughouse(
    app_state: PychessGlobalAppState, game: GameBug, user: User
) -> Mapping[str, object]:
    # Use the game's move_lock to ensure atomic operations for rematch functionality
    async with game.move_lock:
        if game.rematch_id is not None:
            response = {"type": "view_rematch", "gameId": game.rematch_id}
            await user.send_game_message(game.id, response)
            return response

        log.info("rematch request by %s.", user)
        rematch_id = None
        other_players = filter(lambda p: p.username != user.username, game.non_bot_players)

        log.info("other_plauers %s.", other_players)
        if all(
            elem in game.rematch_offers
            for elem in (app_state.users[u.username].username for u in other_players)
        ):
            color = "w"  # if game.wplayer.username == opp_name else "b"
            fen = game.initial_fen

            reused_fen = True
            if game.chess960 and game.new_960_fen_needed_for_rematch:
                fen = FairyBoard.start_fen(
                    game.variant, game.chess960, disabled_fen=game.initial_fen.split(" | ")[0]
                )
                reused_fen = False

            seek_id = await new_id(None if app_state.db is None else app_state.db.seek)
            seek = Seek(
                seek_id,
                game.bplayer,
                game.variant,
                fen=fen,
                color=color,
                base=game.base,
                inc=game.inc,
                byoyomi_period=game.byoyomi_period,
                level=game.level,
                rated=game.rated,
                player1=game.bplayer,
                player2=game.wplayer,
                bugPlayer1=game.wplayerB,
                bugPlayer2=game.bplayerB,
                chess960=game.chess960,
                reused_fen=reused_fen,
                is_rematch=True,
            )
            app_state.seeks[seek.id] = seek

            response = await join_seek_bughouse(
                app_state, None, seek.id, None, "all-joined-players-set-generate-response"
            )
            rematch_id = response["gameId"]
            game.rematch_id = rematch_id
            for u in set(game.non_bot_players):
                await u.send_game_message(game.id, response)
        else:
            # THE FIRST PRESS OFFERS; EVERY LATER ONE ACCEPTS. They are the same message
            # to the server — a rematch begins when all four names are in the set — but
            # they are not the same event to a reader, and calling them both "offered"
            # made the chat say a rematch had been offered four times.
            joining = len(game.rematch_offers) > 0
            game.rematch_offers.add(user.username)
            response = {
                "type": "rematch_offer",
                "username": user.username,
                # WHO HAS OFFERED, not just who moved last. Each client decides its own
                # control's state from this: in the list means "I have offered, and I may
                # withdraw", not in it means "someone else has, and I may accept". Sending
                # only the sender left every client guessing, and guessing wrongly — the
                # original offerer saw somebody else's acceptance and turned its own
                # CANCEL into ACCEPT, offering to accept its own rematch.
                "offers": sorted(game.rematch_offers),
                "message": (
                    "%s accepted the rematch" % user.username
                    if joining
                    else "%s offers a rematch" % user.username
                ),
                "room": "player",
                "user": "",
            }
            game.messages.append(response)
            for u in set(game.non_bot_players):
                await u.send_game_message(game.id, response)
        if rematch_id:
            await round_broadcast(game, {"type": "view_rematch", "gameId": rematch_id})

    return response
