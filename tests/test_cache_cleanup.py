import asyncio
import unittest
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import ai
import pychess_global_app_state
import test_logger
import user as user_module
import utils
from ai import bot_game_tasks
from aiohttp.test_utils import AioHTTPTestCase
from clock import BOT_FIRST_MOVE_TIMEOUT, Clock, CorrClock
from compress import R2C
from const import ABORTED, BLOCK, CASUAL, FOLLOW, MAX_USER_BLOCK, STARTED, T_FINISHED
from fairy import FairyBoard
from game import Game
from mongomock_motor import AsyncMongoMockClient
from pychess_global_app_state_utils import get_app_state
from seek import Seek
from user import User
from utils import load_game, load_game_from_doc
from variants import get_server_variant
from wsr import finally_logic

from server import make_app

test_logger.init_test_logger()


class CacheCleanupTestCase(AioHTTPTestCase):
    async def get_application(self):
        # Use the in-memory Mongo mock so we can load/save games without touching a real DB.
        app = make_app(db_client=AsyncMongoMockClient(tz_aware=True))
        return app

    async def tearDownAsync(self):
        await self.client.close()

    async def _insert_user_doc(self, username):
        # load_game() expects user documents for non-anon usernames.
        app_state = get_app_state(self.app)
        await app_state.db.user.insert_one({"_id": username})

    async def _wait_for_bot_task(self, game_id):
        # BOT_task registers game tasks with a predictable name; poll until it appears.
        while True:
            for task in list(bot_game_tasks):
                if task.get_name() == f"bot-game-{game_id}":
                    return task
            await asyncio.sleep(0)

    async def test_load_finished_game_cancels_clock(self):
        app_state = get_app_state(self.app)

        await self._insert_user_doc("white")
        await self._insert_user_doc("black")

        variant_code = get_server_variant("chess", False).code
        doc = {
            "_id": "finished-game",
            "us": ["white", "black"],
            "p0": {"e": "1500?"},
            "p1": {"e": "1500?"},
            "v": variant_code,
            "b": 1,
            "i": 0,
            "bp": 0,
            "m": [],
            "d": datetime.now(UTC),
            "f": FairyBoard.start_fen("chess"),
            "s": ABORTED,
            "r": R2C["*"],
            "x": 0,
            "y": int(CASUAL),
            "z": 0,
            "c": False,
        }
        await app_state.db.game.insert_one(doc)

        game = await load_game(app_state, doc["_id"])

        # Finished games must not keep a live clock task; cancel() clears the task ref.
        self.assertIsNone(game.stopwatch.clock_task)
        self.assertIsNone(game.wplayer.game_in_progress)
        self.assertIsNone(game.bplayer.game_in_progress)

    async def test_concurrent_document_loads_share_one_game_construction(self):
        app_state = get_app_state(self.app)
        await self._insert_user_doc("singleflight-white")
        await self._insert_user_doc("singleflight-black")
        doc = {
            "_id": "singleflight-game",
            "us": ["singleflight-white", "singleflight-black"],
            "p0": {"e": "1500?"},
            "p1": {"e": "1500?"},
            "v": get_server_variant("chess", False).code,
            "b": 1,
            "i": 0,
            "bp": 0,
            "m": [],
            "d": datetime.now(UTC),
            "f": FairyBoard.start_fen("chess"),
            "s": -2,
            "r": R2C["*"],
            "x": 0,
            "y": int(CASUAL),
            "z": 0,
            "c": True,
        }
        real_loader = utils._load_game_from_doc
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def delayed_loader(state, loaded_doc):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return await real_loader(state, loaded_doc)

        with patch("utils._load_game_from_doc", side_effect=delayed_loader):
            first = asyncio.create_task(load_game_from_doc(app_state, doc))
            await entered.wait()
            second = asyncio.create_task(load_game_from_doc(app_state, doc))
            await asyncio.sleep(0)
            release.set()
            first_game, second_game = await asyncio.gather(first, second)

        self.assertEqual(1, calls)
        self.assertIs(first_game, second_game)
        self.assertIs(first_game, app_state.games[doc["_id"]])
        self.assertNotIn(doc["_id"], app_state.game_load_tasks)

    async def test_load_finished_game_without_cache_skips_app_cache(self):
        app_state = get_app_state(self.app)

        await self._insert_user_doc("white-no-cache")
        await self._insert_user_doc("black-no-cache")

        variant_code = get_server_variant("chess", False).code
        doc = {
            "_id": "finished-no-cache",
            "us": ["white-no-cache", "black-no-cache"],
            "p0": {"e": "1500?"},
            "p1": {"e": "1500?"},
            "v": variant_code,
            "b": 1,
            "i": 0,
            "bp": 0,
            "m": [],
            "d": datetime.now(UTC),
            "f": FairyBoard.start_fen("chess"),
            "s": ABORTED,
            "r": R2C["*"],
            "x": 0,
            "y": int(CASUAL),
            "z": 0,
            "c": False,
        }
        await app_state.db.game.insert_one(doc)

        game = await load_game(app_state, doc["_id"], cache_finished=False)

        self.assertIsNotNone(game)
        self.assertNotIn(doc["_id"], app_state.games)
        self.assertNotIn(doc["_id"], app_state.game_remove_tasks)
        self.assertIsNone(game.stopwatch.clock_task)
        self.assertIsNone(game.wplayer.game_in_progress)
        self.assertIsNone(game.bplayer.game_in_progress)

    async def test_load_finished_bughouse_cancels_clocks(self):
        app_state = get_app_state(self.app)

        for username in ("wa", "ba", "wb", "bb"):
            await self._insert_user_doc(username)

        variant_code = get_server_variant("bughouse", False).code
        doc = {
            "_id": "finished-bughouse",
            "us": ["wa", "ba", "wb", "bb"],
            "p0": {"e": "1500?"},
            "p1": {"e": "1500?"},
            "p2": {"e": "1500?"},
            "p3": {"e": "1500?"},
            "v": variant_code,
            "b": 1,
            "i": 0,
            "m": [],
            "o": [],
            "d": datetime.now(UTC),
            "f": FairyBoard.start_fen("bughouse"),
            "s": ABORTED,
            "r": R2C["*"],
            "x": 0,
            "y": int(CASUAL),
            "z": 0,
        }
        await app_state.db.game.insert_one(doc)

        game = await load_game(app_state, doc["_id"])

        # Bughouse finished games should cancel both board clock tasks.
        self.assertIsNone(game.gameClocks.stopwatches["a"].clock_task)
        self.assertIsNone(game.gameClocks.stopwatches["b"].clock_task)
        self.assertIsNone(game.wplayerA.game_in_progress)
        self.assertIsNone(game.bplayerA.game_in_progress)
        self.assertIsNone(game.wplayerB.game_in_progress)
        self.assertIsNone(game.bplayerB.game_in_progress)

    async def test_load_finished_bughouse_without_cache_skips_app_cache_and_in_progress(self):
        app_state = get_app_state(self.app)

        for username in ("wa-no-cache", "ba-no-cache", "wb-no-cache", "bb-no-cache"):
            await self._insert_user_doc(username)

        variant_code = get_server_variant("bughouse", False).code
        doc = {
            "_id": "finished-bughouse-no-cache",
            "us": ["wa-no-cache", "ba-no-cache", "wb-no-cache", "bb-no-cache"],
            "p0": {"e": "1500?"},
            "p1": {"e": "1500?"},
            "p2": {"e": "1500?"},
            "p3": {"e": "1500?"},
            "v": variant_code,
            "b": 1,
            "i": 0,
            "m": [],
            "o": [],
            "d": datetime.now(UTC),
            "f": FairyBoard.start_fen("bughouse"),
            "s": ABORTED,
            "r": R2C["*"],
            "x": 0,
            "y": int(CASUAL),
            "z": 0,
        }
        await app_state.db.game.insert_one(doc)

        game = await load_game(app_state, doc["_id"], cache_finished=False)

        self.assertIsNotNone(game)
        self.assertNotIn(doc["_id"], app_state.games)
        self.assertNotIn(doc["_id"], app_state.game_remove_tasks)
        self.assertIsNone(game.wplayerA.game_in_progress)
        self.assertIsNone(game.bplayerA.game_in_progress)
        self.assertIsNone(game.wplayerB.game_in_progress)
        self.assertIsNone(game.bplayerB.game_in_progress)

    async def test_finished_game_is_evicted_when_last_spectator_disconnects(self):
        app_state = get_app_state(self.app)

        await self._insert_user_doc("white-viewer")
        await self._insert_user_doc("black-viewer")

        variant_code = get_server_variant("chess", False).code
        doc = {
            "_id": "finished-evict",
            "us": ["white-viewer", "black-viewer"],
            "p0": {"e": "1500?"},
            "p1": {"e": "1500?"},
            "v": variant_code,
            "b": 1,
            "i": 0,
            "bp": 0,
            "m": [],
            "d": datetime.now(UTC),
            "f": FairyBoard.start_fen("chess"),
            "s": ABORTED,
            "r": R2C["*"],
            "x": 0,
            "y": int(CASUAL),
            "z": 0,
            "c": False,
        }
        await app_state.db.game.insert_one(doc)

        game = await load_game(app_state, doc["_id"])
        viewer = User(app_state, username="viewer")
        app_state.users[viewer.username] = viewer
        ws = object()
        viewer.add_ws_for_game(game.id, ws)
        game.spectators.add(viewer)

        await finally_logic(app_state, ws, viewer, game)

        self.assertNotIn(doc["_id"], app_state.games)
        self.assertNotIn(doc["_id"], app_state.game_remove_tasks)

    async def test_finished_game_stays_cached_while_analysis_is_pending(self):
        app_state = get_app_state(self.app)

        await self._insert_user_doc("white-analysis")
        await self._insert_user_doc("black-analysis")

        variant_code = get_server_variant("chess", False).code
        doc = {
            "_id": "finished-analysis",
            "us": ["white-analysis", "black-analysis"],
            "p0": {"e": "1500?"},
            "p1": {"e": "1500?"},
            "v": variant_code,
            "b": 1,
            "i": 0,
            "bp": 0,
            "m": [],
            "d": datetime.now(UTC),
            "f": FairyBoard.start_fen("chess"),
            "s": ABORTED,
            "r": R2C["*"],
            "x": 0,
            "y": int(CASUAL),
            "z": 0,
            "c": False,
        }
        await app_state.db.game.insert_one(doc)

        game = await load_game(app_state, doc["_id"])
        viewer = User(app_state, username="analysis-viewer")
        app_state.users[viewer.username] = viewer
        ws = object()
        viewer.add_ws_for_game(game.id, ws)
        game.spectators.add(viewer)
        app_state.fishnet_works["pending-analysis"] = {
            "work": {"type": "analysis", "id": "pending-analysis"},
            "game_id": game.id,
            "time": monotonic(),
        }

        await finally_logic(app_state, ws, viewer, game)

        self.assertIn(doc["_id"], app_state.games)
        self.assertIn(doc["_id"], app_state.game_remove_tasks)

        app_state.fishnet_works.clear()
        await app_state.remove_game_from_cache_now(game)

    async def test_bot_first_move_timeout_enabled(self):
        app_state = get_app_state(self.app)

        human = User(app_state, username="human")
        app_state.users[human.username] = human

        bot = app_state.users["Random-Mover"]

        game = Game(
            app_state,
            "bot-timeout",
            "chess",
            "",
            human,
            bot,
            base=1,
            inc=0,
            rated=False,
        )

        # Bot games should not keep an unlimited first-move clock in casual mode.
        self.assertTrue(game.stopwatch.running)
        self.assertEqual(game.stopwatch.secs, BOT_FIRST_MOVE_TIMEOUT)

    async def test_clock_timeout_notifies_bot_queue(self):
        app_state = get_app_state(self.app)

        human = User(app_state, username="human2")
        app_state.users[human.username] = human

        bot = app_state.users["Random-Mover"]
        game = Game(
            app_state,
            "bot-clock",
            "chess",
            "",
            human,
            bot,
            base=1,
            inc=0,
            rated=False,
        )
        bot.game_queues[game.id] = asyncio.Queue()

        # Force the clock to expire immediately without waiting real time.
        game.stopwatch.secs = 0
        game.stopwatch.running = True

        msg = await asyncio.wait_for(bot.game_queues[game.id].get(), timeout=1)

        # When the clock ends the game, the bot queue should receive a gameEnd.
        self.assertEqual(msg, game.game_end)

    async def test_bot_game_task_exits_without_messages(self):
        app_state = get_app_state(self.app)

        human = User(app_state, username="human3")
        app_state.users[human.username] = human

        bot = app_state.users["Random-Mover"]
        bot.game_queues.clear()

        game = Game(
            app_state,
            "bot-task",
            "chess",
            "",
            human,
            bot,
            base=1,
            inc=0,
            rated=False,
        )
        app_state.games[game.id] = game
        bot.game_queues[game.id] = asyncio.Queue()

        # Make the polling interval tiny so the test completes quickly.
        original_poll = ai.BOT_QUEUE_POLL_SECS
        ai.BOT_QUEUE_POLL_SECS = 0.01
        try:
            await bot.event_queue.put(game.game_start)
            task = await asyncio.wait_for(self._wait_for_bot_task(game.id), timeout=1)

            self.assertFalse(task.done())

            # End the game without enqueuing any gameState messages.
            game.status = ABORTED

            # The bot task should notice the status change and exit promptly.
            await asyncio.wait_for(task, timeout=1)
            self.assertTrue(task.done())
        finally:
            ai.BOT_QUEUE_POLL_SECS = original_poll

    async def test_random_mover_selects_current_moves_after_waiting_for_game_lock(self):
        app_state = get_app_state(self.app)
        human = User(app_state, username="bot-race-human")
        app_state.users[human.username] = human
        bot = app_state.users["Random-Mover"]
        game = Game(app_state, "bot-lock-race", "chess", "", human, bot, rated=False)
        app_state.games[game.id] = game
        bot.game_queues[game.id] = asyncio.Queue()
        waiting = asyncio.Event()
        moved = asyncio.Event()
        attempted_moves = []

        class ObservedLock(asyncio.Lock):
            async def __aenter__(self):
                waiting.set()
                return await super().__aenter__()

        game.move_lock = ObservedLock()
        await game.move_lock.acquire()

        async def observed_play_move(app_state, user, game, move):
            attempted_moves.append(move)
            try:
                await utils.play_move(app_state, user, game, move)
            finally:
                moved.set()

        # Prefer a White move when given the old list, making the race fail
        # deterministically instead of depending on random.choice().
        def choose_move(moves):
            return "d2d4" if "d2d4" in moves else moves[0]

        task = None
        try:
            with (
                patch("ai.play_move", side_effect=observed_play_move),
                patch("ai.random.choice", side_effect=choose_move),
            ):
                await bot.event_queue.put(game.game_start)
                task = await asyncio.wait_for(self._wait_for_bot_task(game.id), timeout=1)
                # Bots also receive their own gameState events. Such an event
                # can be consumed while the next human move holds the lock.
                await bot.game_queues[game.id].put(game.game_state)
                await asyncio.wait_for(waiting.wait(), timeout=1)
                await game.play_move("e2e4", clocks=[300000, 300000], ply=1)
                current_moves = game.board.legal_moves()
                game.move_lock.release()
                await asyncio.wait_for(moved.wait(), timeout=1)

                self.assertEqual(len(attempted_moves), 1)
                self.assertIn(attempted_moves[0], current_moves)
                self.assertEqual(game.ply, 2)
                self.assertEqual(game.status, STARTED)
                self.assertEqual(game.result, "*")
        finally:
            if game.move_lock.locked():
                game.move_lock.release()
            game.status = ABORTED
            await bot.game_queues[game.id].put(game.game_end)
            if task is not None:
                await asyncio.wait_for(task, timeout=1)

    async def test_random_mover_ignores_opponent_turn_before_reading_legal_moves(self):
        app_state = get_app_state(self.app)
        human = User(app_state, username="bot-turn-human")
        app_state.users[human.username] = human
        bot = app_state.users["Random-Mover"]
        game = Game(app_state, "bot-opponent-turn", "chess", "", human, bot, rated=False)
        app_state.games[game.id] = game
        bot.game_queues[game.id] = asyncio.Queue()
        processed = asyncio.Event()

        class ObservedLock(asyncio.Lock):
            async def __aexit__(self, *args):
                await super().__aexit__(*args)
                processed.set()

        game.move_lock = ObservedLock()
        await bot.event_queue.put(game.game_start)
        task = await asyncio.wait_for(self._wait_for_bot_task(game.id), timeout=1)
        try:
            with patch.object(game.board, "legal_moves") as legal_moves:
                await bot.game_queues[game.id].put(game.game_state)
                await asyncio.wait_for(processed.wait(), timeout=1)
                legal_moves.assert_not_called()
                self.assertEqual(game.ply, 0)
        finally:
            game.status = ABORTED
            await bot.game_queues[game.id].put(game.game_end)
            await asyncio.wait_for(task, timeout=1)

    async def test_bot_task_ignores_invalid_event_queue_json(self):
        app_state = get_app_state(self.app)

        human = User(app_state, username="human5")
        app_state.users[human.username] = human

        bot = app_state.users["Random-Mover"]
        bot.game_queues.clear()

        game = Game(
            app_state,
            "bot-bad-event-json",
            "chess",
            "",
            human,
            bot,
            base=1,
            inc=0,
            rated=False,
        )
        app_state.games[game.id] = game
        bot.game_queues[game.id] = asyncio.Queue()

        # Make the polling interval tiny so task shutdown checks complete quickly.
        original_poll = ai.BOT_QUEUE_POLL_SECS
        ai.BOT_QUEUE_POLL_SECS = 0.01
        try:
            # A malformed event must not terminate BOT_task's event loop.
            await bot.event_queue.put('{"type":"gameStart","game":{"id":"broken","skill_level":}}')
            await bot.event_queue.put(game.game_start)

            task = await asyncio.wait_for(self._wait_for_bot_task(game.id), timeout=1)
            self.assertFalse(task.done())

            game.status = ABORTED
            await asyncio.wait_for(task, timeout=1)
            self.assertTrue(task.done())
        finally:
            ai.BOT_QUEUE_POLL_SECS = original_poll

    async def test_bot_game_task_ignores_invalid_game_queue_json(self):
        app_state = get_app_state(self.app)

        human = User(app_state, username="human6")
        app_state.users[human.username] = human

        bot = app_state.users["Random-Mover"]
        bot.game_queues.clear()

        game = Game(
            app_state,
            "bot-bad-game-json",
            "chess",
            "",
            human,
            bot,
            base=1,
            inc=0,
            rated=False,
        )
        app_state.games[game.id] = game
        bot.game_queues[game.id] = asyncio.Queue()

        # Make the polling interval tiny so the test completes quickly.
        original_poll = ai.BOT_QUEUE_POLL_SECS
        ai.BOT_QUEUE_POLL_SECS = 0.01
        try:
            await bot.event_queue.put(game.game_start)
            task = await asyncio.wait_for(self._wait_for_bot_task(game.id), timeout=1)

            # A malformed game event must not terminate the per-game bot task.
            await bot.game_queues[game.id].put(
                '{"type":"gameState","moves":"e2e4","wtime":1000,"btime":}'
            )
            await asyncio.sleep(0.05)
            self.assertFalse(task.done())

            game.status = ABORTED
            await asyncio.wait_for(task, timeout=1)
            self.assertTrue(task.done())
        finally:
            ai.BOT_QUEUE_POLL_SECS = original_poll

    async def test_remove_from_cache_prunes_idle_anon(self):
        app_state = get_app_state(self.app)

        anon = User(app_state, username="AnonTest", anon=True)
        app_state.users[anon.username] = anon

        human = User(app_state, username="human4")
        app_state.users[human.username] = human

        game = Game(
            app_state,
            "anon-cleanup",
            "chess",
            "",
            anon,
            human,
            base=1,
            inc=0,
            rated=False,
        )

        # Mark the game as finished so game_in_progress is cleared.
        game.update_status(ABORTED, "*")

        # Avoid waiting in remove_from_cache during tests.
        original_keep = pychess_global_app_state.LOCALHOST_CACHE_KEEP_TIME
        pychess_global_app_state.LOCALHOST_CACHE_KEEP_TIME = 0
        try:
            await app_state.remove_from_cache(game)
        finally:
            pychess_global_app_state.LOCALHOST_CACHE_KEEP_TIME = original_keep

        # An idle anon user should be removed from the cache and have no running cleanup task.
        self.assertNotIn(anon.username, app_state.users)
        self.assertIsNone(anon.remove_anon_task)

    async def test_remove_game_from_cache_now_clears_stale_game_in_progress(self):
        app_state = get_app_state(self.app)

        white = User(app_state, username="cleanup-white")
        black = User(app_state, username="cleanup-black")
        app_state.users[white.username] = white
        app_state.users[black.username] = black

        game = Game(
            app_state,
            "cleanup-stale-gip",
            "chess",
            "",
            white,
            black,
            base=1,
            inc=0,
            rated=False,
        )
        app_state.games[game.id] = game

        # Simulate a stale in-progress reference that can happen when games are
        # loaded/evicted across reconnects.
        white.game_in_progress = game.id
        black.game_in_progress = game.id

        await app_state.remove_game_from_cache_now(game)

        self.assertIsNone(white.game_in_progress)
        self.assertIsNone(black.game_in_progress)
        self.assertNotIn(game.id, app_state.games)

    async def test_concurrent_registered_user_loads_are_singleflight_and_fully_initialized(self):
        app_state = get_app_state(self.app)
        username = "singleflight-user"
        await self._insert_user_doc(username)
        await app_state.db.relation.insert_many(
            [
                {
                    "_id": f"{username}/blocked-{i}",
                    "u1": username,
                    "u2": f"blocked-{i}",
                    "r": BLOCK,
                }
                for i in range(MAX_USER_BLOCK + 1)
            ]
            + [
                {
                    "_id": f"{username}/followed",
                    "u1": username,
                    "u2": "followed",
                    "r": FOLLOW,
                }
            ]
        )

        collection_type = type(app_state.db.relation)
        real_find = collection_type.find
        entered = asyncio.Event()
        release = asyncio.Event()
        relation_find_calls = 0

        class DelayedCursor:
            def __init__(self, cursor):
                self.cursor = cursor

            async def to_list(self, length):
                entered.set()
                await release.wait()
                return await self.cursor.to_list(length)

        def delayed_find(collection, *args, **kwargs):
            cursor = real_find(collection, *args, **kwargs)
            if collection.name != "relation":
                return cursor
            nonlocal relation_find_calls
            relation_find_calls += 1
            return DelayedCursor(cursor)

        with patch.object(collection_type, "find", delayed_find):
            first = asyncio.create_task(app_state.users.get(username))
            entered_wait = asyncio.create_task(entered.wait())
            done, _ = await asyncio.wait({first, entered_wait}, return_when=asyncio.FIRST_COMPLETED)
            if first in done:
                await first
            await entered_wait

            # Never expose the freshly constructed User with empty relation sets.
            self.assertNotIn(username, app_state.users.data)

            second = asyncio.create_task(app_state.users.get(username))
            await asyncio.sleep(0)
            self.assertFalse(second.done())

            release.set()
            first_user, second_user = await asyncio.gather(first, second)

        await asyncio.sleep(0)
        self.assertEqual(1, relation_find_calls)
        self.assertIs(first_user, second_user)
        self.assertIs(first_user, app_state.users[username])
        self.assertEqual(MAX_USER_BLOCK, len(first_user.blocked))
        self.assertEqual({"followed"}, first_user.following)
        self.assertNotIn(username, app_state.users.load_tasks)

    async def test_registered_user_cache_evicts_only_idle_unreferenced_users(self):
        app_state = get_app_state(self.app)
        for username in ("cache-idle", "cache-fresh", "cache-protected"):
            await self._insert_user_doc(username)

        idle = await app_state.users.get("cache-idle")
        fresh = await app_state.users.get("cache-fresh")
        protected = await app_state.users.get("cache-protected")
        app_state.users.cache_access[idle.username] = 100
        app_state.users.cache_access[fresh.username] = 950
        app_state.users.cache_access[protected.username] = 100

        evicted = app_state.users.prune_registered_cache(
            {protected},
            max_idle_seconds=300,
            now=1000,
        )

        self.assertEqual(["cache-idle"], evicted)
        self.assertNotIn(idle.username, app_state.users)
        self.assertNotIn(idle.username, app_state.users.cache_access)
        self.assertIn(fresh.username, app_state.users)
        self.assertIn(protected.username, app_state.users)
        self.assertEqual(1, app_state.users.registered_cache_evictions)

        anon = User(app_state, username="Anon-cache-tracking", anon=True)
        app_state.users[anon.username] = anon
        self.assertNotIn(anon.username, app_state.users.cache_access)

    async def test_registered_user_cache_enumeration_does_not_refresh_access(self):
        app_state = get_app_state(self.app)
        await self._insert_user_doc("cache-enumerated")
        user = await app_state.users.get("cache-enumerated")
        app_state.users.cache_access[user.username] = 100

        self.assertIn(user, list(app_state.users.values()))
        self.assertIn((user.username, user), list(app_state.users.items()))
        self.assertEqual(100, app_state.users.cache_access[user.username])

        with patch("users.monotonic", return_value=200):
            self.assertIs(user, app_state.users[user.username])
        self.assertEqual(200, app_state.users.cache_access[user.username])

    async def test_registered_user_cache_protects_players_in_cached_finished_game(self):
        app_state = get_app_state(self.app)
        for username in ("cache-game-white", "cache-game-black"):
            await self._insert_user_doc(username)

        white = await app_state.users.get("cache-game-white")
        black = await app_state.users.get("cache-game-black")
        game = Game(
            app_state,
            "registered-cache-game",
            "chess",
            "",
            white,
            black,
            base=1,
            inc=0,
            rated=False,
        )
        game.update_status(ABORTED, "*")
        app_state.games[game.id] = game
        app_state.users.cache_access[white.username] = 100
        app_state.users.cache_access[black.username] = 100

        evicted = app_state.users.prune_registered_cache(
            app_state.registered_user_cache_references(),
            max_idle_seconds=300,
            now=1000,
        )

        self.assertEqual([], evicted)
        self.assertIn(white.username, app_state.users)
        self.assertIn(black.username, app_state.users)

        del app_state.games[game.id]
        evicted = app_state.users.prune_registered_cache(
            app_state.registered_user_cache_references(),
            max_idle_seconds=300,
            now=1000,
        )
        self.assertCountEqual([white.username, black.username], evicted)

    async def test_finished_tournament_cache_waits_for_active_socket(self):
        app_state = get_app_state(self.app)
        tournament_id = "finished-cache-active"
        viewer = User(app_state, username="finished-cache-viewer")
        app_state.users[viewer.username] = viewer

        class DummySocket:
            closed = False

            async def close(self):
                self.closed = True

        socket = DummySocket()
        tournament = SimpleNamespace(
            id=tournament_id,
            status=T_FINISHED,
            clock_task=None,
            players={viewer: object()},
            player_keys_by_name={viewer.username: viewer},
            bye_players=[],
            spectators=set(),
        )
        before_stats = app_state.tournament_cache_stats()
        app_state.tournaments[tournament_id] = cast(Any, tournament)
        viewer.tournament_sockets[tournament_id] = {cast(Any, socket)}
        app_state.tourneysockets[tournament_id] = {
            viewer.username: viewer.tournament_sockets[tournament_id]
        }

        with patch.object(pychess_global_app_state, "LOCALHOST_CACHE_KEEP_TIME", 0.01):
            app_state.schedule_tournament_cache_removal(cast(Any, tournament))
            task = app_state.tournament_remove_tasks[tournament_id]
            await asyncio.sleep(0.04)

            self.assertIn(tournament_id, app_state.tournaments)
            stats = app_state.tournament_cache_stats()
            self.assertEqual(
                stats["finished_tournaments"],
                before_stats["finished_tournaments"] + 1,
            )
            self.assertEqual(
                stats["finished_tournament_user_references"],
                before_stats["finished_tournament_user_references"] + 1,
            )
            self.assertEqual(
                stats["tournament_active_sockets"],
                before_stats["tournament_active_sockets"] + 1,
            )

            socket.closed = True
            await asyncio.wait_for(task, timeout=0.2)

        self.assertNotIn(tournament_id, app_state.tournaments)
        self.assertNotIn(tournament_id, app_state.tourneysockets)
        self.assertNotIn(tournament_id, app_state.tournament_cache_access)
        self.assertNotIn(tournament_id, viewer.tournament_sockets)

    async def test_finished_tournament_cache_refreshes_idle_deadline(self):
        app_state = get_app_state(self.app)
        tournament_id = "finished-cache-refresh"
        tournament = SimpleNamespace(
            id=tournament_id,
            status=T_FINISHED,
            clock_task=None,
            players={},
            player_keys_by_name={},
            bye_players=[],
            spectators=set(),
        )
        app_state.tournaments[tournament_id] = cast(Any, tournament)
        app_state.tourneysockets[tournament_id] = {}

        with patch.object(pychess_global_app_state, "LOCALHOST_CACHE_KEEP_TIME", 0.05):
            app_state.schedule_tournament_cache_removal(cast(Any, tournament))
            task = app_state.tournament_remove_tasks[tournament_id]
            first_access = app_state.tournament_cache_access[tournament_id]
            await asyncio.sleep(0.03)

            app_state.schedule_tournament_cache_removal(cast(Any, tournament))
            self.assertGreater(app_state.tournament_cache_access[tournament_id], first_access)
            await asyncio.sleep(0.03)
            self.assertIn(tournament_id, app_state.tournaments)

            await asyncio.wait_for(task, timeout=0.1)

        self.assertNotIn(tournament_id, app_state.tournaments)

    async def test_user_remove_ignores_missing_cache_entry(self):
        app_state = get_app_state(self.app)
        ghost = User(app_state, username="Anon-missing-cleanup")
        ghost.online = False

        async def no_sleep(_seconds):
            return None

        with patch.object(user_module.asyncio, "sleep", new=no_sleep):
            await ghost.remove()

        self.assertNotIn(ghost.username, app_state.users)

    async def test_user_remove_does_not_delete_replaced_instance(self):
        app_state = get_app_state(self.app)
        old_user = User(app_state, username="Anon-replaced-cleanup")
        new_user = User(app_state, username="Anon-replaced-cleanup")
        app_state.users[old_user.username] = new_user
        old_user.online = False

        async def no_sleep(_seconds):
            return None

        with patch.object(user_module.asyncio, "sleep", new=no_sleep):
            await old_user.remove()

        self.assertIn(old_user.username, app_state.users)
        self.assertIs(app_state.users[old_user.username], new_user)

    async def test_user_remove_cleans_up_invites_for_removed_anon(self):
        app_state = get_app_state(self.app)
        anon = User(app_state, username="Anon-invite-cleanup", anon=True)
        app_state.users[anon.username] = anon

        invite = Seek(
            "seek-invite-cleanup",
            anon,
            "chess",
            target="Invite-friend",
            player1=anon,
            game_id="invitegame",
        )
        app_state.seeks[invite.id] = invite
        app_state.invites[invite.game_id] = invite
        anon.seeks[invite.id] = invite
        anon.online = False

        async def no_sleep(_seconds):
            return None

        with patch.object(user_module.asyncio, "sleep", new=no_sleep):
            await anon.remove()

        self.assertNotIn(anon.username, app_state.users)
        self.assertNotIn(invite.id, app_state.seeks)
        self.assertNotIn(invite.game_id, app_state.invites)
        self.assertEqual({}, anon.seeks)

    async def test_user_remove_uses_fast_timeout_for_never_connected_anon(self):
        app_state = get_app_state(self.app)
        anon = User(app_state, username="Anon-fast-cleanup", anon=True)
        app_state.users[anon.username] = anon

        # Keep this test deterministic: we drive remove() directly.
        if anon.remove_anon_task is not None:
            anon.remove_anon_task.cancel()
            with suppress(asyncio.CancelledError):
                await anon.remove_anon_task
            anon.remove_anon_task = None

        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        with (
            patch.object(user_module, "URI", "https://prod.test"),
            patch.object(user_module, "ANON_NEVER_CONNECTED_TIMEOUT", 7),
            patch.object(user_module.asyncio, "sleep", new=fake_sleep),
        ):
            await anon.remove()

        self.assertEqual([7, 3], sleeps[:2])
        self.assertNotIn(anon.username, app_state.users)
        self.assertIsNone(anon.remove_anon_task)

    async def test_user_remove_skips_fast_timeout_after_socket_activity(self):
        app_state = get_app_state(self.app)
        anon = User(app_state, username="Anon-connected-cleanup", anon=True)
        app_state.users[anon.username] = anon

        if anon.remove_anon_task is not None:
            anon.remove_anon_task.cancel()
            with suppress(asyncio.CancelledError):
                await anon.remove_anon_task
            anon.remove_anon_task = None

        # Simulate a user who had any socket activity at least once.
        anon.ever_connected = True
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            raise RuntimeError("stop-after-first-sleep")

        with (
            patch.object(user_module, "URI", "https://prod.test"),
            patch.object(user_module, "ANON_TIMEOUT", 123),
            patch.object(user_module, "ANON_NEVER_CONNECTED_TIMEOUT", 7),
            patch.object(user_module.asyncio, "sleep", new=fake_sleep),
            self.assertRaises(RuntimeError),
        ):
            await anon.remove()

        self.assertEqual([123], sleeps)
        self.assertIn(anon.username, app_state.users)

    async def test_clock_cancel_skips_awaiting_current_task(self):
        clock = object.__new__(Clock)
        clock.running = True
        clock.secs = 1
        clock.clock_task = asyncio.current_task()

        await Clock.cancel(clock)

        self.assertFalse(clock.running)
        self.assertIsNone(clock.clock_task)

    async def test_corr_clock_cancel_skips_awaiting_current_task(self):
        clock = object.__new__(CorrClock)
        clock.running = True
        clock.mins = 1
        clock.clock_task = asyncio.current_task()

        await CorrClock.cancel(clock)

        self.assertFalse(clock.running)
        self.assertIsNone(clock.clock_task)


if __name__ == "__main__":
    unittest.main()
