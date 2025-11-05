# Plotune SDK

**Plotune SDK** is a lightweight Python toolkit for developing modular **extensions** that seamlessly integrate with the **Plotune Core** system.  
It provides a unified environment to build, serve, and manage extension logic — including REST APIs, WebSocket handlers, and runtime lifecycle management — all with minimal boilerplate.

---

## Features

- **FastAPI-based server** — automatically starts a local HTTP/WebSocket server for your extension  
- **Event-driven design** — register logic with decorators like `@server.on_event()` or `@server.on_ws()`  
- **Core communication** — built-in client for registration and heartbeat with Plotune Core  
- **Runtime management** — tray-based control with start/stop/kill functionality  
- **Cross-platform logging** — lightweight rotating file logger without external dependencies  
- **Packaged assets** — safely bundle icons or other resources in your extension package  

---

## Architecture Overview

```
┌────────────────────────────────┐
│        Plotune Core            │
│  - Manages extensions          │
│  - Receives registration       │
│  - Sends control/heartbeat     │
└─────────────┬──────────────────┘
              │
              │ HTTP / WS
              │
┌─────────────▼──────────────────┐
│        Plotune SDK             │
│  ┌──────────────────────────┐  │
│  │  PlotuneServer (FastAPI) │  │
│  │  - /health, /read-file   │  │
│  │  - @on_event, @on_ws     │  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │  CoreClient (httpx)      │  │
│  │  - register, heartbeat   │  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │  PlotuneRuntime          │  │
│  │  - lifecycle control     │  │
│  │  - tray integration      │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

---

## Development Setup

```bash

# create virtual environment
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# install dependencies
pip install plotune-sdk

```

---

## User-Input Forms (Dynamic UI)

Extensions can ask the **Plotune Core** to show a modal form to the user.  
The Core will:

1. **GET** `/form` → receive the *form schema* (JSON).  
2. Render the UI with `DynamicForm` (PyQt5).  
3. **POST** the collected data back to `/form`.

You only have to implement **two optional handlers**:

| Endpoint | Method | Purpose | Required? |
|----------|--------|---------|-----------|
| `/form`  | `GET`  | Return the **schema** (`dict`) that describes tabs, groups and fields. | **Optional** – if missing an empty form is shown. |
| `/form`  | `POST` | Receive the **filled-in values** (`dict`) and process them. | **Required** – Core expects a response (default `{"status":"success"}`).

---

### 1. Register the handlers (extension side)

```python
# __main__.py (or any module that creates the server)
from plotune_sdk.server import PlotuneServer
from plotune_sdk.forms import FormLayout   # optional helper

server = PlotuneServer(host="127.0.0.1", port=8100)

# ------------------------------------------------------------------
# GET /form  →  return the schema
# ------------------------------------------------------------------
@server.on_event("/form", "GET")
def get_form_schema(_):
    # Build the schema with the fluent helper (recommended)
    form = FormLayout()

    form.add_tab("General") \
        .add_text("username", "Username", default="", required=False) \
        .add_number("seed", "Random seed", default=42, min_val=0, max_val=9999, required=True)

    form.add_tab("Appearance") \
        .add_combobox("theme", "Theme", options=["Light", "Dark", "Auto"], default="Auto") \
        .add_checkbox("high_contrast", "High-contrast mode", default=False)

    form.add_group("Advanced") \
        .add_file("config_file", "Config file (optional)", required=False) \
        .add_button(
            "reset",
            "Reset to defaults",
            action={"method": "GET", "url": "/reset"}   # optional custom action
        )

    return form.to_schema()          # ← exact format expected by DynamicForm


# ------------------------------------------------------------------
# POST /form  →  process submitted data
# ------------------------------------------------------------------
@server.on_event("/form", "POST")
def handle_form_submission(data: dict):
    # `data` contains the field keys exactly as you defined in the schema
    username = data.get("username", "")
    seed     = data.get("seed")
    theme    = data.get("theme")
    # … validate / store / start a task …

    # Raise HTTPException for client-side errors
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    # Do something with the values
    print(f"[Extension] User submitted: {username=}, {seed=}, {theme=}")

    # Any dict you return is sent back to the Core (optional)
    return {"status": "success", "saved": True}
```

---

### 2. Schema format (what `DynamicForm` expects)

```json
{
  "layout": [
    { "type": "tab",   "label": "General",   "fields": ["username","seed"] },
    { "type": "tab",   "label": "Appearance","fields": ["theme","high_contrast"] },
    { "type": "group", "label": "Advanced",  "fields": ["config_file","reset"] }
  ],
  "fields": {
    "username":      { "type":"text",      "label":"Username",      "default":"",      "required":false },
    "seed":          { "type":"number",    "label":"Random seed",   "default":"42",    "min":0,"max":9999,"required":true },
    "theme":         { "type":"combobox",  "label":"Theme",         "options":["Light","Dark","Auto"], "default":"Auto","required":false },
    "high_contrast": { "type":"checkbox",  "label":"High-contrast mode","default":false,"required":false },
    "config_file":   { "type":"file",      "label":"Config file (optional)","required":false },
    "reset":         { "type":"button",    "label":"Reset to defaults",
                       "action":{"method":"GET","url":"/reset"} }
  }
}
```

*All fields are **optional** unless `required: true`.*

---

### 3. `plotune_sdk.forms` – fluent schema builder

```python
from plotune_sdk.forms import FormLayout

form = FormLayout()
form.add_tab("Settings") \
    .add_text("api_key", "API Key", required=True) \
    .add_number("timeout", "Timeout (s)", default=30, min_val=5, max_val=300)

schema = form.to_schema()      # → dict ready for GET /form
```

| Method | Field type | Extra keys |
|--------|------------|------------|
| `add_text` | `text` | `default`, `required` |
| `add_number` | `number` | `default`, `min`, `max`, `required` |
| `add_combobox` | `combobox` | `options`, `default`, `required` |
| `add_checkbox` | `checkbox` | `default`, `required` |
| `add_file` | `file` | `required` |
| `add_button` | `button` | `action: {"method":…, "url":…, "payload_fields": […]}` |

---

### 4. Testing locally

```bash
# 1. Run the extension
python -m my_extension

# 2. GET the schema
curl http://127.0.0.1:8100/form | jq .

# 3. POST a filled form
curl -X POST http://127.0.0.1:8100/form \
     -H "Content-Type: application/json" \
     -d '{"username":"alice","seed":123}'
```

> The Core will automatically open the modal when the extension’s manifest contains `"ask_form": true`.

**That’s it!**  
Add the two `@server.on_event` decorators (or just one if you only need a static form) and you have a fully-featured, type-safe user-input dialog.

---

## Example

```python
# examples/example_extension.py
import time, random
from plotune_sdk.runtime import PlotuneRuntime
from plotune_sdk.server import PlotuneServer

server = PlotuneServer()

@server.on_event("/health", "GET")
def health(_):
    return {"status": "active"}

@server.on_ws("fetch")
async def fetch_signal(signal_name, websocket, data):
    print(f"Received WS signal {signal_name}: {data}")
    await websocket.send_json({
                "timestamp": time.time(),
                "value": random.random()
            })

runtime = PlotuneRuntime(
    ext_name="file-extension",
    host="127.0.0.1",
    port=8010,
    core_url="http://127.0.0.1:8000",
    config={
        "id": "file_extension",
        "name": "File Extension",
        "version": "1.0.0",
        "mode": "offline",
        "author": "Plotune SDK Team",
        "enabled": True,
        "connection": {"ip": "127.0.0.1", "port": 8010},
        "configuration": {},
    }
)

@runtime.tray("Open Logs")
def show_logs():
    print("Opening log directory...")

if __name__ == "__main__":
    runtime.start()
```

## Extension Configuration Schema

All extensions must define a configuration payload that matches the **ExtensionConfig** model:

```python
{
  "name": "Simple Reader",
  "id": "simple_reader",
  "version": "1.0.0",
  "description": "Reads table data from defined files.",
  "mode": "offline",
  "author": "Plotune Official",
  "cmd": ["python", "__main__.py"],
  "enabled": true,
  "last_updated": "2025-06-15",
  "git_path": "https://github.com/plotune/simple-reader",
  "category": "Recorder",
  "post_url": "http://localhost:8000/api/extension_click",
  "file_formats": ["csv", "pltx"],
  "ask_form": false,
  "connection": {
    "ip": "127.0.0.1",
    "port": 8105,
    "target": "127.0.0.1",
    "target_port": 8000
  },
  "configuration": {
    "file_path": {
      "type": "string",
      "description": "Path to the target file",
      "default": ""
    }
  }
}
```

---

## Packaging Assets

All icons or resources can be safely bundled inside your SDK package:

```
plotune_sdk/
 ├── assets/
 │   └── icon.png
 ├── server.py
 ├── core.py
 └── runtime.py
```

Access them using:

```python
from importlib.resources import files
from PIL import Image

icon_path = files("plotune_sdk.assets") / "icon.png"
icon = Image.open(icon_path)
```

This works even when your extension is built as a **.exe** or packaged into a **wheel**.

---

## License

Apache License 2.0 © 2025 — **Plotune Team**  
For more details, visit [https://plotune.net](https://plotune.net)


---

### Build. Extend. Integrate.

The Plotune SDK — your gateway to modular and intelligent extensions.

