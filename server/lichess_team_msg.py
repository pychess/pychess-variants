from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp
from const import T_CREATED
from misc import time_control_str

if TYPE_CHECKING:
    from pychess_global_app_state import PychessGlobalAppState
    from tournament.tournament import Tournament
from settings import (
    DEV,
    LICHESS_API_TOKEN,
    URI,
)

log = logging.getLogger(__name__)

# POST
# Responses:
# 200: {"ok": true}
# 400: {"error": "This request is invalid because [...]"}


async def lichess_team_msg(app_state: PychessGlobalAppState) -> None:
    if DEV or LICHESS_API_TOKEN is None:
        return

    to_date = datetime.now(UTC).date()
    if to_date in app_state.sent_lichess_team_msg:
        log.info("No more lichess team msg for today!")
        return

    team_id = "pychess-tournaments"
    msg = upcoming_tournaments_msgs(app_state.tournaments)
    log.debug("lichess team message: %r", msg)

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": "Bearer %s" % LICHESS_API_TOKEN,
            "Accept": "application/json",
        }

        endpoint = f"https://lichess.org/team/{team_id}/pm-all"
        async with session.post(endpoint, headers=headers, data={"message": msg}) as resp:
            log.info("response status: %r", resp.status)
            json = await resp.json()
            if resp.status == 200 and json.get("ok") is True:
                app_state.sent_lichess_team_msg.append(to_date)
            else:
                log.error("Lichess team message failed (HTTP %s): %s", resp.status, json)


def upcoming_tournaments_msgs(tournaments: Mapping[str, Tournament]) -> str:
    to_date = datetime.now(UTC).date()
    tourney_msgs = []

    for _id, tourney in sorted(tournaments.items(), key=lambda item: item[1].starts_at):
        starts_at = tourney.starts_at
        if tourney.status == T_CREATED and starts_at.date() <= to_date:
            tc = time_control_str(tourney.base, tourney.inc, tourney.byoyomi_period)
            at = starts_at.strftime("%H:%M")
            url = "%s/tournament/%s" % (URI, _id)
            tourney_msgs.append("%s %s starts at today UTC %s\n%s" % (tc, tourney.name, at, url))

    tourney_msgs.append(
        "If you want more notifications (10 min before start) join our Discord https://discord.gg/aPs8RKr and use #self-roles! Thx."
    )

    return "\n\n".join(tourney_msgs)
