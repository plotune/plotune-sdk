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

logger = get_logger("extension")

class PlotuneRuntime:
    """
    The main runtime manager for a Plotune extension.

    This class orchestrates the interaction between:
      - The local FastAPI server (PlotuneServer)
      - The Plotune Core client (CoreClient)
      - An optional system tray icon for user control

    It handles asynchronous execution, graceful shutdown, and
    background heartbeat communication with the Core.
    """
    def __init__(
        self,
        ext_name: str = "default-extension",
        core_url: str = "http://127.0.0.1:8000",
        host: str = "127.0.0.1",
        port: int = None,
        config: Optional[dict] = None,
        tray_icon: bool = True,
    ):
        """
        Initialize a PlotuneRuntime instance.

        Args:
            ext_name (str): Name of the extension instance.
            core_url (str): Base URL of the Plotune Core.
            host (str): Host address for the embedded server.
            port (Optional[int]): Optional custom port for the server.
            config (Optional[dict]): Configuration dictionary to pass to CoreClient.
            tray_icon (bool): Whether to display a system tray icon for control.
        """
        self.ext_name = ext_name
        self.core_url = core_url
        self.host = host
        self.port = port
        self.tray_icon_enabled = tray_icon
        self.config = config or {"id": ext_name}
        self.server = PlotuneServer(host=self.host, port=self.port)

        @self.server.on_event("/stop", method="GET")
        async def handle_stop_request(_):
            logger.info("Stop request received via /stop endpoint.")
            self.stop()
            return {"status": "stopping"}

        self.core_client = CoreClient(core_url=self.core_url, config=self.config)
        self.core_client.register_fail_handler = self.stop
        self.core_client.heartbeat_fail_handler = self.stop

        self.icon = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._server_task: Optional[asyncio.Task] = None
        self._core_task: Optional[asyncio.Task] = None
        
        self._tray_actions = []

    def tray(self, label: str):
        """
        Decorator to register custom actions in the system tray menu.

        Example:
            ```python
            @runtime.tray("Custom Action")
            def custom_action():
                print("Custom action triggered from tray!")
            ```

        Args:
            label (str): Display label for the tray menu item.

        Returns:
            Callable: Decorator for the tray function.
        """
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
        """
        Start the PlotuneRuntime environment.

        Launches the asynchronous event loop in a separate thread,
        starts the PlotuneServer, connects to the Core, and optionally
        creates a system tray icon for manual control.
        """
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
        """
        Gracefully stop the runtime and all active components.

        Stops the CoreClient heartbeat, signals the server to shut down,
        and removes the tray icon if present.
        """
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
        """
        Immediately terminate the runtime process.

        This method forcefully stops the event loop, tray icon, and exits the process.
        Should only be used when graceful shutdown fails or in critical conditions.
        """
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

        import inspect
        def make_callback(f):
            def callback(icon, item):
                try:
                    if inspect.iscoroutinefunction(f):
                        coro = f()  # coroutine objesi oluştur
                        asyncio.run_coroutine_threadsafe(coro, self.loop)
                    else:
                        f()
                except Exception as e:
                    logger.exception("Tray action failed: %s", e)
            return callback


        dynamic_items = [
            MenuItem(label, make_callback(func))
            for label, func in self._tray_actions
        ]

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
