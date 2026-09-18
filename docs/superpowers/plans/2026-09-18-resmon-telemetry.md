# ResMon Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and containerize ResMon Web, an ultra-low-overhead Linux telemetry monitoring web application featuring deep system metrics (PSI CPU latency, per-core utilization, page faults, disk IOPS, network connections & ports) and a responsive glassmorphism dark-tech UI with real-time WebSocket streaming.

**Architecture:** A lightweight asynchronous FastAPI backend collects Linux metrics directly from `/proc` and `psutil` in <2ms per tick, buffers 15 minutes of history in an in-memory ring buffer (`collections.deque`), and streams live deltas over WebSockets. A multi-stage Docker build compiles a modern React/Vite SPA (styled with Tailwind CSS and Chart.js per the `ui-ux-pro-max` design system) into static assets served directly by FastAPI under `network_mode: "host"` and `pid: "host"`.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, psutil, React 19, TypeScript, Vite, Tailwind CSS, Chart.js, Phosphor Icons, Docker, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-18-resmon-telemetry-design.md`

## Global Constraints

- **Minimal System Overhead:** Metric collection cycle must take < 2ms, zero subprocess forks, no disk writes for metrics history.
- **Linux & Docker First:** Must mount `/proc` and `/sys` read-only (`ro`), run in host network and pid namespaces.
- **Graceful Fallbacks:** If running outside Linux (e.g., macOS dev environment) or if PSI is unavailable, the backend must not crash; it should fall back cleanly.
- **Design System Quality:** Adhere strictly to `ui-ux-pro-max` dark glassmorphism guidelines (`#0F172A`, `#1B2336`, Plus Jakarta Sans / JetBrains Mono, Phosphor vector icons, zero emojis as structural icons).
- **Zero Placeholders:** All tasks must have complete code and verifiable test instructions.

---

### Task 1: Project Scaffolding & Configuration (`.env`, `backend/config.py`)

**Files:**
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: Environment variables (`PORT`, `HOST`, `UPDATE_INTERVAL`, `HISTORY_POINTS`, `HOST_PROC`, `HOST_SYS`).
- Produces: `backend.config.Settings` pydantic/dataclass instance accessible globally.

- [ ] **Step 1: Write the failing test for configuration loading**

```python
# tests/test_config.py
import os
from backend.config import get_settings

def test_settings_defaults():
    settings = get_settings()
    assert settings.PORT == 8080
    assert settings.HOST == "0.0.0.0"
    assert settings.UPDATE_INTERVAL == 1.0
    assert settings.HISTORY_POINTS == 900
    assert settings.HOST_PROC in ["/host/proc", "/proc"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py`
Expected: FAIL with module not found or import error.

- [ ] **Step 3: Create dependencies file and implement `backend/config.py`**

Create `requirements.txt`:
```txt
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
psutil>=6.1.0
pydantic-settings>=2.6.0
pytest>=8.3.0
httpx>=0.28.0
websockets>=13.1
```

Create `backend/config.py`:
```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 8080
    HOST: str = "0.0.0.0"
    UPDATE_INTERVAL: float = 1.0
    HISTORY_POINTS: int = 900
    HOST_PROC: str = "/host/proc" if os.path.exists("/host/proc") else "/proc"
    HOST_SYS: str = "/host/sys" if os.path.exists("/host/sys") else "/sys"
    LOG_LEVEL: str = "info"

    class Config:
        env_file = ".env"
        extra = "ignore"

_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

- [ ] **Step 4: Create `.env.example` and run test to verify it passes**

Run: `pytest tests/test_config.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example backend/config.py tests/test_config.py
git commit -m "feat(config): add project settings and env configuration"
```

---

### Task 2: Low-Overhead Linux Metrics Collector (`backend/collector.py`)

**Files:**
- Create: `backend/collector.py`
- Test: `tests/test_collector.py`

**Interfaces:**
- Consumes: `backend.config.get_settings`
- Produces: `backend.collector.SystemMetricsCollector` with `get_static_info() -> dict` and `collect_snapshot() -> dict`.

- [ ] **Step 1: Write test for PSI parser and metrics snapshot collection**

```python
# tests/test_collector.py
from backend.collector import SystemMetricsCollector, parse_psi_file

def test_parse_psi_content():
    content = """some avg10=0.04 avg60=0.02 avg300=0.01 total=1234567\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0"""
    parsed = parse_psi_file(content)
    assert "some" in parsed
    assert parsed["some"]["avg10"] == 0.04
    assert parsed["some"]["total"] == 1234567

def test_collector_snapshot_structure():
    collector = SystemMetricsCollector()
    snapshot = collector.collect_snapshot()
    assert "timestamp" in snapshot
    assert "cpu" in snapshot
    assert "overall" in snapshot["cpu"]
    assert "cores" in snapshot["cpu"]
    assert "memory" in snapshot
    assert "total" in snapshot["memory"]
    assert "disk" in snapshot
    assert "network" in snapshot
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector.py`
Expected: FAIL with `collector` not found.

- [ ] **Step 3: Implement `backend/collector.py`**

Implement `backend/collector.py` supporting:
- `/proc/pressure/cpu`, `/proc/pressure/memory`, `/proc/pressure/io` parsing with fallback when running on non-Linux or without PSI.
- `/proc/vmstat` delta calculation for minor/major page faults (`pgfault`, `pgmajfault`).
- `psutil.cpu_percent(interval=None, percpu=True)` for non-blocking CPU usage.
- `psutil.virtual_memory()`, `psutil.swap_memory()`.
- `psutil.disk_io_counters()`, `psutil.disk_partitions()`, `psutil.disk_usage()`.
- `psutil.net_io_counters()`, `psutil.net_connections()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/collector.py tests/test_collector.py
git commit -m "feat(collector): implement low-overhead linux metrics collector"
```

---

### Task 3: In-Memory Ring Buffer & State Manager (`backend/buffer.py`)

**Files:**
- Create: `backend/buffer.py`
- Test: `tests/test_buffer.py`

**Interfaces:**
- Consumes: metric snapshots (`dict`).
- Produces: `backend.buffer.MetricsBuffer` with `append(snapshot: dict)` and `get_history() -> list[dict]`.

- [ ] **Step 1: Write test for Ring Buffer**

```python
# tests/test_buffer.py
from backend.buffer import MetricsBuffer

def test_buffer_maxlen():
    buf = MetricsBuffer(maxlen=3)
    buf.append({"t": 1})
    buf.append({"t": 2})
    buf.append({"t": 3})
    buf.append({"t": 4})
    history = buf.get_history()
    assert len(history) == 3
    assert history[0]["t"] == 2
    assert history[2]["t"] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_buffer.py`
Expected: FAIL

- [ ] **Step 3: Implement `backend/buffer.py`**

Using thread-safe `collections.deque(maxlen=maxlen)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_buffer.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/buffer.py tests/test_buffer.py
git commit -m "feat(buffer): implement in-memory ring buffer"
```

---

### Task 4: FastAPI REST API & WebSocket Streaming (`backend/main.py`)

**Files:**
- Create: `backend/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Endpoints:
  - `GET /api/info` -> Static host information
  - `GET /api/history` -> List of historical snapshots
  - `GET /api/health` -> `{"status": "ok"}`
  - `WS /ws/metrics` -> Real-time broadcasting to connected clients
  - Static file mount: `/` serving `frontend/dist` if available.

- [ ] **Step 1: Write test for API endpoints**

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_info():
    response = client.get("/api/info")
    assert response.status_code == 200
    assert "hostname" in response.json()

def test_history():
    response = client.get("/api/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py`
Expected: FAIL

- [ ] **Step 3: Implement `backend/main.py`**

Include background `asyncio.create_task` collector loop running every `settings.UPDATE_INTERVAL`, pushing to `MetricsBuffer` and broadcasting to active WebSocket connections.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/main.py tests/test_api.py
git commit -m "feat(api): implement fastAPI routes and websocket broadcaster"
```

---

### Task 5: Frontend Scaffolding & Setup (`frontend/`)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css` (Tailwind & fonts)

- [ ] **Step 1: Create `package.json` with React, Vite, Tailwind, Chart.js, and Phosphor Icons**
- [ ] **Step 2: Configure Vite proxy to `http://localhost:8080` for development**
- [ ] **Step 3: Configure Tailwind CSS tokens matching `ui-ux-pro-max` Glassmorphism Dark Tech palette**
- [ ] **Step 4: Run `npm install` and verify build setup**
- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold react-vite project with tailwind and chart.js"
```

---

### Task 6: Frontend Dashboard Components & Glassmorphism Theme

**Files:**
- Create: `frontend/src/types/metrics.ts`
- Create: `frontend/src/hooks/useTelemetry.ts`
- Create: `frontend/src/components/Header.tsx`
- Create: `frontend/src/components/KpiRow.tsx`
- Create: `frontend/src/components/CpuSection.tsx` (Per-core grid & PSI latency)
- Create: `frontend/src/components/MemorySection.tsx` (RAM, Swap, Page Faults sparkline)
- Create: `frontend/src/components/DiskSection.tsx` (IOPS & Throughput charts)
- Create: `frontend/src/components/NetworkSection.tsx` (Traffic chart, Connections & Ports table)
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Define TypeScript interfaces for telemetry and snapshot data**
- [ ] **Step 2: Implement `useTelemetry` hook handling REST initial load + WebSocket streaming with auto-reconnect and pause/resume**
- [ ] **Step 3: Implement `Header.tsx` with Live Pulse badge, pause toggle, resolution switch**
- [ ] **Step 4: Implement `KpiRow.tsx` with glassmorphic cards and PSI pressure badges**
- [ ] **Step 5: Implement `CpuSection.tsx` with Chart.js streaming chart and per-core progress gauges**
- [ ] **Step 6: Implement `MemorySection.tsx` and `DiskSection.tsx`**
- [ ] **Step 7: Implement `NetworkSection.tsx` with interactive searchable/filterable listening ports and sockets table**
- [ ] **Step 8: Build frontend with `npm run build` and ensure zero TypeScript errors**
- [ ] **Step 9: Commit**

```bash
git add frontend/src/
git commit -m "feat(ui): complete glassmorphic telemetry dashboard components"
```

---

### Task 7: Multi-Stage Dockerfile & Docker Compose

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Write multi-stage `Dockerfile` (`node:20-alpine` builder + `python:3.11-slim` runtime)**
- [ ] **Step 2: Write `docker-compose.yml` with `network_mode: "host"`, `pid: "host"`, read-only mounts `/proc` and `/sys`**
- [ ] **Step 3: Test `docker compose build` locally**
- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat(docker): add multi-stage dockerfile and host-monitoring compose"
```

---

### Task 8: Verification & Validation

- [ ] **Step 1: Run all Python unit tests with `pytest -v`**
- [ ] **Step 2: Run frontend production build `npm run build`**
- [ ] **Step 3: Test service execution locally and verify `/api/health`, `/api/info`, and `/ws/metrics`**
- [ ] **Step 4: Commit final refinements**
