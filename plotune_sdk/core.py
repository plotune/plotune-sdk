# plotune_sdk/core.py
import httpx
import asyncio
import logging
from time import time
from typing import Optional
from plotune_sdk.models.config_models import ExtensionConfig

from plotune_sdk.utils import get_logger

logger = get_logger("plotune_core")

class CoreClient:
    def __init__(self, core_url: str, config: dict, api_key: Optional[str] = None):
        """
        Initialize the CoreClient instance for communication with the Plotune Core.

        Args:
            core_url (str): Base URL of the Plotune Core API.
            config (dict): Extension configuration dictionary.
            api_key (Optional[str]): Optional bearer token for authentication.
        """
        self.core_url = core_url.rstrip("/")
        self.session = httpx.AsyncClient(timeout=5.0)
        self.config = config
        self.api_key = api_key
        self._stop_event = asyncio.Event()
        self._hb_task: Optional[asyncio.Task] = None
        logger.debug(f"CoreClient initialized with core_url: {self.core_url}")

        self.register_fail_handler:callable = None
        self.heartbeat_fail_handler:callable = None

    async def register(self):
        """
        Register this extension instance with the Plotune Core.

        Sends the current configuration to the Core for registration.
        If registration fails and a fail handler is set, it will be called.

        Raises:
            httpx.HTTPError: If the registration request fails.
        """
        try:
            url = f"{self.core_url}/register"
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            payload = ExtensionConfig(**self.config).dict()
            logger.debug(f"Registering with payload: {payload}")
            r = await self.session.post(url, json=payload, headers=headers)
            r.raise_for_status()
            logger.info("Successfully registered with core server.")
        except Exception as e:
            logger.error(f"Failed to register with core server: {e}")
            if self.register_fail_handler:
                self.register_fail_handler()


    async def send_heartbeat(self, ext_id: str) -> bool:
        """
        Send a heartbeat signal to the Plotune Core.

        Args:
            ext_id (str): Extension ID as registered with the Core.

        Returns:
            bool: True if the heartbeat was successful, False otherwise.
        """
        url = f"{self.core_url}/heartbeat"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"id": ext_id, "timestamp": time()}
        logger.debug(f"Sending heartbeat with payload: {payload}")
        try:
            response = await self.session.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.debug("Heartbeat ok")
            return True
        except httpx.HTTPError as e:
            logger.warning(f"Heartbeat failed: {e}")
            return False

    async def heartbeat_loop(self, ext_id: str, interval: int = 15, max_failures: int = 3):
        """
        Continuously send periodic heartbeat messages to the Core.

        Args:
            ext_id (str): Extension ID.
            interval (int): Base heartbeat interval in seconds.
            max_failures (int): Maximum allowed consecutive failures before stopping.

        Notes:
            The wait interval is dynamically reduced after failures to attempt recovery faster.
        """
        fail_count = 0
        while not self._stop_event.is_set():
            success = await self.send_heartbeat(ext_id)
            if success:
                fail_count = 0
            else:
                fail_count += 1
                logger.warning(f"Failed heartbeats: {fail_count}/{max_failures}")
                if fail_count >= max_failures:
                    logger.critical("Max heartbeat failures reached, stopping heartbeat loop")
                    if self.heartbeat_fail_handler:
                        self.heartbeat_fail_handler()
                    break
            try:
                wait_time = max(int(interval/(fail_count*2 + 1)), 1)
                await asyncio.wait_for(self._stop_event.wait(), timeout = wait_time)
            except asyncio.TimeoutError:
                continue  # timeout expired -> send next heartbeat

    async def start(self):
        """Start core client: register + spawn heartbeat task."""
        await self.register()
        ext_id = self.config.get("id", "unknown")
        logger.info("Starting heartbeat loop...")
        self._stop_event.clear()
        self._hb_task = asyncio.create_task(self.heartbeat_loop(ext_id))

    async def stop(self):
        """Gracefully stop heartbeat and close session."""
        logger.info("Stopping CoreClient...")
        self._stop_event.set()
        if self._hb_task:
            try:
                await asyncio.wait_for(self._hb_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._hb_task.cancel()
        await self.session.aclose()
        logger.debug("HTTP session closed.")

    # Plotune Core API wrappers can be added here

    async def toast(self, title: str="Notification", message: str="Extension Message", duration:int=2500):
        """
        Send a toast (notification) message to the Plotune UI.

        Args:
            title (str): Title of the notification.
            message (str): Message body text.
            duration (int): Duration in milliseconds for the toast to remain visible.

        Returns:
            dict: JSON response from the Core.
        """
        url = f"{self.core_url}/api/toast"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"title": title, "message": message, "duration": duration}
        logger.debug(f"Sending toast with payload: {payload}")
        r = await self.session.post(url, json=payload, headers=headers)
        r.raise_for_status()
        logger.info("Toast sent to core.")
        return r.json()
    
    async def info(self):
        """
        Retrieve system information from the Plotune Core.

        Returns:
            dict: Information about the running Core instance.
        """
        url = f"{self.core_url}/api/info"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug("Fetching core info")
        r = await self.session.get(url, headers=headers)
        r.raise_for_status()
        info = r.json()
        logger.debug(f"Core info received: {info}")
        return info
    
    async def start_extension(self, ext_id: str):
        """
        Request the Core to start a specific extension.

        Args:
            ext_id (str): ID of the extension to start.

        Returns:
            dict: JSON response from the Core.
        """
        url = f"{self.core_url}/api/start/{ext_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug(f"Starting extension {ext_id}")
        r = await self.session.post(url, headers=headers)
        r.raise_for_status()
        logger.info(f"Extension {ext_id} started.")
        return r.json()
    
    async def get_configuration(self):
        """
        Fetch the currently active configuration from the Core.

        Returns:
            dict: The current configuration data.
        """
        url = f"{self.core_url}/api/configuration/current"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug("Fetching configuration from core")
        r = await self.session.get(url, headers=headers)
        r.raise_for_status()
        config = r.json()
        logger.debug(f"Configuration received: {config}")
        return config
    
    async def update_configuration_from_path(self, path: str):
        """
        Instruct the Core to reload configuration from a specific file path.

        Args:
            path (str): Filesystem path to the configuration file.

        Returns:
            dict: JSON response indicating success or failure.
        """
        url = f"{self.core_url}/api/configuration/load/from_path"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"file_path": path}
        logger.debug(f"Updating configuration from path: {path}")
        r = await self.session.post(url, json=payload, headers=headers)
        r.raise_for_status()
        logger.info(f"Configuration updated from path: {path}")
        return r.json()
    