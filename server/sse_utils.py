from __future__ import annotations

import asyncio
import logging
import sys
from typing import Protocol

from aiohttp import web
from aiohttp_sse import sse_response as aiohttp_sse_response
from const import (
    SSE_GET_TIMEOUT,
    SSE_PING_INTERVAL,
    SSE_SEND_TIMEOUT,
)


class SSEResponse(Protocol):
    def is_connected(self) -> bool: ...

    async def send(self, data: str) -> None: ...


def sse_response(request: web.Request):
    """Configure keepalives and Linux TCP dead-peer detection consistently."""
    return aiohttp_sse_response(
        request,
        send_timeout=SSE_SEND_TIMEOUT,
        ping_interval=SSE_PING_INTERVAL,
    )


def log_sse_failure(endpoint: str) -> None:
    """Ignore expected disconnects but retain tracebacks for unexpected faults."""
    exc = sys.exception()
    if isinstance(exc, OSError):
        return
    logging.getLogger("sse").exception("Unexpected SSE failure in %s", endpoint)


def enqueue_sse_payload(
    queue: asyncio.Queue[str],
    payload: str,
    *,
    replace_pending: bool = False,
) -> bool:
    """Enqueue without blocking; optionally replace an obsolete state snapshot."""
    try:
        queue.put_nowait(payload)
        return True
    except asyncio.QueueShutDown:
        return False
    except asyncio.QueueFull:
        if not replace_pending:
            queue.shutdown(immediate=True)
            return False

    try:
        queue.get_nowait()
        queue.task_done()
    except (asyncio.QueueEmpty, asyncio.QueueShutDown):
        pass

    try:
        queue.put_nowait(payload)
        return True
    except (asyncio.QueueFull, asyncio.QueueShutDown):
        queue.shutdown(immediate=True)
        return False


async def consume_sse_queue(
    response: SSEResponse,
    queue: asyncio.Queue[str],
) -> None:
    while response.is_connected():
        try:
            payload = await asyncio.wait_for(queue.get(), timeout=SSE_GET_TIMEOUT)
        except TimeoutError:
            if not response.is_connected():
                break
            continue
        except asyncio.QueueShutDown:
            break

        try:
            await response.send(payload)
        except TimeoutError:
            break
        finally:
            queue.task_done()
