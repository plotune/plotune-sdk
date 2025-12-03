import asyncio
import json
import time
from aiohttp import ClientSession
from multiprocessing import Queue, Event as MpEvent


def build_producer_url(username: str, stream_name: str) -> str:
    """Build the WebSocket URL for a producer."""
    return f"wss://stream.plotune.net/ws/producer/{username}/{stream_name}"


def data_from_queue(q: Queue):
    """Retrieve data from the queue and format it for sending."""
    try:
        data = q.get_nowait()
        if not isinstance(data, dict):
            return None
        return {
            "key": data.get("key", "Unknown"),
            "time": data.get("time", int(time.time())),
            "value": data.get("value", 0),
        }
    except Exception:
        return None


async def producer_worker(
    username: str,
    stream_name: str,
    token: str,
    q: Queue,
    stop_event,
    interval: float = 0.2,
):
    """Asynchronous producer worker to send queue messages via WebSocket."""
    url = build_producer_url(username, stream_name)

    while not stop_event.is_set():
        try:
            async with ClientSession() as session:
                async with session.ws_connect(url, headers={"Authorization": f"Bearer {token}"}) as ws:

                    while not stop_event.is_set():
                        message = data_from_queue(q)
                        if message:
                            try:
                                await ws.send_str(json.dumps(message))
                            except Exception:
                                break

                        await asyncio.sleep(interval)

                        # Keep the connection alive
                        if not stop_event.is_set():
                            try:
                                await ws.ping()
                            except Exception:
                                break

        except Exception:
            if not stop_event.is_set():
                await asyncio.sleep(1)  # Wait before reconnecting
            else:
                break


def worker_entry(
    username: str,
    stream_name: str,
    token: str,
    q: Queue,
    stop_event = None,
    interval: float = 0.2,
):
    """Entry point for the producer worker process."""
    if stop_event is None:
        stop_event = MpEvent()

    asyncio.run(producer_worker(username, stream_name, token, q, stop_event, interval))
