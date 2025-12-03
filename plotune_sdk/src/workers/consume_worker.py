# src/workers/consume_worker.py
import asyncio
import json
from typing import Any
from aiohttp import ClientSession, WSMsgType
from multiprocessing import Queue

def build_url(username: str, stream_name: str, group: str) -> str:
    return f"wss://stream.plotune.net/ws/consumer/{username}/{stream_name}/{group}"


async def _put_to_queue_async(q: Queue, item: Any):
    """
    Run blocking q.put in a thread so the worker's async loop doesn't block.
    Works with multiprocessing.Queue.
    """
    loop = asyncio.get_running_loop()
    # run blocking put in a thread pool worker
    await loop.run_in_executor(None, q.put, item)


async def consume(username: str, stream_name: str, group: str, token: str, q: Queue):
    url = build_url(username, stream_name, group)

    try:
        async with ClientSession() as session:
            async with session.ws_connect(
                url,
                headers={"Authorization": f"Bearer {token}"}
            ) as ws:
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                        except Exception:
                            data = msg.data
                        # push to main process without blocking event loop
                        await _put_to_queue_async(q, {"type": "message", "payload": data})
                    elif msg.type == WSMsgType.ERROR:
                        await _put_to_queue_async(q, {"type": "error", "payload": str(ws.exception())})
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # forward unexpected worker errors to main (best-effort)
        try:
            await _put_to_queue_async(q, {"type": "error", "payload": str(exc)})
        except Exception:
            pass


def worker_entry(username: str, stream_name: str, group: str, token: str, q: Queue):
    """
    Multiprocessing target. This function is executed inside the child process.
    The `q` argument is the multiprocessing.Queue created in the parent process.
    """
    asyncio.run(consume(username, stream_name, group, token, q))
