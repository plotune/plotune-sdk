import os
from functools import lru_cache

from diskcache import Cache
from platformdirs import user_cache_dir

API_URL = "https://api.plotune.net"
STREAM_URL = "https://stream.plotune.net"

PYSTRAY_HEADLESS = os.getenv("PYSTRAY_HEADLESS", "0") == "1"


@lru_cache(maxsize=None)
def get_cache(extension_id: str) -> Cache:
    """
    Returns a disk-backed cache for the given extension ID.
    Uses platform-specific cache directory.
    """
    app_name = extension_id
    app_author = "BAKSI"
    cache_dir = user_cache_dir(app_name, app_author)
    cache = Cache(cache_dir)
    return cache
