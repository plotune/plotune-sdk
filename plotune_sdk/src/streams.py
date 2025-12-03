# src/streams.py
import asyncio
import secrets
from multiprocessing import Process, Queue
from typing import Callable, Any, Dict, List, Optional
from plotune_sdk.src.workers.consume_worker import worker_entry
from plotune_sdk.utils import get_logger

logger = get_logger("plotune_stream")


class PlotuneStream:
    def __init__(self, runtime, stream_name: str):
        self.runtime = runtime
        self.stream_name = stream_name
        self.username: Optional[str] = None

        # handlers[group] = [async_handler_func, ...]
        self.handlers: Dict[str, List[Callable[[Any], Any]]] = {}

        # per-group state
        self.workers: Dict[str, Process] = {}
        self.queues: Dict[str, Queue] = {}
        self._queue_tasks: Dict[str, asyncio.Task] = {}

    # -----------------------------------------------------------------
    # API for registering consume handlers
    # -----------------------------------------------------------------
    def on_consume(self, group_name: Optional[str] = None):
        group = group_name or secrets.token_hex(4)

        def decorator(func: Callable[[Any], Any]):
            # handler must be a coroutine function (async def)
            if not asyncio.iscoroutinefunction(func):
                raise TypeError("Handler must be an async function (async def).")
            self.handlers.setdefault(group, []).append(func)
            logger.info(f"Registered handler for group={group}: {func}")
            return func

        return decorator

    # -----------------------------------------------------------------
    # Start all workers (one per registered group)
    # -----------------------------------------------------------------
    async def start(self, token: str):
        if not self.username:
            raise RuntimeError("Username must be assigned before calling start()")

        for group in list(self.handlers.keys()):
            if group in self.workers:
                logger.debug(f"Worker for group={group} already running, skipping")
                continue
            await self._start_worker_for_group(group, token)

    async def _start_worker_for_group(self, group: str, token: str):
        """
        Create a multiprocessing.Queue for this group, start worker process,
        and start an async reader task that dispatches messages to handlers.
        """
        q = Queue()
        p = Process(
            target=worker_entry,
            args=(self.username, self.stream_name, group, token, q),
            daemon=True,
        )
        p.start()

        self.queues[group] = q
        self.workers[group] = p

        # start async queue reader task (non-blocking)
        task = asyncio.create_task(self._queue_reader(group, q))
        self._queue_tasks[group] = task

        logger.info(f"[{group}] Worker started PID={p.pid}")

    # -----------------------------------------------------------------
    # Async queue reader - uses asyncio.to_thread to avoid blocking event loop
    # -----------------------------------------------------------------
    async def _queue_reader(self, group: str, q: Queue):
        """
        Continuously read from multiprocessing.Queue using a background thread
        (via asyncio.to_thread) so main loop is never blocked.
        """
        handlers = self.handlers.get(group, [])
        logger.info(f"[{group}] Queue reader started (async)")

        try:
            while True:
                # blocking queue.get executed in a separate thread
                try:
                    item = await asyncio.to_thread(q.get)
                except asyncio.CancelledError:
                    # task was cancelled -> break
                    break
                except Exception as exc:
                    logger.exception(f"[{group}] Error reading queue: {exc}")
                    await asyncio.sleep(1.0)
                    continue

                # item could be dicts like {"type": "message", "payload": ...}
                # dispatch to handlers concurrently
                for h in handlers:
                    try:
                        asyncio.create_task(h(item))
                    except Exception as exc:
                        logger.exception(f"[{group}] Error scheduling handler: {exc}")
        finally:
            logger.info(f"[{group}] Queue reader stopped")

    # -----------------------------------------------------------------
    # Stop/cleanup
    # -----------------------------------------------------------------
    async def stop(self):
        """
        Stop all workers and cancel queue reader tasks. This does NOT forcibly kill processes;
        it attempts graceful shutdown then terminates if necessary.
        """
        logger.info("Stopping all stream workers...")
        # cancel queue tasks
        for group, task in list(self._queue_tasks.items()):
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.debug(f"[{group}] queue reader did not stop in time, continuing")
            except Exception:
                pass
            self._queue_tasks.pop(group, None)

        # terminate processes
        for group, proc in list(self.workers.items()):
            if proc.is_alive():
                try:
                    proc.terminate()
                    proc.join(timeout=2.0)
                    if proc.is_alive():
                        proc.kill()
                except Exception:
                    logger.exception(f"Failed to terminate worker for group={group}")
            self.workers.pop(group, None)

        # close queues
        for group, q in list(self.queues.items()):
            try:
                q.close()
                q.cancel_join_thread()
            except Exception:
                pass
            self.queues.pop(group, None)

        logger.info("All workers stopped.")

    # -----------------------------------------------------------------
    # Optional helpers
    # -----------------------------------------------------------------
    def is_running(self, group: Optional[str] = None) -> bool:
        if group:
            p = self.workers.get(group)
            return bool(p and p.is_alive())
        return any(p.is_alive() for p in self.workers.values() if p)

    def get_worker_pid(self, group: str) -> Optional[int]:
        p = self.workers.get(group)
        return p.pid if p else None
