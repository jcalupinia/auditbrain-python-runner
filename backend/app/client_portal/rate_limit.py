"""Rate limiter en memoria (suficiente para MVP single-instance Render)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = Lock()


def check_and_record(key: str, *, max_hits: int, window_seconds: int) -> bool:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        bucket = _WINDOWS[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_hits:
            return False
        bucket.append(now)
        return True


def reset_for_key(key: str) -> None:
    with _LOCK:
        _WINDOWS.pop(key, None)
