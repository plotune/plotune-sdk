from datetime import datetime
from time import time 
from plotune_sdk.utils import AVAILABLE_PORT

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
    "webpage": "www.plotune.net",
    "file_formats": ["csv", "txt", "json"],
    "ask_form": True,
    "connection": {
        "ip": "127.0.0.1",          # where SDK server runs
        "port": AVAILABLE_PORT,     # SDK server port
        "target": "127.0.0.1",      # Plotune Core
        "target_port": 8000         # Core port
    },
    "configuration": {
    }
}

from plotune_sdk.runtime import PlotuneRuntime
from plotune_sdk.forms import FormLayout


runtime = PlotuneRuntime(
    ext_name="file-extension", 
    core_url="http://127.0.0.1:8000",
    config=EXAMPLE_EXTENSION_CONFIG)

@runtime.server.on_event("/fetch-meta")
async def my_variables(data:dict):
    return {"headers": [
        "Signal_Name_A",
        "Signal_Name_B",
        "Signal_Name_C",
        "Signal_Name_D"
    ]}

@runtime.server.on_event("/form")
async def generate_the_form(data:dict):
    form = FormLayout()

    # Tab 1: Settings
    form.add_tab("Settings") \
        .add_text("username", "Username", default="", required=True) \
        .add_text("test_field", "Test", default="", required=False) \
        .add_number("seed", "Seed", default=100, min_val=10, max_val=2000, required=False) \
        .add_combobox("color", "Color Pick", options=["Red", "Green", "Blue"], default="", required=False)

    # Tab 2: Custom (note: added 'test_field' twice as in your example, but keys must be unique—adjust if needed)
    form.add_tab("Custom") \
        .add_file("file", "Optional file", required=False)

    # Group: Custom Group
    form.add_group("Custom Group") \
        .add_checkbox("enable", "Enable", default=True, required=False) \
        .add_button("forward", "Visit", action={
            "method": "POST",
            "url": "http://example.com/api/upload",
            "payload_fields": ["upload_file"]
        })

    # Generate and print the schema (this matches your schema_json exactly)
    return form.to_schema()

import random, asyncio
@runtime.server.on_event("/form", method="POST")
async def get_answer(data: dict):
    print("Form submitted with data:", data)
    random.seed(data.get("seed"))
    return {"status": "success", "message": "Form saved!"}

@runtime.server.on_ws()
async def stream(signal_name, websocket, _):
    try:
        while True:
            await websocket.send_json({
                "timestamp":time(),
                "value" : random.random()
            })
            await asyncio.sleep(0.03)
    except Exception:
        pass

if __name__ == "__main__":
    runtime.start()
