# tests/test_stream.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from multiprocessing import Queue, Event as MpEvent

from plotune_sdk.src.streams import PlotuneStream
from plotune_sdk.src.runtime import PlotuneRuntime


class DummyRuntime:
    """Minimal dummy runtime with a running loop and stop event."""
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self._stop_event = MpEvent()


@pytest.fixture
def dummy_runtime():
    """Provide a dummy runtime."""
    return DummyRuntime()


@pytest.fixture
def plotune_stream(dummy_runtime):
    """Provide a PlotuneStream instance with dummy runtime."""
    stream = PlotuneStream(runtime=dummy_runtime, stream_name="dummy_stream")
    stream.username = "testuser"
    return stream


@pytest.mark.asyncio
async def test_stream_consume_handler(plotune_stream):
    """Test registering a consume handler and invoking it."""

    called = asyncio.Event()

    @plotune_stream.on_consume("group1")
    async def dummy_handler(msg):
        assert isinstance(msg, dict)
        called.set()

    # Simulate a queue and manually trigger handler
    test_msg = {"type": "message", "payload": {"data": 123}}
    await plotune_stream._queue_reader("group1", Queue())  # Task starts, but queue is empty

    # Directly call handler to simulate consumption
    for h in plotune_stream.handlers["group1"]:
        await h(test_msg)

    # Wait to ensure handler ran
    await asyncio.wait_for(called.wait(), timeout=1)
    assert called.is_set()


@pytest.mark.asyncio
async def test_aproduce(plotune_stream):
    """Test producing a message into the producer queue."""
    # Mock _start_worker_for_producer to prevent real process start
    plotune_stream._start_worker_for_producer = AsyncMock()
    plotune_stream.producer_enabled = False

    await plotune_stream.aproduce("TestKey", 123456.0, 42.0)

    # _start_worker_for_producer should have been called to enable producer
    plotune_stream._start_worker_for_producer.assert_awaited_once()


@pytest.mark.asyncio
async def test_enable_producer_sets_queue(plotune_stream):
    """Test that enabling producer sets the queue and worker."""
    with patch(
        "plotune_sdk.src.streams.Process"
    ) as mock_process, patch("multiprocessing.Queue") as mock_queue:
        mock_proc_instance = mock_process.return_value
        mock_proc_instance.is_alive.return_value = True

        await plotune_stream._start_worker_for_producer("dummy_token")

        assert plotune_stream.producer_enabled is True
        assert plotune_stream.producer_queue == mock_queue.return_value
        assert plotune_stream.workers["@producer@"] == mock_proc_instance
