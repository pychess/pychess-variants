import asyncio
import json
import unittest
from unittest.mock import patch

from header_challenges import _consume_header_channels
from sse_utils import consume_sse_queue, enqueue_sse_payload


class SlowResponse:
    def is_connected(self) -> bool:
        return True

    async def send(self, _payload: str) -> None:
        await asyncio.Event().wait()


class SSEUtilsTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_enqueue_replaces_pending_payload(self) -> None:
        queue = asyncio.Queue[str](maxsize=1)
        queue.put_nowait("old")

        enqueued = enqueue_sse_payload(queue, "new", replace_pending=True)

        self.assertTrue(enqueued)
        self.assertEqual(queue.qsize(), 1)
        self.assertEqual(queue.get_nowait(), "new")
        queue.task_done()
        await queue.join()

    async def test_event_overflow_shuts_down_and_drains_queue(self) -> None:
        queue = asyncio.Queue[str](maxsize=1)
        queue.put_nowait("old")

        enqueued = enqueue_sse_payload(queue, "new")

        self.assertFalse(enqueued)
        self.assertEqual(queue.qsize(), 0)
        with self.assertRaises(asyncio.QueueShutDown):
            queue.get_nowait()

    async def test_consumer_times_out_blocked_send_and_balances_queue(self) -> None:
        queue = asyncio.Queue[str](maxsize=1)
        queue.put_nowait("payload")

        with patch("sse_utils.SSE_SEND_TIMEOUT", 0.01):
            await consume_sse_queue(SlowResponse(), queue)

        self.assertEqual(queue.qsize(), 0)
        await asyncio.wait_for(queue.join(), timeout=0.1)


class HeaderStreamTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_revoking_one_source_ends_multiplexed_stream(self) -> None:
        delivered = asyncio.Event()
        messages: list[str] = []

        class Response:
            def is_connected(self) -> bool:
                return True

            async def send(self, payload: str) -> None:
                messages.append(payload)
                delivered.set()

        sources = {"challenges": asyncio.Queue[str](), "notifications": asyncio.Queue[str]()}
        sources["notifications"].put_nowait("initial")
        task = asyncio.create_task(_consume_header_channels(Response(), sources))
        try:
            await asyncio.wait_for(delivered.wait(), timeout=1)
            sources["challenges"].shutdown(immediate=True)
            await asyncio.wait_for(task, timeout=1)
            self.assertEqual(
                [{"channel": "notifications", "payload": "initial"}],
                [json.loads(message) for message in messages],
            )
            await asyncio.wait_for(sources["notifications"].join(), timeout=1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_already_revoked_sources_do_not_leave_consumer_waiting(self) -> None:
        sources = {"challenges": asyncio.Queue[str](), "notifications": asyncio.Queue[str]()}
        for source in sources.values():
            source.shutdown(immediate=True)
        await asyncio.wait_for(_consume_header_channels(SlowResponse(), sources), timeout=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
