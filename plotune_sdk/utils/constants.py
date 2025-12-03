from diskcache import Cache
from platformdirs import user_cache_dir
from functools import lru_cache

API_URL = "https://api.plotune.net" 
STREAM_URL = "https://stream.plotune.net" 

@lru_cache(maxsize=None)
def get_cache(extension_id:str) -> Cache:
    APP_NAME = extension_id
    APP_AUTHOR = "BAKSI"
    USER_CACHE_DIR = user_cache_dir(APP_NAME, APP_AUTHOR)
    CACHE = Cache(USER_CACHE_DIR)
    return CACHE