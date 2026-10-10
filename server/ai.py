from __future__ import annotations

import asyncio
import random
import string
from time import monotonic
from typing import TYPE_CHECKING

import msgspec
from catalogued_variants import catalogued_variant_allows_fishnet
from const import MOVE, STARTED
from fairy import WHITE
from fishnet import has_available_fishnet_worker

if TYPE_CHECKING:
    from game import Game
    from pychess_global_app_state import PychessGlobalAppState
    from user import User
import logging

from utils import play_move

log = logging.getLogger(__name__)

bot_game_tasks: set[asyncio.Task[None]] = set()
# Poll interval for bot queues when no messages are arriving; this prevents
# stuck bot-game tasks from keeping finished games and players alive forever.
BOT_QUEUE_POLL_SECS = 5
_BOT_EVENT_DECODER = msgspec.json.Decoder()


async def BOT_task(bot: User, app_state: PychessGlobalAppState) -> None:
    def parse_bot_event(line: str, queue_name: str, game_id: str = "-"):
        try:
            event = _BOT_EVENT_DECODER.decode(line)
        except msgspec.DecodeError:
            log.error(
                "Invalid JSON in BOT_task() %s queue. bot=%s game=%s line=%r",
                queue_name,
                bot.username,
                game_id,
                line.rstrip("\n"),
            )
            return None

        if not isinstance(event, dict):
            log.error(
                "Invalid JSON event type in BOT_task() %s queue. bot=%s game=%s payload_type=%s line=%r",
                queue_name,
                bot.username,
                game_id,
                type(event).__name__,
                line.rstrip("\n"),
            )
            return None
        return event

    async def game_task(bot: User, game: Game, level: int, random_mover: bool) -> None:
        while game.status <= STARTED:
            try:
                queue = bot.game_queues.get(game.id)
                if queue is None:
                    # The queue was removed during cleanup; exit so this task
                    # does not keep the game referenced.
                    break
                line = await asyncio.wait_for(queue.get(), timeout=BOT_QUEUE_POLL_SECS)
                queue.task_done()
            except TimeoutError:
                # Periodically re-check game status so we can exit even if no
                # further messages are enqueued (e.g., clock/abort endings).
                if game.status > STARTED:
                    break
                continue
            except ValueError:
                log.error(
                    "task_done() called more times than there were items placed in the queue in ai.py game_task()"
                )
            except KeyError:
                log.error("Break in BOT_task() game_task(). %s not in ai.game_queues", game.id)
                if game.status <= STARTED:
                    await game.abort_by_server()
                break

            event = parse_bot_event(line, "game", game.id)
            if event is None or event.get("type") != "gameState":
                continue
            # print("   +++ game_queues get()", event)
            try:
                if random_mover:
                    async with game.move_lock:
                        if game.status > STARTED or game.turn_player != bot.username:
                            continue
                        # A queued event can arrive during the opponent's move.
                        # Read the current position only after acquiring its lock;
                        # cached moves may belong to the previous ply or a reload.
                        legal_moves = game.board.legal_moves()
                        if not legal_moves:
                            log.warning(
                                "No legal moves for bot=%s in game=%s game_task()",
                                bot.username,
                                game.id,
                            )
                            continue
                        await play_move(app_state, bot, game, random.choice(legal_moves))
                elif has_available_fishnet_worker(app_state, variant=game.variant):
                    if not catalogued_variant_allows_fishnet(app_state, game.variant):
                        log.warning(
                            "Aborting bot game %s because Fairy-Stockfish AI is temporarily disabled for variant %s",
                            game.id,
                            game.variant,
                        )
                        await game.abort_by_server()
                        break
                    AI_move(game, level)
                else:
                    log.warning(
                        "Aborting bot game %s because no recent Fairy-Stockfish worker is available",
                        game.id,
                    )
                    await game.abort_by_server()
                    break
            except Exception:
                log.exception(
                    "Break in BOT_task() game_task(). %s BOT play_move/AI_move failed", game.id
                )
                break

    def AI_move(game: Game, level: int) -> None:
        work_id = "".join(random.choice(string.ascii_letters + string.digits) for x in range(6))
        work = {
            "work": {
                "type": "move",
                "id": work_id,
                "level": level,
            },
            "time": monotonic(),
            "game_id": game.id,  # optional
            "position": game.board.initial_fen,  # start position (X-FEN)
            "variant": game.board.variant,
            "chess960": game.chess960,
            "moves": " ".join(game.board.move_stack),  # moves of the game (UCI)
            "nnue": game.board.nnue,
        }
        app_state.fishnet_works[work_id] = work
        app_state.fishnet_queue.put_nowait((MOVE, work_id))

    def start_game_task(
        active_game_tasks: dict[str, asyncio.Task[None]],
        game: Game,
        level: int,
        random_mover: bool,
    ) -> bool:
        if game.id in active_game_tasks:
            return False
        task = asyncio.create_task(
            game_task(bot, game, level, random_mover), name="bot-game-%s" % game.id
        )
        active_game_tasks[game.id] = task
        bot_game_tasks.add(task)

        def _cleanup(done: asyncio.Task[None], game_id: str = game.id) -> None:
            bot_game_tasks.discard(done)
            active_game_tasks.pop(game_id, None)

        task.add_done_callback(_cleanup)
        return True

    # After server restart we may have to wait for fairyfishnet workers to join...
    while not bot.online:
        await asyncio.sleep(3)

    random_mover = bot.username == "Random-Mover"
    active_game_tasks: dict[str, asyncio.Task[None]] = {}

    while not app_state.shutdown:
        line = await bot.event_queue.get()
        try:
            bot.event_queue.task_done()
        except ValueError:
            log.error(
                "task_done() called more times than there were items placed in the queue in ai.py AI_move()"
            )

        event = parse_bot_event(line, "event")
        if event is None:
            continue
        # print("+++ AI event_queue.get()", event)

        if event.get("type") != "gameStart":
            continue

        gameId = event["game"]["id"]
        level = int(event["game"]["skill_level"])
        if gameId not in app_state.games:
            continue
        game = app_state.games[gameId]
        if TYPE_CHECKING:
            assert isinstance(game, Game)

        if not random_mover and not has_available_fishnet_worker(app_state, variant=game.variant):
            log.error("ERROR: No recent fairyfishnet worker capable of %s!", game.variant)
            # TODO: send msg to player
            await game.abort_by_server()
            continue

        started_now = start_game_task(active_game_tasks, game, level, random_mover)
        if not started_now:
            continue

        # Do not execute first move inline in the global event loop: that would
        # serialize startup across many games and increase aborts under stress.
        turn_player = game.wplayer.username if game.board.color == WHITE else game.bplayer.username
        if turn_player == bot.username:
            queue = bot.game_queues.get(game.id)
            if queue is not None:
                queue.put_nowait(game.game_state)
            else:
                log.warning(
                    "Missing game queue for bot=%s game=%s first move trigger",
                    bot.username,
                    game.id,
                )
