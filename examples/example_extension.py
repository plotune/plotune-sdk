from datetime import datetime
from time import time

EXAMPLE_EXTENSION_CONFIG = {
    "name": "Plotune File Extension",
    "id": "plotune_file_ext",
    "version": "1.0.0",
    "description": "Provides file operations (read/write) and WebSocket streaming to Plotune Core.",
    "mode": "online",  # allowed values: online | offline | hybrid
    "author": "Plotune SDK Team",
    "cmd": [
        "python",
        "-m",
        "examples.example_extension",
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
        "ip": "127.0.0.1",  # where SDK server runs
        "port": 8010,       # SDK server port
        "target": "127.0.0.1",  # Plotune Core
        "target_port": 8000,     # Core port
    },
    "configuration": {},
}


from plotune_sdk import PlotuneRuntime

runtime = PlotuneRuntime(
    ext_name="file-extension",
    core_url="http://127.0.0.1:8000",
    port=8010,
    config=EXAMPLE_EXTENSION_CONFIG,
)

client = runtime.core_client


# Register events on runtime.server
@runtime.server.on_event("/health", method="GET")
async def health(_):
    print("Health - running")
    return {"status": "running"}


@runtime.tray("Say Hello")
async def say_hello_tray():
    print("Hello from tray!")
    await client.toast(
        title="Tray Action",
        message="Hello from the tray menu!",
        duration=3000,
    )


@runtime.tray("Add Random Variable")
async def add_random_variable():
    import random

    var_name = f"RandomVar_{random.randint(1000, 9999)}"
    await client.add_variable(
        variable_name=var_name,
        variable_desc="A randomly added variable",
    )


@runtime.server.on_ws()
async def stream(signal_name, websocket, _):
    import random
    import asyncio

    try:
        while True:
            await websocket.send_json(
                {
                    "timestamp": time(),
                    "value": random.random(),
                    "desc": f"{signal_name}",
                    "status": True,
                }
            )
            await asyncio.sleep(1)
    except Exception:
        pass


if __name__ == "__main__":
    runtime.start()
