import uvicorn
import asyncio
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from typing import Callable, Any, Dict, List, Tuple, Optional
from plotune_sdk.models.file_models import FileReadRequest, FileMetaData
from plotune_sdk.models.variable_models import Variable, NewVariable
from plotune_sdk.utils import get_logger, setup_uvicorn_logging, AVAILABLE_PORT

logger = get_logger("plotune_server")


class PlotuneServer:
    """FastAPI-based server for Plotune extensions."""

    def __init__(
        self,
        runtime,
        host: str = "localhost",
        port: int = None,
        log_level: str = "info",
    ):
        """
        Initialize the PlotuneServer instance.

        Args:
            runtime: The extension runtime instance.
            host (str): Host address to bind the FastAPI server.
            port (int, optional): TCP port to listen on. Defaults to AVAILABLE_PORT.
            log_level (str): Logging verbosity level for Uvicorn.
        """
        self.runtime = runtime
        self.api = FastAPI()
        self.host = host
        self.port = port or AVAILABLE_PORT
        self.log_level = log_level
        self._uvicorn_server = None

        self._event_hooks: Dict[Tuple[str, str], List[Callable]] = {}
        self._ws_hooks: Dict[str, List[Callable]] = {}
        self._handler_policy: Dict[Tuple[str, str], bool] = {}
        self._ws_policy: Dict[str, bool] = {}

        self.init_policies()
        self._register_builtin_routes()
        logger.debug(f"PlotuneServer initialized at {host}:{self.port}")

    # -------------------------------------------------------------------------
    # Policies
    # -------------------------------------------------------------------------
    def init_policies(self):
        """Initialize default route policies."""
        self._ws_policy["fetch"] = False
        self._handler_policy[("/health", "GET")] = False
        self._handler_policy[("/stop", "GET")] = False
        self._handler_policy[("/read-file", "POST")] = True
        self._handler_policy[("/form", "GET")] = False
        self._handler_policy[("/form", "POST")] = True
        self._handler_policy[("/fetch-meta", "GET")] = False
        self._handler_policy[("/bridge/{variable_name}", "POST")] = True
        self._handler_policy[("/unbridge/{variable_name}", "POST")] = True
        self._handler_policy[("/functions", "GET")] = False
        self._handler_policy[("/add-variable/{variable_name}", "POST")] = True

    def update_policy(self, path: str, method: str, required: bool):
        """Update or override the route policy."""
        logger.debug(f"Updating policy for {method} {path} to {'required' if required else 'optional'}")
        self._handler_policy[(path, method.upper())] = required

    # -------------------------------------------------------------------------
    # Built-in routes
    # -------------------------------------------------------------------------
    def _register_builtin_routes(self):
        @self.api.get("/health", tags=["System"])
        async def health(request: Request):
            result = await self._trigger_event("/health", "GET", request)
            return result or {"status": "ok"}

        @self.api.get("/stop", tags=["System"])
        async def stop(request: Request):
            result = await self._trigger_event("/stop", "GET", request)
            return result or {"status": "ok"}

        @self.api.post("/read-file", response_model=FileMetaData, tags=["Tasks"])
        async def read_file(request: FileReadRequest):
            result = await self._trigger_event("/read-file", "POST", request)
            if result is None and self._handler_policy[("/read-file", "POST")]:
                raise HTTPException(status_code=500, detail="Extension doesn't handle this request")
            return result or {"path": request.path, "status": "not_handled"}

        @self.api.get("/form", tags=["form"])
        async def user_input_form():
            result = await self._trigger_event("/form", "GET", None)
            return result or {}

        @self.api.post("/form", tags=["form"])
        async def collect_user_input(input_form: dict):
            result = await self._trigger_event("/form", "POST", input_form)
            if result is None and self._handler_policy[("/form", "POST")]:
                raise HTTPException(status_code=500, detail="Extension doesn't handle this request")
            return result or {"status": "success"}

        @self.api.get("/fetch-meta", tags=["fetch"])
        async def fetch_source_meta():
            result = await self._trigger_event("/fetch-meta", "GET", None)
            return result or {"headers": []}

        @self.api.post("/bridge/{variable_name}")
        async def bridge_variable(variable_name: str, variable: Variable):
            result = await self._trigger_event("/bridge/{variable_name}", "POST", variable)
            if result is None and self._handler_policy[("/bridge/{variable_name}", "POST")]:
                raise HTTPException(status_code=500, detail="Extension doesn't handle this request")
            return result or {"status": "success"}

        @self.api.post("/unbridge/{variable_name}")
        async def unbridge_variable(variable_name: str, variable: Variable):
            result = await self._trigger_event("/unbridge/{variable_name}", "POST", variable)
            if result is None and self._handler_policy[("/unbridge/{variable_name}", "POST")]:
                raise HTTPException(status_code=500, detail="Extension doesn't handle this request")
            return result or {"status": "success"}

        @self.api.get("/functions", tags=["functions"])
        async def get_functions():
            result = await self._trigger_event("/functions", "GET", None)
            return result or {"functions": []}

        @self.api.post("/add-variable/{variable_name}", tags=["variables"])
        async def add_new_variable(variable_name: str, request: NewVariable):
            result = await self._trigger_event("/add-variable/{variable_name}", "POST", request)
            if result is None and self._handler_policy[("/add-variable/{variable_name}", "POST")]:
                raise HTTPException(status_code=500, detail="Extension doesn't handle this request")
            return result or {"status": "success"}

        @self.api.websocket("/fetch/{signal_name}")
        async def websocket_endpoint(websocket: WebSocket, signal_name: str):
            handlers = self._ws_hooks.get("fetch", [])
            if not handlers:
                await websocket.close(code=4403)
                return

            await websocket.accept()
            tasks = []
            for handler in handlers:
                result = handler(signal_name, websocket, None)
                if asyncio.iscoroutine(result):
                    tasks.append(asyncio.create_task(result))
            try:
                await asyncio.gather(*tasks)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {signal_name}")
            except Exception as e:
                logger.error(f"WebSocket error for {signal_name}: {e}")
                await websocket.close(code=1011, reason="internal error")

    # -------------------------------------------------------------------------
    # Event decorators
    # -------------------------------------------------------------------------
    def on_event(self, path: str, method: str = "GET"):
        """Register a function as an HTTP event handler."""
        def decorator(func: Callable[..., Any]):
            key = (path, method.upper())
            self._event_hooks.setdefault(key, []).append(func)
            return func
        return decorator

    def on_ws(self, route: str = "fetch", require_response: bool = False):
        """Register a WebSocket handler."""
        self._ws_policy[route] = require_response
        def decorator(func: Callable[..., Any]):
            self._ws_hooks.setdefault(route, []).append(func)
            return func
        return decorator

    # -------------------------------------------------------------------------
    # Event triggering
    # -------------------------------------------------------------------------
    async def _trigger_event(self, path: str, method: str, *args, **kwargs) -> Optional[Any]:
        key = (path, method.upper())
        if key not in self._event_hooks:
            return None
        result = None
        for func in self._event_hooks[key]:
            out = func(*args, **kwargs)
            if asyncio.iscoroutine(out):
                out = await out
            result = out
        return result

    async def _trigger_ws_event(self, signal_name: str, websocket: WebSocket, data: Any):
        if signal_name not in self._ws_hooks:
            return None
        result = None
        for func in self._ws_hooks[signal_name]:
            out = func(signal_name, websocket, data)
            if asyncio.iscoroutine(out):
                out = await out
            result = out
        return result

    # -------------------------------------------------------------------------
    # Dynamic route registration
    # -------------------------------------------------------------------------
    def route(self, path: str, method: str = "GET"):
        """Dynamically register a new HTTP route on the FastAPI app."""
        def decorator(func):
            self.api.add_api_route(path, func, methods=[method])
            return func
        return decorator

    # -------------------------------------------------------------------------
    # Server control
    # -------------------------------------------------------------------------
    async def serve(self):
        """Start the Uvicorn server (async)."""
        log_config = setup_uvicorn_logging()
        config = uvicorn.Config(
            self.api,
            host=self.host,
            port=self.port,
            log_level=self.log_level,
            log_config=log_config,
            access_log=False,
        )
        server = uvicorn.Server(config)
        self._uvicorn_server = server
        await server.serve()

    async def shutdown(self):
        """Gracefully stop the Uvicorn server."""
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
