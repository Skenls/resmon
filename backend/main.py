import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import json
import logging
import os
import secrets
from typing import Set
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.auth import COOKIE_NAME, authenticate_http_request, authenticate_websocket
from backend.buffer import MetricsBuffer
from backend.collector import SystemMetricsCollector
from backend.config import get_settings, validate_security

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("resmon")

collector = SystemMetricsCollector()
buffer = MetricsBuffer(maxlen=settings.HISTORY_POINTS)
connected_clients: Set[WebSocket] = set()


async def metrics_collector_loop() -> None:
    """Background task collecting telemetry every UPDATE_INTERVAL."""
    logger.info("Starting background telemetry collector (interval=%.2fs)", settings.UPDATE_INTERVAL)
    while True:
        try:
            snapshot = await asyncio.to_thread(collector.collect_snapshot)
            buffer.append(snapshot)

            clients = list(connected_clients)
            if clients:
                payload = json.dumps(snapshot)
                results = await asyncio.gather(
                    *(asyncio.wait_for(ws.send_text(payload), timeout=2.0) for ws in clients),
                    return_exceptions=True,
                )
                for ws, result in zip(clients, results):
                    if isinstance(result, BaseException):
                        connected_clients.discard(ws)
                        try:
                            await ws.close()
                        except Exception:
                            pass
        except Exception as e:
            logger.error("Error in metrics collector tick: %s", e)

        await asyncio.sleep(settings.UPDATE_INTERVAL)


mcp_server = None
mcp_app = None
if settings.MCP_ENABLED:
    if not settings.MCP_API_KEY:
        logger.warning("MCP_ENABLED is true but MCP_API_KEY is empty; MCP stays disabled")
    else:
        from backend.mcp_server import create_mcp

        mcp_server, mcp_app = create_mcp(buffer, settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security(settings)
    if not settings.AUTH_ENABLED:
        logger.warning("AUTH_ENABLED=false: the web UI is unprotected")
    else:
        if len(settings.AUTH_PASSWORD) < 12:
            logger.warning("AUTH_PASSWORD is shorter than 12 characters")
        if len(settings.SECRET_KEY) < 32:
            logger.warning("SECRET_KEY is shorter than 32 characters")

    # Prime the buffer with initial snapshot
    init_snap = await asyncio.to_thread(collector.collect_snapshot)
    buffer.append(init_snap)

    async with AsyncExitStack() as stack:
        if mcp_server is not None:
            await stack.enter_async_context(mcp_server.session_manager.run())
        task = asyncio.create_task(metrics_collector_loop())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="ResMon Web Telemetry",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


if mcp_server is not None:

    @app.middleware("http")
    async def mcp_api_key_guard(request, call_next):
        path = request.url.path
        if path == "/mcp":
            request.scope["path"] = "/mcp/"
            path = "/mcp/"
        if path.startswith("/mcp/"):
            auth = request.headers.get("authorization", "")
            key = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            key = key or request.headers.get("x-api-key", "")
            if not secrets.compare_digest(key.encode("utf-8"), settings.MCP_API_KEY.encode("utf-8")):
                return JSONResponse(
                    {"detail": "Invalid MCP API key"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)


@app.get("/api/health")
async def get_health(auth: bool = Depends(authenticate_http_request)):
    return {"status": "ok"}


@app.get("/api/info")
async def get_info(auth: bool = Depends(authenticate_http_request)):
    return collector.get_static_info()


@app.get("/api/history")
async def get_history(auth: bool = Depends(authenticate_http_request)):
    return buffer.get_history()


@app.get("/api/snapshot")
async def get_snapshot(auth: bool = Depends(authenticate_http_request)):
    latest = buffer.get_latest()
    if latest is None:
        latest = await asyncio.to_thread(collector.collect_snapshot)
    return latest


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        return True
    host = websocket.headers.get("host")
    return bool(host) and urlsplit(origin).netloc == host


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    if not authenticate_websocket(websocket) or not _origin_allowed(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if len(connected_clients) >= settings.MAX_WS_CLIENTS:
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    await websocket.accept()
    connected_clients.add(websocket)

    # Immediately push latest snapshot upon connection
    latest = buffer.get_latest()
    if latest is None:
        latest = await asyncio.to_thread(collector.collect_snapshot)
        buffer.append(latest)
    try:
        await websocket.send_text(json.dumps(latest))
    except Exception:
        connected_clients.discard(websocket)
        return

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WebSocket error: %s", e)
    finally:
        connected_clients.discard(websocket)


if mcp_app is not None:
    app.mount("/mcp", mcp_app)


# Mount frontend distribution directory if built
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist"))


def resolve_spa_file(full_path: str) -> str:
    root = os.path.realpath(dist_dir)
    try:
        candidate = os.path.realpath(os.path.join(root, full_path))
        inside = os.path.commonpath([root, candidate]) == root
    except (OSError, ValueError):
        inside = False
        candidate = ""
    if not inside or not os.path.isfile(candidate):
        candidate = os.path.join(root, "index.html")
    return candidate


if os.path.isdir(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str, _auth: bool = Depends(authenticate_http_request)):
        resp = FileResponse(resolve_spa_file(full_path))
        if hasattr(request.state, "session_token"):
            resp.set_cookie(
                key=COOKIE_NAME,
                value=request.state.session_token,
                httponly=True,
                samesite="lax",
                secure=settings.COOKIE_SECURE or request.url.scheme == "https",
                max_age=86400,
            )
        return resp

