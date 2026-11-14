"""Read-only MCP tools for the monitoring data and host logs."""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from backend.buffer import MetricsBuffer
from backend.config import Settings

MAX_METRICS_AGE_SECONDS = 300
MAX_SERIES_POINTS = 60


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _parse_time(value: str, name: str) -> float:
    try:
        return float(value)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO 8601 or Unix seconds") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _downsample(points: List[Dict[str, Any]], limit: int) -> Tuple[List[Dict[str, Any]], bool]:
    if len(points) <= limit:
        return points, False
    step = (len(points) - 1) / (limit - 1)
    indexes = sorted({round(i * step) for i in range(limit)})
    return [points[i] for i in indexes], True


def _journal_dirs(settings: Settings) -> List[str]:
    return [
        directory
        for directory in (settings.HOST_JOURNAL_DIR, settings.HOST_RUN_JOURNAL_DIR)
        if os.path.isdir(directory)
    ]


def _journal_file_count(directory: str) -> int:
    return sum(
        1
        for _, _, files in os.walk(directory)
        for name in files
        if name.endswith((".journal", ".journal~"))
    )


def _journal_root(settings: Settings) -> Optional[str]:
    """journalctl accepts only one --directory; a common root reads both paths."""
    journal_dir = settings.HOST_JOURNAL_DIR.rstrip("/")
    run_dir = settings.HOST_RUN_JOURNAL_DIR.rstrip("/")
    if not journal_dir.endswith("/var/log/journal") or not run_dir.endswith("/run/log/journal"):
        return None
    journal_root = journal_dir[: -len("/var/log/journal")]
    run_root = run_dir[: -len("/run/log/journal")]
    if journal_root != run_root:
        return None
    return journal_root or "/"


def _journal_command(settings: Settings, lines: int, unit: Optional[str]) -> List[str]:
    command = [
        "journalctl",
        "--no-pager",
        "--output=short-iso",
        "--lines",
        str(lines),
    ]
    root = _journal_root(settings)
    if root and root != "/":
        command.extend(["--root", root])
    else:
        dirs = _journal_dirs(settings)
        if dirs:
            command.extend(["--directory", max(dirs, key=_journal_file_count)])
    if unit:
        command.extend(["--unit", unit])
    return command


def create_mcp(buffer: MetricsBuffer, settings: Settings):
    mcp = MCPServer(
        "resmon",
        version="1.0.0",
        instructions=(
            "Read-only access to the server monitoring data. Metrics are kept for "
            "at most 5 minutes. Logs come from the host journal (system, systemd "
            "units, and the docker.service daemon); container stdout logs are not "
            "available."
        ),
    )

    @mcp.tool()
    def get_metrics(start: str, end: str) -> Dict[str, Any]:
        """Return server metrics for a required time interval.

        Both start and end are mandatory. Use ISO 8601 with timezone (for example
        2026-11-14T10:00:00Z) or Unix seconds. The oldest available point is 5
        minutes in the past; older ranges are clamped. At most 60 points are
        returned, evenly sampled over the interval.
        """
        now = time.time()
        requested_start = _parse_time(start, "start")
        requested_end = _parse_time(end, "end")
        if requested_end < requested_start:
            raise ValueError("end must be greater than or equal to start")

        oldest = now - MAX_METRICS_AGE_SECONDS
        if requested_end < oldest:
            raise ValueError("metrics are retained for only 5 minutes; end is too old")

        start_ts = max(requested_start, oldest)
        end_ts = min(requested_end, now)
        if start_ts > end_ts:
            raise ValueError("the requested interval has no available metrics")

        history = buffer.get_history()
        matched = [
            point
            for point in history
            if start_ts <= float(point.get("timestamp", 0)) <= end_ts
        ]
        series, downsampled = _downsample(matched, MAX_SERIES_POINTS)

        return {
            "now": _iso(now),
            "requested": {"start": _iso(requested_start), "end": _iso(requested_end)},
            "effective": {"start": _iso(start_ts), "end": _iso(end_ts)},
            "clamped": start_ts != requested_start or end_ts != requested_end,
            "oldest_available": _iso(oldest),
            "matched_points": len(matched),
            "returned_points": len(series),
            "downsampled": downsampled,
            "series": series,
        }

    @mcp.tool()
    def get_logs(
        source: Literal["system", "systemd", "docker"],
        unit: Optional[str] = None,
        lines: int = 100,
    ) -> Dict[str, Any]:
        """Return recent host logs from journald.

        source="system" returns the system journal, source="systemd" returns one
        unit (pass unit, for example "nginx" or "ssh"), and source="docker"
        returns the docker.service daemon log. Container stdout logs are not
        available without the Docker socket. lines is clamped to 1..1000.
        """
        if not 1 <= lines <= 1000:
            raise ValueError("lines must be between 1 and 1000")

        if source == "systemd" and not unit:
            raise ValueError("unit is required for source=systemd")
        target_unit = unit if source == "systemd" else "docker.service" if source == "docker" else None

        command = _journal_command(settings, lines, target_unit)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except FileNotFoundError:
            return {
                "source": source,
                "unit": target_unit,
                "returned_lines": 0,
                "lines": [],
                "error": "journalctl is not installed",
            }
        except subprocess.TimeoutExpired:
            return {
                "source": source,
                "unit": target_unit,
                "returned_lines": 0,
                "lines": [],
                "error": "journalctl timed out",
            }

        entries = completed.stdout.rstrip("\n").splitlines()
        if entries == ["-- No entries --"]:
            entries = []
        result: Dict[str, Any] = {
            "source": source,
            "unit": target_unit,
            "returned_lines": len(entries),
            "lines": entries,
        }
        if not entries:
            dirs = _journal_dirs(settings)
            journal_files = sum(_journal_file_count(directory) for directory in dirs)
            result["journal_root"] = _journal_root(settings)
            result["journal_dirs"] = dirs
            result["journal_files"] = journal_files
            if not dirs:
                result["hint"] = (
                    "Host journal is not mounted. Mount /var/log/journal at "
                    f"{settings.HOST_JOURNAL_DIR} and /run/log/journal at "
                    f"{settings.HOST_RUN_JOURNAL_DIR}, then recreate the container."
                )
            elif journal_files == 0:
                result["hint"] = (
                    "The mounted journal directories contain no .journal files. "
                    "The host may use a different journal path."
                )
            else:
                result["hint"] = (
                    "Journal files exist but journalctl returned no entries; "
                    "check read permissions on the mounted directory."
                )
        if completed.returncode != 0 and completed.stderr.strip():
            result["error"] = completed.stderr.strip()[:2000]
        return result

    app = mcp.streamable_http_app(
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return mcp, app
