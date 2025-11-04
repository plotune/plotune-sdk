# plotune_sdk/runtime.py
import asyncio
import threading
import signal
import sys
from typing import Optional
from pystray import Icon, Menu, MenuItem
from importlib.resources import files, as_file
from PIL import Image, ImageDraw

from typing import Callable, List, Tuple

from plotune_sdk.server import PlotuneServer
from plotune_sdk.core import CoreClient
from plotune_sdk.utils import get_logger

logger = get_logger("plotune_runtime", console=True)

class PlotuneRuntime:
    def __init__(
        self,
        ext_name: str = "default-extension",
        core_url: str = "http://127.0.0.1:8000",
        host: str = "127.0.0.1",
        port: int = 8000,
        config: Optional[dict] = None,
        tray_icon: bool = True,
    ):
        self.ext_name = ext_name
        self.core_url = core_url
        self.host = host
        self.port = port
        self.tray_icon_enabled = tray_icon
        self.config = config or {"id": ext_name}
        self.server = PlotuneServer(host=self.host, port=self.port)
        self.core_client = CoreClient(core_url=self.core_url, config=self.config)

        self.icon = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._server_task: Optional[asyncio.Task] = None
        self._core_task: Optional[asyncio.Task] = None
        
        self._tray_actions = []

    def tray(self, label: str):
        """Decorator to register tray menu actions dynamically."""
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
            # ensure cleanup
            pending = asyncio.all_tasks(loop=self.loop)
            for t in pending:
                t.cancel()
            try:
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            except Exception:
                pass
            self.loop.close()
            logger.debug("Event loop closed.")

    async def _main(self):
        # start core client (register + heartbeat task)
        await self.core_client.start()
        # start server serve coroutine as task
        self._server_task = asyncio.create_task(self.server.serve())
        # keep running until server finishes or core signals stop
        await asyncio.wait([self._server_task], return_when=asyncio.FIRST_COMPLETED)
        # when server stops, ensure core client stops
        await self.core_client.stop()

    def start(self):
        logger.info(f"Starting PlotuneRuntime for {self.ext_name} on {self.host}:{self.port}")
        self.thread.start()
        if self.tray_icon_enabled:
            self._start_tray_icon()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        def handler(signum, _frame):
            logger.warning(f"Signal {signum} received — stopping runtime...")
            self.stop()
        for s in (signal.SIGINT, signal.SIGTERM):
            signal.signal(s, handler)

    def stop(self):
        """Graceful stop: schedule shutdown in the runtime loop."""
        logger.info("Stopping PlotuneRuntime (graceful)...")

        # stop core client safely
        try:
            if self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.core_client.stop(), self.loop)
            else:
                asyncio.run(self.core_client.stop())
        except Exception as e:
            logger.debug("core_client.stop scheduling failed: %s", e)

        # stop uvicorn server safely
        try:
            uvicorn_srv = getattr(self.server, "_uvicorn_server", None)
            if uvicorn_srv:
                uvicorn_srv.should_exit = True
        except Exception as e:
            logger.debug("Failed to set server.should_exit: %s", e)

        # stop tray
        self._stop_tray_icon()


    def kill(self):
        """Immediate kill."""
        logger.warning("Killing PlotuneRuntime (force) ...")
        # try graceful first
        self.stop()
        # then force stop the loop
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
        # stop tray
        self._stop_tray_icon()
        # exit process as last resort
        sys.exit(0)

    # ----------------------------
    # tray icon helpers
    # ----------------------------
    def _load_icon_image(self):
        # attempt to load package asset, fallback to generated
        try:
            icon_res = files("plotune_sdk.assets").joinpath("icon.png")
            with as_file(icon_res) as p:
                return Image.open(p)
        except Exception:
            # fallback placeholder
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
                    f()
                except Exception as e:
                    logger.exception("Tray action failed: %s", e)
            return callback
        # dynamic actions
        dynamic_items = [
            MenuItem(label, make_callback(func))
            for label, func in self._tray_actions
        ]

        # merge
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
