"""Thread-safe Playwright Runner to prevent greenlet cross-thread switching errors in FastAPI."""
import threading
import queue
import concurrent.futures
from typing import Callable, Any

class PlaywrightWorker:
    """
    Dedicated single-thread worker that executes all Playwright operations
    to guarantee greenlet thread affinity and zero thread-switching errors.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(PlaywrightWorker, cls).__new__(cls)
                cls._instance._init_worker()
            return cls._instance

    def _init_worker(self):
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="PlaywrightDedicatedWorkerThread"
        )
        self._thread.start()

    def _run_loop(self):
        while True:
            task = self._queue.get()
            if task is None:
                break
            fn, args, kwargs, fut = task
            try:
                res = fn(*args, **kwargs)
                fut.set_result(res)
            except Exception as ex:
                fut.set_exception(ex)
            finally:
                self._queue.task_done()

    def run(self, fn: Callable, *args, timeout: float = 180.0, **kwargs) -> Any:
        """Execute a function synchronously inside the dedicated Playwright worker thread."""
        if threading.current_thread() == self._thread:
            return fn(*args, **kwargs)

        fut = concurrent.futures.Future()
        self._queue.put((fn, args, kwargs, fut))
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Playwright operation timed out after {timeout} seconds")

# Global singleton instance
playwright_worker = PlaywrightWorker()
