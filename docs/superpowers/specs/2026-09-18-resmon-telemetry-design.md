# Design Document: ResMon Web - High-Performance Linux Telemetry Service

**Date:** 2026-09-18  
**Status:** Approved  
**Author:** AI Pair Programmer & User

---

## 1. Executive Summary & Goals

ResMon Web is an ultra-low-overhead, high-performance real-time telemetry and system monitoring dashboard specifically designed for Linux environments and deployed via Docker.

### Key Goals:
- **Zero Impact on Latency & Performance:** Sampling takes < 2ms per cycle, using non-blocking native asynchronous loops (`asyncio`) and reading directly from Linux `/proc` and `/sys` virtual filesystems without spawning subprocesses or heavy tools.
- **Deep Linux Metrics:**
  - CPU: Overall utilization %, per-core utilization %, CPU Pressure Stall Information (PSI stall latency from `/proc/pressure/cpu`), and Load Average.
  - RAM & Swap: Memory utilization (used, free, buffers, cached, available), swap usage, Memory Pressure (PSI `/proc/pressure/memory`), and memory access dynamics (minor & major page faults per second from `/proc/vmstat`).
  - Disk I/O: Read/Write IOPS, Read/Write throughput (MB/s), Disk Pressure (PSI `/proc/pressure/io`), and filesystem partition usage.
  - Network: Rx/Tx throughput (KB/s and packets/s), connection state breakdown (ESTABLISHED, TIME_WAIT, etc.), and interactive open/listening ports table with PID and process name mappings.
- **In-Memory Ring Buffer:** Retains 15 minutes of historical points in RAM (`collections.deque`), causing zero disk write wear and immediate instant chart rendering on page load.
- **Modern Dark Tech Glassmorphism UI:** Built per `ui-ux-pro-max` design system with Tailwind CSS, Chart.js (GPU canvas acceleration), Phosphor SVG icons, responsive layout, and pause/resume stream controls.
- **Containerized Deployment:** Multi-stage Docker image (~85MB) with host namespaces (`pid: "host"`, `network_mode: "host"`, volume mounts `/proc:/host/proc:ro`, `/sys:/host/sys:ro`).

---

## 2. Architecture & Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Host Linux System                      │
│   /proc/stat, /proc/pressure/*, /proc/vmstat, /proc/net/*   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Mounts: /proc, /sys (ro)
                               │ Namespaces: host pid, host net
┌──────────────────────────────▼──────────────────────────────┐
│                    ResMon Web Docker Container              │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    FastAPI Backend                    │  │
│  │                                                       │  │
│  │  ┌───────────────────┐       ┌──────────────────────┐ │  │
│  │  │ Metrics Collector │       │ In-Memory Ring Buffer│ │  │
│  │  │ (asyncio task 1s) ├──────►│ (deque: 900 points)  │ │  │
│  │  └─────────┬─────────┘       └──────────┬───────────┘ │  │
│  │            │                            │             │  │
│  │            │ Delta broadcast            │ Snapshot    │  │
│  │            ▼                            ▼             │  │
│  │    WebSocket (/ws/metrics)        REST (/api/history) │  │
│  └────────────────────┬────────────────────┬─────────────┘  │
│                       │                    │                │
│                       ▼                    ▼                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              React / Vite Frontend SPA                │  │
│  │  - Glassmorphic Cards (#0F172A / #1B2336)             │  │
│  │  - Chart.js Streaming Time-Series (Canvas GPU)        │  │
│  │  - Per-Core CPU Gauges & Page Faults Sparkline        │  │
│  │  - Network Ports & Connections Table (Search/Filter)  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Data Specifications

### 3.1 Linux Kernel Metric Sources
1. **CPU:**
   - Utilization: `psutil.cpu_percent(interval=None, percpu=True)`
   - Latency / Pressure: `/proc/pressure/cpu`
     - `some avg10=X avg60=Y avg300=Z total=T` (microseconds tasks were stalled waiting for CPU)
   - Load Average: `os.getloadavg()` or `/proc/loadavg` (1m, 5m, 15m)
2. **Memory:**
   - Utilization: `psutil.virtual_memory()` (`total`, `used`, `free`, `buffers`, `cached`, `available`)
   - Swap: `psutil.swap_memory()` (`total`, `used`, `free`, `sin`, `sout`)
   - Memory Pressure: `/proc/pressure/memory` (`some` and `full`)
   - Memory Access Dynamics: `/proc/vmstat` delta calculation:
     - `pgfault` (minor page faults / memory address translations)
     - `pgmajfault` (major page faults / disk read page faults)
     - `pgpgin`, `pgpgout` (pages read/written)
3. **Disk I/O:**
   - Disk Operations: `psutil.disk_io_counters(perdisk=True)`
     - Delta calculation for Read IOPS, Write IOPS, Read MB/s, Write MB/s
   - I/O Pressure: `/proc/pressure/io` (`some` and `full` stall time)
   - Filesystem Usage: `psutil.disk_partitions()` & `psutil.disk_usage()`
4. **Network & Sockets:**
   - Traffic: `psutil.net_io_counters()` (Rx/Tx bytes, packets, drops, errors per sec)
   - Sockets: `psutil.net_connections(kind='all')` or direct parse of `/proc/net/tcp` and `/proc/net/tcp6`
     - Connection counts by status (`ESTABLISHED`, `TIME_WAIT`, `CLOSE_WAIT`, `SYN_SENT`, `LISTEN`)
     - Open listening ports list: `port`, `proto` (TCP/UDP), `address`, `pid`, `process_name`

### 3.2 WebSocket Data Format
Every second, the server broadcasts:
```json
{
  "timestamp": 1773831000.123,
  "cpu": {
    "overall": 14.2,
    "cores": [12.0, 18.5, 10.1, 16.2],
    "psi_some": {"avg10": 0.0, "avg60": 0.0, "avg300": 0.0, "total": 12400},
    "loadavg": [0.45, 0.52, 0.48]
  },
  "memory": {
    "total": 16777216000,
    "used": 8388608000,
    "free": 4194304000,
    "cached": 3145728000,
    "buffers": 1048576000,
    "percent": 50.0,
    "swap_total": 4294967296,
    "swap_used": 0,
    "swap_percent": 0.0,
    "psi_some": {"avg10": 0.0, "avg60": 0.0, "avg300": 0.0},
    "page_faults_minor_sec": 450,
    "page_faults_major_sec": 0
  },
  "disk": {
    "read_mbs": 1.25,
    "write_mbs": 4.80,
    "read_iops": 45,
    "write_iops": 112,
    "psi_some": {"avg10": 0.02, "avg60": 0.01, "avg300": 0.0},
    "partitions": [
      {"device": "/dev/sda1", "mountpoint": "/", "total": 512000000000, "used": 150000000000, "percent": 29.3}
    ]
  },
  "network": {
    "rx_kbs": 245.8,
    "tx_kbs": 180.2,
    "connections_count": {"ESTABLISHED": 42, "TIME_WAIT": 8, "LISTEN": 12},
    "listening_ports": [
      {"port": 8080, "proto": "tcp", "pid": 1234, "process": "python"}
    ]
  }
}
```

---

## 4. UI/UX Design System Specification

- **Palette:**
  - Background: `#0F172A`
  - Cards: `#1B2336` (with `backdrop-blur-md` and `border border-slate-700/50`)
  - Accent / CPU: Cyan `#06B6D4`
  - Memory: Purple `#8B5CF6`
  - Disk: Amber `#F59E0B`
  - Network: Emerald `#10B981`
  - Warning/Pressure: Rose `#F43F5E`
- **Typography:** Plus Jakarta Sans & JetBrains Mono
- **Controls:**
  - Pause / Resume toggle
  - Resolution selector (1m, 5m, 15m)
  - Port search and filter bar
  - Per-core drill-down modal/view

---

## 5. Docker Deployment & Security

- **Base Image:** `python:3.11-slim`
- **Builder Stage:** `node:20-alpine` for frontend build
- **Host Integration:**
  - `network_mode: "host"`
  - `pid: "host"`
  - Volumes mounted strictly `:ro`:
    - `/proc:/host/proc:ro`
    - `/sys:/host/sys:ro`
    - `/etc/os-release:/host/etc/os-release:ro`
- **Resource Constraints in compose:** CPU limit 0.2, Memory limit 128MB.
