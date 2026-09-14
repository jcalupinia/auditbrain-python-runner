"""Rate limiter en memoria (suficiente para MVP single-instance Render)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = Lock()
# Tope de claves en memoria (cada IP/correo distinto crea una).
_MAX_KEYS = 50_000
# Mayor ventana en uso (topes de correo de recursos, 1 h): una clave sin hits en
# ese lapso ya no limita nada y se puede borrar.
_STALE_SECONDS = 3600


def _barrer(now: float) -> None:
    # ponytail: barrido O(n) bajo el lock, solo al pasar _MAX_KEYS; si el tráfico
    # lo dispara seguido, pasar a un store con TTL (Redis).
    viejo = now - _STALE_SECONDS
    for k in [k for k, b in _WINDOWS.items() if not b or b[-1] < viejo]:
        del _WINDOWS[k]


def check_and_record(key: str, *, max_hits: int, window_seconds: int) -> bool:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        if len(_WINDOWS) > _MAX_KEYS:
            _barrer(now)
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
