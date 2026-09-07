"""线程安全的 TTL 内存缓存（MVP 用；多进程部署可换 Redis）。"""

from __future__ import annotations

import json
import threading
import time
from typing import Any


def cache_key(*parts: Any) -> str:
    return json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)


class TTLCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, float, Any]] = {}  # key -> (expire_at, created_at, value)

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expire_at, _, value = entry
            if expire_at <= now:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, *, ttl: float) -> None:
        now = time.monotonic()
        with self._lock:
            self._store[key] = (now + ttl, now, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
