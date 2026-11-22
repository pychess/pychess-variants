import asyncio
import json
import unittest
from unittest.mock import patch, sentinel

from header_challenges import _consume_header_channels
from sse_utils import (
    consume_sse_queue,
    enqueue_sse_payload,
    log_sse_failure,
    sse_response,
)


class SlowResponse:
    def is_connected(self) -> bool:
        return True

    async def send(self, _payload: str) -> None:
        async with asyncio.timeout(0.01):
            await asyncio.Event().wait()


class SSEUtilsTestCase(unittest.IsolatedAsyncioTestCase):
    def test_sse_response_configures_transport_and_ping(self) -> None:
        with patch("sse_utils.aiohttp_sse_response", return_value=sentinel.context) as factory:
            response = sse_response(sentinel.request)

        self.assertIs(response, sentinel.context)
        factory.assert_called_once_with(sentinel.request, send_timeout=10, ping_interval=15)

    def test_expected_disconnect_is_not_logged(self) -> None:
        with patch("sse_utils.logging.getLogger") as get_logger:
            try:
                raise ConnectionResetError("browser disconnected")
            except ConnectionResetError:
                log_sse_failure("test")
        get_logger.assert_not_called()

    def test_unexpected_error_is_logged_with_traceback(self) -> None:
        with patch("sse_utils.logging.getLogger") as get_logger:
            try:
                raise RuntimeError("broken subscription")
            except RuntimeError:
                log_sse_failure("test")
        get_logger.return_value.exception.assert_called_once_with(
            "Unexpected SSE failure in %s", "test"
        )

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

    async def test_consumer_does_not_add_an_outer_send_timeout(self) -> None:
        queue = asyncio.Queue[str](maxsize=1)
        queue.put_nowait("event")
        messages: list[str] = []

        class DelayedResponse:
            def is_connected(self) -> bool:
                return True

            async def send(self, payload: str) -> None:
                await asyncio.sleep(0.03)
                messages.append(payload)
                queue.shutdown()

        # The library, not an outer wait_for, owns the transport timeout.
        with patch("sse_utils.SSE_SEND_TIMEOUT", 0.001):
            await asyncio.wait_for(consume_sse_queue(DelayedResponse(), queue), 0.2)

        self.assertEqual(messages, ["event"])
        await asyncio.wait_for(queue.join(), timeout=0.1)

    async def test_consumer_times_out_blocked_send_and_balances_queue(self) -> None:
        queue = asyncio.Queue[str](maxsize=1)
        queue.put_nowait("payload")

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
