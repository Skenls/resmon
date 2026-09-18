import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.buffer import MetricsBuffer
from backend.collector import SystemMetricsCollector
from backend.config import get_settings

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
            snapshot = collector.collect_snapshot()
            buffer.append(snapshot)

            if connected_clients:
                payload = json.dumps(snapshot)
                disconnected = set()
                for ws in connected_clients:
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        disconnected.add(ws)
                for dead_ws in disconnected:
                    connected_clients.discard(dead_ws)
        except Exception as e:
            logger.error("Error in metrics collector tick: %s", e)

        await asyncio.sleep(settings.UPDATE_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prime the buffer with initial snapshot
    init_snap = collector.collect_snapshot()
    buffer.append(init_snap)

    task = asyncio.create_task(metrics_collector_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="ResMon Web Telemetry", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from backend.auth import authenticate_http_request, authenticate_websocket
from fastapi import Depends, status


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
        latest = collector.collect_snapshot()
    return latest


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    if not authenticate_websocket(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    connected_clients.add(websocket)

    # Immediately push latest snapshot upon connection
    latest = buffer.get_latest()
    if latest is None:
        latest = collector.collect_snapshot()
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


from backend.auth import authenticate_http_request, authenticate_websocket, COOKIE_NAME
from fastapi import Depends, Request, status


# Mount frontend distribution directory if built
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist"))
if os.path.isdir(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str, auth: bool = Depends(authenticate_http_request)):
        file_path = os.path.join(dist_dir, full_path)
        target = file_path if (os.path.exists(file_path) and os.path.isfile(file_path)) else os.path.join(dist_dir, "index.html")
        resp = FileResponse(target)
        if hasattr(request.state, "session_token"):
            resp.set_cookie(
                key=COOKIE_NAME,
                value=request.state.session_token,
                httponly=True,
                samesite="lax",
                max_age=86400,
            )
        return resp

