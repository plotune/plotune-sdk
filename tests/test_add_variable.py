from datetime import datetime
from time import time 
EXAMPLE_EXTENSION_CONFIG = {
    "name": "Plotune File Extension",
    "id": "plotune_file_ext",
    "version": "1.0.0",
    "description": "Provides file operations (read/write) and WebSocket streaming to Plotune Core.",
    "mode": "online",  # allowed values: online | offline | hybrit
    "author": "Plotune SDK Team",
    "cmd": [
        "python",
        "-m",
        "examples.example_extension"
    ],
    "enabled": True,
    "last_updated": datetime.utcnow().strftime("%Y-%m-%d"),
    "git_path": "https://github.com/plotune/plotune-sdk",
    "category": "Utility",
    "post_url": "http://localhost:8000/api/extension_click",
    "webpage": None,
    "file_formats": ["csv", "txt", "json"],
    "ask_form": False,
    "connection": {
        "ip": "127.0.0.1",          # where SDK server runs
        "port": 8010,               # SDK server port
        "target": "127.0.0.1",      # Plotune Core
        "target_port": 8000         # Core port
    },
    "configuration": {
    }
}



from plotune_sdk.runtime import PlotuneRuntime

runtime = PlotuneRuntime(
    ext_name="file-extension", 
    core_url="http://127.0.0.1:8000", 
    port=8010,
    config=EXAMPLE_EXTENSION_CONFIG)

import threading

def start_runtime():
    runtime.start()

if __name__ == "__main__":
    th = threading.Thread(target=start_runtime, daemon=True)
    th.start()

from time import sleep
sleep(2)  # wait for runtime to start   
import httpx
import random

url = "http://127.0.0.1:8000"

payload = {
    "name": f"Var_{random.randint(100,999)}",
    "desc": f"Desc_{random.randint(1000,9999)}",
    "extension_id": "plotune_file_ext"
}

r = httpx.post(f"{url}/add/variable", json=payload)
print("Status:", r.status_code)
print("Response:", r.text)