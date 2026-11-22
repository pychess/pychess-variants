from __future__ import annotations

from const import DRAW, RATED, STARTED
from variants import JANGGI_VARIANTS


async def draw(game, user, agreement=False):
    """Draw claim or draw offer"""
    if game.is_claimable_draw or agreement:
        result = "1/2-1/2"
        game.update_status(DRAW, result)
        await game.save_game()

        if game.corr:
            opp_player = game.wplayer if user.username == game.bplayer.username else game.bplayer
            await opp_player.notify_game_end(game)

        response = {
            "type": "gameEnd",
            "status": game.status,
            "result": game.result,
            "gameId": game.id,
            "pgn": game.pgn,
            "ct": game.crosstable,
            "rdiffs": (
                {"brdiff": game.brdiff, "wrdiff": game.wrdiff}
                if game.status > STARTED and game.rated == RATED
                else ""
            ),
        }
    else:
        response = {
            "type": "draw_offer",
            "username": user.username,
            "message": "Pass" if game.variant in JANGGI_VARIANTS else "Draw offer sent",
            "room": "player",
            "user": "",
        }

        game.messages.append(response)

        if game.corr:
            await save_draw_offer(game)

    return response


async def reject_draw(game, opp_user):
    response = None

    # Don't send reject_draw message for Makruk BHC.
    if game.board.count_started <= 0 and opp_user.username in game.draw_offers:
        game.draw_offers.clear()
        response = {"type": "draw_rejected", "message": "Draw offer rejected"}

        await save_draw_offer(game)

    return response


async def save_draw_offer(game):
    db = game.app_state.db
    if db is not None:
        await db.game.find_one_and_update(
            {"_id": game.id},
            {
                "$set": {
                    "wd": game.wplayer.username in game.draw_offers,
                    "bd": game.bplayer.username in game.draw_offers,
                }
            },
        )
