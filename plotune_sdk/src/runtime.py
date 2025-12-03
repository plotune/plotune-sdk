import asyncio
import threading
import multiprocessing
import signal
import sys
from typing import Optional, Dict

from pystray import Icon, Menu, MenuItem
from importlib.resources import files, as_file
from PIL import Image, ImageDraw

from plotune_sdk.src import PlotuneServer, CoreClient
from plotune_sdk.src.streams import PlotuneStream
from plotune_sdk.utils import get_logger, get_cache, API_URL

logger = get_logger("extension")


class PlotuneRuntime:
    def __init__(
        self,
        ext_name: str = "default-extension",
        core_url: str = "http://127.0.0.1:8000",
        host: str = "127.0.0.1",
        port: int = None,
        config: Optional[dict] = None,
        tray_icon: bool = True,
    ):
        self.ext_name = ext_name
        self.core_url = core_url
        self.host = host
        self.port = port
        self.tray_icon_enabled = tray_icon
        self.config = config or {"id": ext_name}
        self.cache = get_cache(ext_name)
        self._stop_event = multiprocessing.Event()
        self.end_signal = asyncio.Event()
        self.server = PlotuneServer(self, host=self.host, port=self.port)

        @self.server.on_event("/stop", method="GET")
        async def handle_stop_request(_):
            logger.info("Stop request received via /stop endpoint.")
            self.stop()
            return {"status": "stopping"}

        self.core_client = CoreClient(self, core_url=self.core_url, config=self.config)
        self.core_client.register_fail_handler = self.stop
        self.core_client.heartbeat_fail_handler = self.stop

        self.icon = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._server_task: Optional[asyncio.Task] = None

        self._tray_actions = []
        self._streams: Dict[str, PlotuneStream] = {}
        self._stream_token_cache: Optional[str] = None
        self._stream_username_cache: Optional[str] = None
        self._stream_loops = []

    def tray(self, label: str):
        def decorator(func):
            self._tray_actions.append((label, func))
            return func
        return decorator

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            logger.exception("Runtime main loop crashed: %s", e)
        finally:
            pending = asyncio.all_tasks(loop=self.loop)
            for t in pending:
                t.cancel()
            try:
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            except Exception:
                pass
            
            try:
                self.loop.close()
                self.loop.stop()
            except:
                self.kill()

    async def _main(self):
        await self.core_client.start()

        # Start all streams created before start()
        for stream in self._streams.values():
            await self._ensure_stream_running(stream)

        self._server_task = asyncio.create_task(self.server.serve())

        # Wait until server finishes OR is cancelled. Handle CancelledError cleanly.
        try:
            await asyncio.wait([self._server_task], return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            logger.info("Runtime main: server task cancelled (shutdown requested).")
        finally:
            # Final guaranteed cleanup
            try:
                await self._stop_all_streams()
            except Exception as e:
                logger.exception("Error while stopping streams: %s", e)
            try:
                await self.core_client.stop()
            except Exception as e:
                logger.exception("Error while stopping core client: %s", e)


    async def _stop_all_streams(self):
        self._stop_event.set()
        if not self._streams:
            return
        tasks = [stream.stop() for stream in self._streams.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All managed streams stopped.")
        self.end_signal.set()

    def start(self):
        logger.info(f"Starting PlotuneRuntime for {self.ext_name}")
        self.thread.start()
        if self.tray_icon_enabled:
            self._start_tray_icon()
        self._setup_signal_handlers()

        for stream in self._streams.values():
            asyncio.run_coroutine_threadsafe(self._ensure_stream_running(stream), self.loop)
        
        self.thread.join()

    def _setup_signal_handlers(self):
        def handler(signum, _frame):
            logger.warning(f"Signal {signum} received — stopping runtime...")
            self.stop()
        
        for s in (signal.SIGINT, signal.SIGTERM):
            signal.signal(s, handler)

    def stop(self):
        logger.info("Stopping PlotuneRuntime (graceful)...")
        # Stop server
        try:
            uvicorn_srv = getattr(self.server, "_uvicorn_server", None)
            if uvicorn_srv:
                uvicorn_srv.should_exit = True
                uvicorn_srv.force_exit = True
        except Exception:
            pass

        self._stop_tray_icon()

    def kill(self):
        logger.warning("Killing PlotuneRuntime (force) ...")
        self.stop()
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
        self._stop_tray_icon()
        sys.exit(0)

    def create_stream(self, stream_name: str) -> PlotuneStream:
        if stream_name in self._streams:
            return self._streams[stream_name]

        stream = PlotuneStream(self, stream_name)
        self._streams[stream_name] = stream
        logger.info(f"Stream '{stream_name}' created and managed by runtime")
        return stream

    async def _get_stream_auth(self) -> tuple[str, str]:
        if self._stream_token_cache and self._stream_username_cache:
            return self._stream_username_cache, self._stream_token_cache

        username, license_token = await self.core_client.authenticator.get_license_token()
        logger.debug(f"{username}, {license_token}")
        for _ in range(3):
            resp = await self.core_client.session.get(
                f"{API_URL}/auth/stream",
                headers={"Authorization": f"Bearer {license_token}"}
            )
            resp.raise_for_status()
            token = resp.json()["token"]
            logger.debug(token)
            if token:
                break

        self._stream_username_cache = username
        self._stream_token_cache = token
        return username, token

    async def _ensure_stream_running(self, stream: PlotuneStream):
        try:
            username, token = await self._get_stream_auth()
            stream.username = username
            await stream.start(token)
            logger.info(f"Auto-started stream '{stream.stream_name}'")
        except Exception as e:
            logger.error(f"Failed to auto-start stream '{stream.stream_name}': {e}")

    # Tray icon helpers
    def _load_icon_image(self):
        try:
            icon_res = files("plotune_sdk.assets").joinpath("icon.png")
            with as_file(icon_res) as p:
                return Image.open(p)
        except Exception:
            img = Image.new("RGBA", (64, 64), (40, 120, 180, 255))
            draw = ImageDraw.Draw(img)
            draw.text((18, 20), "P", fill=(255, 255, 255))
            return img

    def _start_tray_icon(self):
        image = self._load_icon_image()
        base_items = [
            MenuItem("Stop", lambda _: self.stop()),
            MenuItem("Force Stop", lambda _: self.kill()),
        ]

        def make_callback(f):
            def callback(icon, item):
                try:
                    if asyncio.iscoroutinefunction(f):
                        coro = f()
                        asyncio.run_coroutine_threadsafe(coro, self.loop)
                    else:
                        f()
                except Exception as e:
                    logger.exception("Tray action failed: %s", e)
            return callback

        dynamic_items = [MenuItem(label, make_callback(func)) for label, func in self._tray_actions]
        menu = Menu(*(dynamic_items + [Menu.SEPARATOR] + base_items))
        self.icon = Icon(self.ext_name, image, "Plotune Runtime", menu)
        threading.Thread(target=self.icon.run, daemon=False).start()

    def _stop_tray_icon(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None