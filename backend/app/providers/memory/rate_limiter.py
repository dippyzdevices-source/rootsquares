"""In-process sliding-window rate limiter behind the RateLimiter interface. Per instance only: with several app instances use Cloudflare
edge rules or a shared store (docs/reference/architecture.md section 9)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True
