from datetime import datetime
from time import time
import random
import asyncio

from plotune_sdk import PlotuneRuntime, FormLayout
from plotune_sdk.utils import AVAILABLE_PORT

EXAMPLE_EXTENSION_CONFIG = {
    "name": "Plotune File Extension",
    "id": "plotune_file_ext",
    "version": "1.0.0",
    "description": "Provides file operations (read/write) and WebSocket streaming to Plotune Core.",
    "mode": "online",
    "author": "Plotune SDK Team",
    "cmd": [
        "python",
        "-m",
        "examples.example_form_extension",
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
        "ip": "127.0.0.1",
        "port": AVAILABLE_PORT,
        "target": "127.0.0.1",
        "target_port": 8000,
    },
    "configuration": {},
}

runtime = PlotuneRuntime(
    ext_name="file-extension",
    core_url="http://127.0.0.1:8000",
    config=EXAMPLE_EXTENSION_CONFIG,
)


@runtime.server.on_event("/fetch-meta")
async def my_variables(data: dict):
    return {
        "headers": [
            "Signal_Name_A",
            "Signal_Name_B",
            "Signal_Name_C",
            "Signal_Name_D",
        ]
    }


@runtime.server.on_event("/form")
async def generate_the_form(data: dict):
    form = FormLayout()

    form.add_tab("Settings").add_text("username", "Username", default="", required=True).add_text(
        "test_field", "Test", default="", required=False
    ).add_number("seed", "Seed", default=100, min_val=10, max_val=2000, required=False).add_combobox(
        "color",
        "Color Pick",
        options=["Red", "Green", "Blue"],
        default="",
        required=False,
    )

    form.add_tab("Custom").add_file("file", "Optional file", required=False)

    form.add_group("Custom Group").add_checkbox("enable", "Enable", default=True, required=False).add_button(
        "forward",
        "Visit",
        action={
            "method": "POST",
            "url": "http://example.com/api/upload",
            "payload_fields": ["upload_file"],
        },
    )

    return form.to_schema()


@runtime.server.on_event("/form", method="POST")
async def get_answer(data: dict):
    print("Form submitted with data:", data)
    random.seed(data.get("seed"))
    return {"status": "success", "message": "Form saved!"}


@runtime.tray("Add Random Variable")
async def add_random_variable():
    var_name = f"RandomVar_{random.randint(1000, 9999)}"
    await runtime.core_client.add_variable(
        variable_name=var_name,
        variable_desc="A randomly added variable",
    )


@runtime.tray("Get Token")
async def get_token():
    username, token = await runtime.core_client.authenticator.get_license_token()
    print("Token:", token)


@runtime.server.on_ws()
async def stream(signal_name, websocket, _):
    print(f"{signal_name} requested")
    try:
        while True:
            await websocket.send_json(
                {
                    "timestamp": time(),
                    "value": random.random(),
                }
            )
            await asyncio.sleep(0.03)
    except Exception:
        pass


if __name__ == "__main__":
    runtime.start()
