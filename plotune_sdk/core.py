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
        self.core_url = core_url.rstrip("/")
        self.session = httpx.AsyncClient(timeout=5.0)
        self.config = config
        self.api_key = api_key
        self._stop_event = asyncio.Event()
        self._hb_task: Optional[asyncio.Task] = None
        logger.debug(f"CoreClient initialized with core_url: {self.core_url}")

    async def register(self):
        url = f"{self.core_url}/register"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = ExtensionConfig(**self.config).dict()
        logger.debug(f"Registering with payload: {payload}")
        r = await self.session.post(url, json=payload, headers=headers)
        r.raise_for_status()
        logger.info("Successfully registered with core server.")

    async def send_heartbeat(self, ext_id: str) -> bool:
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
                    break
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
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
        url = f"{self.core_url}/api/toast"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"title": title, "message": message, "duration": duration}
        logger.debug(f"Sending toast with payload: {payload}")
        r = await self.session.post(url, json=payload, headers=headers)
        r.raise_for_status()
        logger.info("Toast sent to core.")
        return r.json()
    
    async def info(self):
        url = f"{self.core_url}/api/info"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug("Fetching core info")
        r = await self.session.get(url, headers=headers)
        r.raise_for_status()
        info = r.json()
        logger.debug(f"Core info received: {info}")
        return info
    
    async def start_extension(self, ext_id: str):
        url = f"{self.core_url}/api/start/{ext_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug(f"Starting extension {ext_id}")
        r = await self.session.post(url, headers=headers)
        r.raise_for_status()
        logger.info(f"Extension {ext_id} started.")
        return r.json()
    
    async def get_configuration(self):
        url = f"{self.core_url}/api/configuration/current"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug("Fetching configuration from core")
        r = await self.session.get(url, headers=headers)
        r.raise_for_status()
        config = r.json()
        logger.debug(f"Configuration received: {config}")
        return config
    
    async def update_configuration_from_path(self, path: str):
        url = f"{self.core_url}/api/configuration/load/from_path"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"file_path": path}
        logger.debug(f"Updating configuration from path: {path}")
        r = await self.session.post(url, json=payload, headers=headers)
        r.raise_for_status()
        logger.info(f"Configuration updated from path: {path}")
        return r.json()
    