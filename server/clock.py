from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from broadcast import round_broadcast
from const import ABORTED
from fairy import BLACK, WHITE
from notify import notify
from typing_defs import NotificationContent
from variants import JANGGI_VARIANTS

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from fairy import FairyBoard
    from game import Game
    from user import User

ESTIMATE_MOVES = 40
CORR_TICK = 60
# Bot games can be created without ever opening a game websocket. For those cases,
# keep a finite "first move" timeout so the game (and its clock task) does not stay
# in memory forever if the human never shows up.
BOT_FIRST_MOVE_TIMEOUT = 5 * 60 * 1000


def first_move_timeout_reason(game: Game, ply: int) -> str:
    if ply >= 2:
        return "flag"
    if game.tournamentArrangementId is not None:
        return "abort"
    if game.tournamentId is None:
        return "abort"
    return "flag"


class Clock:
    """Check game start and time out abandoned games"""

    def __init__(
        self, game: Game, board: FairyBoard | None = None, secs: float | None = None
    ) -> None:
        self.game: Game = game
        self.board: FairyBoard = board if board is not None else game.board
        self.running: bool = False
        self.secs: int | float = -1
        self._generation: int = 0
        self.restart(secs)
        self.clock_task: asyncio.Task[None] | None = asyncio.create_task(
            self.countdown(), name="game-clock-%s" % game.id
        )

    def stop(self) -> int | float:
        self.running = False
        return self.secs

    async def cancel(self) -> None:
        self.stop()

        task = self.clock_task
        self.clock_task = None  # Break strong reference
        current = asyncio.current_task()

        if task and task is not current and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # self.game = None

    def restart(self, secs: float | None = None) -> None:
        # Invalidate ticks and timeout waits belonging to the previous countdown,
        # even when a takeback or time adjustment keeps the same ply and color.
        self._generation += 1
        self.ply: int = self.game.ply
        self.color: int = self.board.color
        if secs is not None:
            self.secs = secs
        else:
            # give some time to make first move
            if self.ply < 2 and not self.game.server_variant.two_boards:
                if self.game.tournamentId is None and not self.game.bot_game:
                    # Non-tournament human games keep unlimited first-move time,
                    # because these sessions are expected to stay active and we
                    # do not want to auto-abort legitimate casual play.
                    self.running = False
                    return
                if self.game.bot_game and self.game.tournamentId is None:
                    # For casual bot games we still want a finite timeout so that
                    # a never-opened game cannot pin memory indefinitely.
                    self.secs = BOT_FIRST_MOVE_TIMEOUT
                else:
                    # Rated games keep their normal first-move timeout.
                    self.secs = self.time_for_first_move
            else:
                # now this same clock object starts measuring the time of the other player - set to what it was when he moved last time
                self.secs = (
                    self.game.clocks_w[-1] if self.color == WHITE else self.game.clocks_b[-1]
                )
        self.running = True

    async def countdown(self) -> None:
        while True:
            generation, ply, color = self._generation, self.ply, self.color
            while self.running and self.secs > 0:
                await asyncio.sleep(1)
                if generation != self._generation or not self.running:
                    break
                self.secs -= 1000

            if generation != self._generation:
                continue

            # Time was running out
            if self.running and self.game.ply == ply:
                # On lichess rage quit waits 10 seconds
                # until the other side gets the win claim,
                # and a disconnection gets 120 seconds.
                if ply >= 2:
                    await asyncio.sleep(20 + self.game.byoyomi_period * self.game.inc)

                if generation != self._generation:
                    continue

                # If FLAG was not received we have to act
                if self.game.status < ABORTED and self.secs <= 0 and self.running:
                    async with self.game.move_lock:
                        # Re-validate after acquiring the move lock. A move may
                        # have been processed while we were waiting, in which case
                        # this timeout belongs to an outdated turn.
                        if (
                            self.game.status >= ABORTED
                            or not self.running
                            or self.secs > 0
                            or generation != self._generation
                            or self.game.ply != ply
                            or self.board.color != color
                        ):
                            continue
                        user = self.game.get_player_at(color, self.board)
                        log.debug("FLAG from server. Secs: %s User: %s", self.secs, user.username)
                        reason = first_move_timeout_reason(self.game, ply)
                        response = await self.game.game_ended(user, reason)
                        await round_broadcast(self.game, response, full=True)
                        # If a clock expires, there may be no further gameState
                        # messages to wake bot queues. Push gameEnd so bot tasks
                        # can exit and release their references.
                        await self._notify_bot_game_end()
                        await self.game.app_state.maybe_remove_finished_game_from_cache_now(
                            self.game
                        )
                    return

            # After stop() we are just waiting for next restart
            await asyncio.sleep(1)

    @property
    def estimate_game_time(self) -> int | float:
        # TODO: calculate with byoyomi
        return (60 * self.game.base) + (ESTIMATE_MOVES * self.game.inc)

    @property
    def time_for_first_move(self) -> int:
        # Fix 45s for janggi because it has setup phase
        if self.game.variant in JANGGI_VARIANTS or self.game.chess960:
            return 45 * 1000

        egt = self.estimate_game_time
        base = 0
        if self.game.tournamentId != "":
            if egt < 30:  # ultra
                base = 11
            elif egt < 180:  # bullet
                base = 16
            elif egt < 480:  # blitz
                base = 21
            elif egt < 1500:  # rapid
                base = 25
            else:  # classical
                base = 30
        else:
            if egt < 30:  # ultra
                base = 15
            elif egt < 180:  # bullet
                base = 20
            elif egt < 480:  # blitz
                base = 25
            elif egt < 1500:  # rapid
                base = 30
            else:  # classical
                base = 35

        return base * 1000

    async def _notify_bot_game_end(self) -> None:
        # This is intentionally conservative: only wake bot queues when a bot
        # is involved, and only if the queue still exists for this game.
        if not self.game.bot_game:
            return
        for player in self.game.all_players:
            if player.bot and self.game.id in player.game_queues:
                await player.game_queues[self.game.id].put(self.game.game_end)


class CorrClock:
    """Correspondence games use 0 + x byoyomi time control, where x is a day"""

    def __init__(self, game: Game) -> None:
        self.game: Game = game
        self.running: bool = False
        self.restart()
        self.time_for_first_move: float = self.mins
        self.clock_task: asyncio.Task[None] | None = asyncio.create_task(
            self.countdown(), name="corr-clock-%s" % game.id
        )
        self.alarm_mins: int = int((self.game.base * 24 * 60) / 5)
        self.alarms: set[int] = set()

    def stop(self) -> float:
        self.running = False
        return self.mins

    async def cancel(self) -> None:
        self.stop()

        task = self.clock_task
        self.clock_task = None  # Break strong reference
        current = asyncio.current_task()

        if task and task is not current and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # self.game = None

    def restart(self, from_db: bool = False) -> None:
        self.ply: int = self.game.ply
        self.color: int = self.game.board.color
        self.mins: float = self.game.base * 24 * 60
        if from_db:
            # For an untouched correspondence game, the current turn started
            # when the game was created. After at least one move, ``l`` is the
            # durable start time of the current turn. Older moved games without
            # ``l`` cannot be reconstructed exactly, so preserve their previous
            # full-clock fallback rather than guessing from the creation date.
            turn_started_at = self.game.last_move_time if self.game.ply > 0 else self.game.date
            if turn_started_at is not None:
                if turn_started_at.tzinfo is None:
                    turn_started_at = turn_started_at.replace(tzinfo=UTC)
                delta = datetime.now(UTC) - turn_started_at
                self.mins -= max(0.0, delta.total_seconds() / 60)
                if self.mins <= 0:
                    # Keep the real expired value. Giving a restarted game a
                    # fresh grace period changes the result merely because the
                    # process restarted; countdown() will now flag/abort it.
                    log.debug("Expired clock in unfinished game %s", self.game.id)
        self.running = True

    async def countdown(self) -> None:
        while True:
            while self.running and self.mins > 0:
                await asyncio.sleep(CORR_TICK)
                self.mins -= 1

                if (
                    self.game.status < ABORTED
                    and self.game.board.ply not in self.alarms
                    and self.mins <= self.alarm_mins
                    and self.mins > self.alarm_mins - 2
                ):
                    user = self.game.bplayer if self.color == BLACK else self.game.wplayer
                    await self.notify_hurry(user)

            if self.game.status < ABORTED and self.mins <= 0 and self.running:
                user = self.game.bplayer if self.color == BLACK else self.game.wplayer
                log.debug("FLAG from server. Mins: %s User: %s", self.mins, user.username)

                reason = first_move_timeout_reason(self.game, self.ply)

                async with self.game.move_lock:
                    response = await self.game.game_ended(user, reason)
                    await round_broadcast(self.game, response, full=True)
                    # Same rationale as in Clock: ensure bot queues receive a
                    # terminal event when the correspondence clock ends a game.
                    await self._notify_bot_game_end()
                    await self.game.app_state.maybe_remove_finished_game_from_cache_now(self.game)
                return

            # After stop() we are just waiting for next restart
            await asyncio.sleep(CORR_TICK)

    async def notify_hurry(self, user: User) -> None:
        opp_name = (
            self.game.wplayer.username
            if self.game.bplayer.username == user.username
            else self.game.bplayer.username
        )

        notif_type = "corrAlarm"
        content: NotificationContent = {
            "id": self.game.id,
            "opp": opp_name,
        }
        await notify(self.game.app_state.db, user, notif_type, content)

        # to prevent creating more than one notification for the same ply
        self.alarms.add(self.game.board.ply)

    async def _notify_bot_game_end(self) -> None:
        # Mirror Clock._notify_bot_game_end so bot tasks do not stick around
        # when a correspondence game ends on time.
        if not self.game.bot_game:
            return
        for player in self.game.all_players:
            if player.bot and self.game.id in player.game_queues:
                await player.game_queues[self.game.id].put(self.game.game_end)
