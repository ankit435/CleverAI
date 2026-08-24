"""Dedicated background-thread asyncio event loop.

Stagehand's Python SDK is entirely `async` (act/observe/extract/goto/create/close),
while the rest of this codebase (FastAPI sync routes, the LangGraph agent nodes,
`tools/executor.py`) is written synchronously. Rather than infecting the whole
call chain with `async def`, we run one persistent event loop on a single
background thread and submit coroutines to it with `asyncio.run_coroutine_threadsafe`,
blocking the calling (sync) thread until the coroutine completes.

This mirrors the previous `browser/playwright_worker.py` design (single dedicated
thread to preserve driver/session thread-affinity) but is loop-based instead of
task-queue-based since our workload is now natively async.
"""
import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

# Give async Stagehand operations (browser launch, act/observe/extract calls that
# may themselves invoke an LLM) generous headroom before we consider them stuck.
DEFAULT_TIMEOUT_SECONDS = 90.0


class AsyncWorker:
    """Runs an asyncio event loop on one background thread for the process lifetime."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="stagehand-async-worker", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro_factory: Callable[[], Awaitable[T]], timeout: float = DEFAULT_TIMEOUT_SECONDS) -> T:
        """Schedule an async callable on the worker loop and block until it resolves."""
        future: Future = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        return future.result(timeout=timeout)

    def submit_background(self, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        """Fire-and-forget a coroutine on the worker loop (best-effort cleanup tasks)."""
        asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)


# Process-wide singleton — every browser session and Stagehand call runs through
# this one loop/thread, matching the previous single-worker-thread model.
async_worker = AsyncWorker()
