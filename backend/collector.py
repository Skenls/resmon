import os
import platform
import time
from typing import Any, Dict, List, Optional
import psutil

from backend.config import get_settings


def parse_psi_file(content: Optional[str]) -> Dict[str, Dict[str, float]]:
    """
    Parse Linux PSI (Pressure Stall Information) content from /proc/pressure/{cpu,memory,io}.
    Format:
    some avg10=0.00 avg60=0.00 avg300=0.00 total=1234
    full avg10=0.00 avg60=0.00 avg300=0.00 total=5678
    """
    if not content:
        return {}

    result: Dict[str, Dict[str, float]] = {}
    for line in content.strip().splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        kind = parts[0]  # "some" or "full"
        metrics: Dict[str, float] = {}
        for item in parts[1:]:
            if "=" in item:
                k, v = item.split("=", 1)
                try:
                    metrics[k] = float(v) if "." in v else int(v)
                except ValueError:
                    metrics[k] = 0.0
        result[kind] = metrics
    return result


class SystemMetricsCollector:
    """
    Ultra-low-overhead Linux system telemetry collector.
    Avoids spawning subprocesses and reads directly from psutil and /proc.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.host_proc = self.settings.HOST_PROC
        self.host_sys = self.settings.HOST_SYS

        self._last_time = time.time()

        # Initialize psutil counters
        psutil.cpu_percent(interval=None, percpu=True)
        self._last_disk_io = psutil.disk_io_counters()
        self._last_net_io = psutil.net_io_counters()
        self._last_vmstat = self._read_vmstat()

        # Process name cache by PID to avoid repeated name lookup overhead
        self._pid_name_cache: Dict[int, str] = {}

        # Cache static info
        self._static_info = self._gather_static_info()
        self._last_partition_check = 0.0
        self._cached_partitions: List[Dict[str, Any]] = []

    def _read_proc_file(self, rel_path: str) -> Optional[str]:
        """Read virtual file from host_proc or standard /proc."""
        target_path = os.path.join(self.host_proc, rel_path.lstrip("/"))
        if not os.path.exists(target_path):
            target_path = os.path.join("/proc", rel_path.lstrip("/"))
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return None
        return None

    def _read_psi(self, resource: str) -> Dict[str, Dict[str, float]]:
        """Read Linux PSI from /proc/pressure/<resource>."""
        content = self._read_proc_file(f"pressure/{resource}")
        return parse_psi_file(content)

    def _read_vmstat(self) -> Dict[str, int]:
        """Read /proc/vmstat for page fault and paging metrics."""
        content = self._read_proc_file("vmstat")
        if not content:
            return {}
        result: Dict[str, int] = {}
        for line in content.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] in ("pgfault", "pgmajfault", "pgpgin", "pgpgout"):
                try:
                    result[parts[0]] = int(parts[1])
                except ValueError:
                    pass
        return result

    def _gather_static_info(self) -> Dict[str, Any]:
        """Collect static OS and hardware information once on initialization."""
        hostname = platform.node()
        kernel = platform.release()

        # Try to read OS Name from /host/etc/os-release or /etc/os-release
        os_name = platform.platform()
        for os_rel_path in [
            os.path.join(self.host_proc, "../etc/os-release"),
            "/etc/os-release",
        ]:
            real_path = os.path.abspath(os_rel_path)
            if os.path.exists(real_path):
                try:
                    with open(real_path, "r") as f:
                        for line in f:
                            if line.startswith("PRETTY_NAME="):
                                os_name = line.strip().split("=", 1)[1].strip('"')
                                break
                except Exception:
                    pass
                break

        # CPU Brand / Model
        cpu_model = platform.processor() or "Unknown CPU"
        cpuinfo = self._read_proc_file("cpuinfo")
        if cpuinfo:
            for line in cpuinfo.splitlines():
                if "model name" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                    break

        mem = psutil.virtual_memory()
        boot_time = psutil.boot_time()

        return {
            "hostname": hostname,
            "os": os_name,
            "kernel": kernel,
            "cpu_model": cpu_model,
            "cpu_cores_physical": psutil.cpu_count(logical=False) or 1,
            "cpu_cores_logical": psutil.cpu_count(logical=True) or 1,
            "total_memory": mem.total,
            "boot_time": boot_time,
        }

    def get_static_info(self) -> Dict[str, Any]:
        """Return static system info with live uptime."""
        info = dict(self._static_info)
        info["uptime_seconds"] = int(time.time() - info["boot_time"])
        return info

    def _get_partitions(self) -> List[Dict[str, Any]]:
        """Refresh partition stats every 30s to keep overhead minimal."""
        now = time.time()
        if now - self._last_partition_check < 30 and self._cached_partitions:
            return self._cached_partitions

        self._last_partition_check = now
        partitions: List[Dict[str, Any]] = []
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    })
                except (PermissionError, FileNotFoundError):
                    continue
        except Exception:
            pass

        self._cached_partitions = partitions
        return partitions

    def _get_network_connections_and_ports(self) -> Dict[str, Any]:
        """Collect active connections summary and listening ports."""
        conn_counts: Dict[str, int] = {
            "ESTABLISHED": 0,
            "LISTEN": 0,
            "TIME_WAIT": 0,
            "CLOSE_WAIT": 0,
            "SYN_SENT": 0,
            "OTHER": 0,
        }
        listening_ports: List[Dict[str, Any]] = []

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError):
            connections = []
        except Exception:
            connections = []

        active_pids = set()
        for conn in connections:
            status = conn.status or "OTHER"
            if status in conn_counts:
                conn_counts[status] += 1
            else:
                conn_counts["OTHER"] += 1

            if status == "LISTEN" and conn.laddr:
                pid = conn.pid
                pname = "unknown"
                if pid:
                    active_pids.add(pid)
                    if pid in self._pid_name_cache:
                        pname = self._pid_name_cache[pid]
                    else:
                        try:
                            proc = psutil.Process(pid)
                            pname = proc.name()
                            self._pid_name_cache[pid] = pname
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pname = "unknown"

                proto = "tcp" if conn.type == 1 else ("udp" if conn.type == 2 else "other")
                listening_ports.append({
                    "port": conn.laddr.port,
                    "address": conn.laddr.ip,
                    "proto": proto,
                    "pid": pid,
                    "process": pname,
                })

        # Evict terminated PIDs from cache periodically
        if len(self._pid_name_cache) > 200:
            self._pid_name_cache = {pid: name for pid, name in self._pid_name_cache.items() if pid in active_pids}

        # Sort listening ports by port number
        listening_ports.sort(key=lambda x: x["port"])

        return {
            "connections_count": conn_counts,
            "listening_ports": listening_ports,
        }

    def collect_snapshot(self) -> Dict[str, Any]:
        """
        Collect a full telemetry snapshot across CPU, Memory, Disk, and Network.
        Runs in < 2ms without subprocess calls.
        """
        now = time.time()
        dt = max(now - self._last_time, 0.001)
        self._last_time = now

        # --- 1. CPU ---
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        overall_cpu = round(sum(per_core) / len(per_core), 1) if per_core else 0.0

        try:
            loadavg = [round(x, 2) for x in os.getloadavg()]
        except (AttributeError, OSError):
            loadavg = [0.0, 0.0, 0.0]

        cpu_psi = self._read_psi("cpu")
        cpu_psi_some = cpu_psi.get("some", {"avg10": 0.0, "avg60": 0.0, "avg300": 0.0, "total": 0})

        # --- 2. Memory & Swap ---
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        mem_psi = self._read_psi("memory")

        curr_vmstat = self._read_vmstat()
        minor_faults_sec = 0.0
        major_faults_sec = 0.0
        if self._last_vmstat and curr_vmstat:
            minor_faults_sec = max(0.0, (curr_vmstat.get("pgfault", 0) - self._last_vmstat.get("pgfault", 0)) / dt)
            major_faults_sec = max(0.0, (curr_vmstat.get("pgmajfault", 0) - self._last_vmstat.get("pgmajfault", 0)) / dt)
        self._last_vmstat = curr_vmstat

        # --- 3. Disk I/O ---
        curr_disk_io = psutil.disk_io_counters()
        read_mbs = 0.0
        write_mbs = 0.0
        read_iops = 0.0
        write_iops = 0.0

        if self._last_disk_io and curr_disk_io:
            read_mbs = max(0.0, (curr_disk_io.read_bytes - self._last_disk_io.read_bytes) / dt / (1024 * 1024))
            write_mbs = max(0.0, (curr_disk_io.write_bytes - self._last_disk_io.write_bytes) / dt / (1024 * 1024))
            read_iops = max(0.0, (curr_disk_io.read_count - self._last_disk_io.read_count) / dt)
            write_iops = max(0.0, (curr_disk_io.write_count - self._last_disk_io.write_count) / dt)
        self._last_disk_io = curr_disk_io

        disk_psi = self._read_psi("io")
        partitions = self._get_partitions()

        # --- 4. Network ---
        curr_net_io = psutil.net_io_counters()
        rx_kbs = 0.0
        tx_kbs = 0.0
        packets_rx_sec = 0.0
        packets_tx_sec = 0.0

        if self._last_net_io and curr_net_io:
            rx_kbs = max(0.0, (curr_net_io.bytes_recv - self._last_net_io.bytes_recv) / dt / 1024)
            tx_kbs = max(0.0, (curr_net_io.bytes_sent - self._last_net_io.bytes_sent) / dt / 1024)
            packets_rx_sec = max(0.0, (curr_net_io.packets_recv - self._last_net_io.packets_recv) / dt)
            packets_tx_sec = max(0.0, (curr_net_io.packets_sent - self._last_net_io.packets_sent) / dt)
        self._last_net_io = curr_net_io

        net_conns = self._get_network_connections_and_ports()

        return {
            "timestamp": round(now, 3),
            "cpu": {
                "overall": overall_cpu,
                "cores": per_core,
                "loadavg": loadavg,
                "psi_some": cpu_psi_some,
            },
            "memory": {
                "total": mem.total,
                "used": mem.used,
                "free": mem.free,
                "available": getattr(mem, "available", mem.free),
                "buffers": getattr(mem, "buffers", 0),
                "cached": getattr(mem, "cached", 0),
                "percent": mem.percent,
                "swap_total": swap.total,
                "swap_used": swap.used,
                "swap_free": swap.free,
                "swap_percent": swap.percent,
                "psi_some": mem_psi.get("some", {}),
                "psi_full": mem_psi.get("full", {}),
                "page_faults_minor_sec": round(minor_faults_sec, 1),
                "page_faults_major_sec": round(major_faults_sec, 1),
            },
            "disk": {
                "read_mbs": round(read_mbs, 2),
                "write_mbs": round(write_mbs, 2),
                "read_iops": round(read_iops, 1),
                "write_iops": round(write_iops, 1),
                "psi_some": disk_psi.get("some", {}),
                "psi_full": disk_psi.get("full", {}),
                "partitions": partitions,
            },
            "network": {
                "rx_kbs": round(rx_kbs, 2),
                "tx_kbs": round(tx_kbs, 2),
                "packets_rx_sec": round(packets_rx_sec, 1),
                "packets_tx_sec": round(packets_tx_sec, 1),
                "connections_count": net_conns["connections_count"],
                "listening_ports": net_conns["listening_ports"],
            },
        }
