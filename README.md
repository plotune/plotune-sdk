# Plotune SDK

**Plotune SDK** is a lightweight Python toolkit for developing modular **extensions** that seamlessly integrate with the **Plotune Core** system.  
It provides a unified environment to build, serve, and manage extension logic — including REST APIs, WebSocket handlers, and runtime lifecycle management — all with minimal boilerplate.

---

## ✨ Features

- **FastAPI-based server** — automatically starts a local HTTP/WebSocket server for your extension  
- **Event-driven design** — register logic with decorators like `@server.on_event()` or `@server.on_ws()`  
- **Core communication** — built-in client for registration and heartbeat with Plotune Core  
- **Runtime management** — tray-based control with start/stop/kill functionality  
- **Cross-platform logging** — lightweight rotating file logger without external dependencies  
- **Packaged assets** — safely bundle icons or other resources in your extension package  

---

## 🚀 Example

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
                "value": random.random(),
                "desc": f"{signal_name}",
                "status": True
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
````

## 🧩 Extension Configuration Schema

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

## 🧠 Architecture Overview

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

## 🧰 Development Setup

```bash
# clone repository
git clone https://github.com/plotune/plotune-sdk.git
cd plotune-sdk

# create virtual environment
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# install dependencies
pip install -e ".[dev]"
```

---

## 🖥️ Packaging Assets

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

## 🧩 License

Apache License 2.0 © 2025 — **Plotune Team**  
For more details, visit [https://plotune.net](https://plotune.net)


---

### 🟣 Build. Extend. Integrate.

The Plotune SDK — your gateway to modular and intelligent extensions.

