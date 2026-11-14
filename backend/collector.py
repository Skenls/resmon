import os
import platform
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
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


_TCP_STATE_NAMES = {
    "01": "ESTABLISHED",
    "02": "SYN_SENT",
    "03": "SYN_RECV",
    "04": "FIN_WAIT1",
    "05": "FIN_WAIT2",
    "06": "TIME_WAIT",
    "07": "CLOSE",
    "08": "CLOSE_WAIT",
    "09": "LAST_ACK",
    "0A": "LISTEN",
    "0B": "CLOSING",
}


def _decode_proc_net_address(value: str) -> Tuple[str, int]:
    address_hex, port_hex = value.split(":")
    raw = bytes.fromhex(address_hex)
    if len(raw) == 4:
        address = socket.inet_ntop(socket.AF_INET, raw[::-1])
    else:
        address = socket.inet_ntop(
            socket.AF_INET6,
            b"".join(raw[offset : offset + 4][::-1] for offset in range(0, 16, 4)),
        )
    return address, int(port_hex, 16)


def parse_proc_net_tables(
    proc_root: str,
) -> Optional[Tuple[List[Dict[str, Any]], Dict[str, int]]]:
    """Read sockets from the host network namespace via /proc/1/net."""
    net_root = os.path.join(proc_root, "1", "net")
    listening: List[Dict[str, Any]] = []
    counts = {
        name: 0
        for name in (
            "ESTABLISHED",
            "SYN_SENT",
            "SYN_RECV",
            "FIN_WAIT1",
            "FIN_WAIT2",
            "TIME_WAIT",
            "CLOSE",
            "CLOSE_WAIT",
            "LAST_ACK",
            "LISTEN",
            "CLOSING",
            "OTHER",
        )
    }
    found = False
    for table in ("tcp", "tcp6", "udp", "udp6"):
        try:
            with open(os.path.join(net_root, table), "r", encoding="utf-8") as handle:
                next(handle, None)
                for line in handle:
                    fields = line.split()
                    if len(fields) < 10:
                        continue
                    found = True
                    proto = table.rstrip("6")
                    state = fields[3]
                    if proto == "tcp":
                        counts[_TCP_STATE_NAMES.get(state, "OTHER")] += 1
                    else:
                        counts["OTHER"] += 1
                    is_listener = (proto == "tcp" and state == "0A") or (
                        proto == "udp" and state == "07"
                    )
                    if not is_listener:
                        continue
                    try:
                        address, port = _decode_proc_net_address(fields[1])
                    except (ValueError, OSError):
                        continue
                    listening.append(
                        {
                            "port": port,
                            "address": address,
                            "proto": proto,
                            "family": "IPv6" if "6" in table else "IPv4",
                            "status": "LISTEN" if proto == "tcp" else "UNCONN",
                            "_inode": fields[9],
                        }
                    )
        except OSError:
            continue
    if not found:
        return None
    return listening, counts


def parse_ufw_rules(ufw_dir: str) -> Dict[str, Any]:
    """Parse read-only UFW configuration. Only allow/limit tuples are returned."""
    result: Dict[str, Any] = {"available": False, "enabled": False, "rules": []}
    try:
        with open(os.path.join(ufw_dir, "ufw.conf"), "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip().startswith("ENABLED="):
                    result["enabled"] = line.split("=", 1)[1].strip().lower() in (
                        "yes",
                        "true",
                        "1",
                    )
                    break
    except OSError:
        pass

    rules: List[Dict[str, str]] = []
    seen = set()
    for filename in ("user.rules", "user6.rules"):
        try:
            with open(os.path.join(ufw_dir, filename), "r", encoding="utf-8") as handle:
                content = handle.read()
        except OSError:
            continue
        result["available"] = True
        for line in content.splitlines():
            if not line.startswith("### tuple ###"):
                continue
            parts = line.split()
            if len(parts) < 10:
                continue
            action, proto, port, to_addr, _sport, from_addr, direction = parts[3:10]
            if action.lower() not in ("allow", "limit"):
                continue
            key = (action, proto, port, from_addr, to_addr, direction)
            if key in seen:
                continue
            seen.add(key)
            rules.append(
                {
                    "action": action,
                    "proto": proto,
                    "port": port,
                    "from": from_addr,
                    "to": to_addr,
                    "direction": direction,
                }
            )
    rules.sort(
        key=lambda rule: (
            int(rule["port"].split(":")[0])
            if rule["port"].split(":")[0].isdigit()
            else 65536,
            rule["proto"],
            rule["port"],
        )
    )
    result["rules"] = rules
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

        # Point psutil to host procfs when running in container on Linux
        if os.path.isdir(self.host_proc) and hasattr(psutil, "PROCFS_PATH"):
            psutil.PROCFS_PATH = self.host_proc

        self._last_time = time.time()

        # Initialize psutil counters
        psutil.cpu_percent(interval=None, percpu=True)
        self._last_disk_io = psutil.disk_io_counters()
        self._last_net_io = psutil.net_io_counters()
        self._last_vmstat = self._read_vmstat()

        # Process name cache by PID to avoid repeated name lookup overhead
        self._pid_name_cache: Dict[int, str] = {}
        self._host_socket_owners: Dict[str, int] = {}
        self._host_socket_owners_time = 0.0
        self._ufw_cache: Optional[Dict[str, Any]] = None
        self._ufw_cache_time = 0.0

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

    def _process_name(self, pid: Optional[int]) -> str:
        if not pid:
            return "unknown"
        if pid in self._pid_name_cache:
            return self._pid_name_cache[pid]
        try:
            pname = psutil.Process(pid).name()
            self._pid_name_cache[pid] = pname
            return pname
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return "unknown"

    def _host_socket_owner_map(self) -> Dict[str, int]:
        """Map socket inodes to host PIDs; cached because fd scans are expensive."""
        now = time.monotonic()
        if self._host_socket_owners and now - self._host_socket_owners_time < 10:
            return self._host_socket_owners

        owners: Dict[str, int] = {}
        try:
            proc_entries = os.scandir(self.host_proc)
        except OSError:
            return {}
        with proc_entries:
            for entry in proc_entries:
                if not entry.name.isdigit():
                    continue
                try:
                    fd_entries = os.scandir(os.path.join(entry.path, "fd"))
                except OSError:
                    continue
                with fd_entries:
                    for fd in fd_entries:
                        try:
                            target = os.readlink(fd.path)
                        except OSError:
                            continue
                        if target.startswith("socket:["):
                            owners[target[8:-1]] = int(entry.name)

        self._host_socket_owners = owners
        self._host_socket_owners_time = now
        return owners

    def _get_ufw(self) -> Dict[str, Any]:
        now = time.monotonic()
        if self._ufw_cache is None or now - self._ufw_cache_time > 5:
            self._ufw_cache = parse_ufw_rules(self.settings.HOST_UFW)
            self._ufw_cache_time = now
        return self._ufw_cache

    def _get_network_connections_and_ports(self) -> Dict[str, Any]:
        """Collect host-wide connections/ports from the host netns when available."""
        host_tables = parse_proc_net_tables(self.host_proc)
        if host_tables is not None:
            listening_ports, conn_counts = host_tables
            owners = self._host_socket_owner_map() if listening_ports else {}
            for port in listening_ports:
                pid = owners.get(port.pop("_inode", ""))
                port["pid"] = pid
                port["process"] = self._process_name(pid)
            listening_ports.sort(key=lambda x: (x["port"], x["proto"]))
            return {
                "connections_count": conn_counts,
                "listening_ports": listening_ports,
                "ufw": self._get_ufw(),
            }

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
                pname = self._process_name(pid)
                if pid:
                    active_pids.add(pid)

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

        listening_ports.sort(key=lambda x: x["port"])

        return {
            "connections_count": conn_counts,
            "listening_ports": listening_ports,
            "ufw": self._get_ufw(),
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
                "ufw": net_conns["ufw"],
            },
        }
