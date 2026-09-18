from collections import deque
from typing import Any, Dict, List, Optional


class MetricsBuffer:
    """
    Fixed-size in-memory circular buffer for telemetry data points.
    Thread-safe append operations with O(1) performance and bounded memory footprint.
    """

    def __init__(self, maxlen: int = 900) -> None:
        self._buffer: deque = deque(maxlen=maxlen)

    def append(self, item: Dict[str, Any]) -> None:
        """Append a new snapshot point."""
        self._buffer.append(item)

    def get_history(self) -> List[Dict[str, Any]]:
        """Return all stored snapshots in chronological order."""
        return list(self._buffer)

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Return the most recently appended snapshot, or None if empty."""
        if not self._buffer:
            return None
        return self._buffer[-1]

    def clear(self) -> None:
        """Clear all stored data points."""
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
