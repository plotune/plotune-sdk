# src/streams.py
import asyncio
import secrets
from multiprocessing import Process, Queue
from typing import Callable, Any, Dict, List, Optional
from plotune_sdk.src.workers import consumer_worker_entry, producer_worker_entry
from plotune_sdk.utils import get_logger
from queue import Empty
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

        self.producer_enabled = False
        self.producer_interval = 0.2 
        self.producer_queue:Queue = None
        self.stream_token:str = None

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
        self.stream_token = token
        if not self.username:
            raise RuntimeError("Username must be assigned before calling start()")
        
        for group in list(self.handlers.keys()):
            if group in self.workers:
                logger.debug(f"Worker for group={group} already running, skipping")
                continue
            await self._start_worker_for_group(group, token)

    async def enable_producer(self):
        await self._start_worker_for_producer(self.stream_token)

    async def aproduce(self, _key:str, timestamp:float, value:float):
        if not self.producer_enabled:
            await self.enable_producer()
        
        data = {"key":_key, "time":timestamp, "value":value}
        try:
            self.producer_queue.put_nowait(data)
        except Exception as exc:
            logger.warning(f"An error occured on {self.stream_name} producer {exc}")

    def produce(self, _key: str, timestamp: float, value: float):
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self.aproduce(_key, timestamp, value),
                self.runtime.loop
            )
        except RuntimeError:
            logger.warning(f"{self.stream_name}: produce() ignored because event loop is shutting down")


    async def _start_worker_for_producer(self, token:str):
        q = Queue()
        p = Process(
            target=producer_worker_entry,
            args=(self.username, self.stream_name, token, q, self.runtime._stop_event, self.producer_interval)
        )
        p.start()
        self.producer_enabled = True
        self.producer_queue = q
        self.workers["@producer@"] = p

        logger.info(f"[producer] Worker started PID={p.pid}")

    async def _start_worker_for_group(self, group: str, token: str):
        """
        Create a multiprocessing.Queue for this group, start worker process,
        and start an async reader task that dispatches messages to handlers.
        """
        q = Queue()
        p = Process(
            target=consumer_worker_entry,
            args=(self.username, self.stream_name, group, token, q, self.runtime._stop_event),
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
        handlers = self.handlers.get(group, [])
        logger.info(f"[{group}] Queue reader started (async)")
        
        while True:
            try:
                # NON-BLOCKING poll + timeout
                item = await asyncio.to_thread(q.get_nowait)
            except asyncio.CancelledError:
                logger.info(f"[{group}] Queue reader cancelled")
                break
            except (Empty, ValueError, OSError, EOFError):
                
                await asyncio.sleep(0.1)
                continue
            except Exception as exc:
                logger.exception(f"[{group}] Unexpected queue error: {exc}")
                await asyncio.sleep(0.5)
                continue

            # Gerçek mesaj geldi
            for h in handlers:
                try:
                    asyncio.create_task(h(item))
                except Exception as exc:
                    logger.exception(f"[{group}] Handler error: {exc}")

                except asyncio.CancelledError:
                    logger.info(f"[{group}] Queue reader cancelled gracefully")
                    break

        logger.info(f"[{group}] Queue reader stopped")

    # -----------------------------------------------------------------
    # Stop/cleanup
    # -----------------------------------------------------------------
    async def stop(self):
        logger.info("Stopping stream workers...")

        # 1. Tüm queue reader task'lerini iptal et
        for task in self._queue_tasks.values():
            task.cancel()

        # 2. Queue'ları kapat (Windows'ta çok önemli!)
        for q in self.queues.values():
            try:
                q.close()
                q.join_thread()  # bu çok kritik!
            except:
                pass

        # 3. Worker process'leri terminate et
        for proc in self.workers.values():
            if proc.is_alive():
                proc.terminate()

        # 4. Kısa bekle, sonra kill
        await asyncio.sleep(0.5)
        for proc in self.workers.values():
            if proc.is_alive():
                logger.warning(f"Killing stubborn worker PID {proc.pid}")
                proc.kill()
            proc.join(timeout=1)

        # 5. Task'lerin bitmesini bekle (artık bloklamaz!)
        if self._queue_tasks:
            await asyncio.gather(*self._queue_tasks.values(), return_exceptions=True)

        self.workers.clear()
        self.queues.clear()
        self._queue_tasks.clear()

        logger.info("All stream workers fully stopped.")

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
