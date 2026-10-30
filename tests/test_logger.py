import asyncio
import logging
import logging.config
import os
import unittest
from copy import deepcopy

from logger import DEFAULT_LOGGING_CONFIG, log_context_data, set_log_context


def init_test_logger():
    """Configure quiet test logging, overridable for debugging.

    Production defaults are intentionally verbose, but emitting DEBUG logs from
    hundreds of short-lived aiohttp test apps adds substantial CI I/O overhead.
    Set PYCHESS_TEST_LOG_LEVEL=DEBUG when verbose logs are needed locally.
    """
    level = os.getenv("PYCHESS_TEST_LOG_LEVEL", "WARNING").upper()
    config = deepcopy(DEFAULT_LOGGING_CONFIG)
    config["handlers"]["default"]["level"] = level
    for logger_config in config["loggers"].values():
        logger_config["level"] = level
    logging.config.dictConfig(config)


class LogContextIsolationTest(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_tasks_do_not_share_log_context(self):
        token = log_context_data.set({"username": "parent", "gameId": "parent-game"})
        ready_a = asyncio.Event()
        ready_b = asyncio.Event()
        resume = asyncio.Event()

        async def worker(name: str, game_id: str, ready: asyncio.Event):
            set_log_context("username", name)
            set_log_context("gameId", game_id)
            ready.set()
            await resume.wait()
            return dict(log_context_data.get())

        try:
            task_a = asyncio.create_task(worker("alice", "game-a", ready_a))
            await ready_a.wait()
            task_b = asyncio.create_task(worker("bob", "game-b", ready_b))
            await ready_b.wait()
            resume.set()
            context_a, context_b = await asyncio.gather(task_a, task_b)
            self.assertEqual(context_a, {"username": "alice", "gameId": "game-a"})
            self.assertEqual(context_b, {"username": "bob", "gameId": "game-b"})
            self.assertEqual(
                log_context_data.get(), {"username": "parent", "gameId": "parent-game"}
            )
        finally:
            log_context_data.reset(token)
