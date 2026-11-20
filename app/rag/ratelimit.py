"""Small in-process sliding-window limiter for the chat endpoint.

One process only. A real deployment behind more than one worker needs Redis (or
the gateway's limiter); this is deliberately simple so the demo cannot be
hammered by a single session.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindow:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = max(1, int(limit))
        self.window = float(window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        stamp = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            cutoff = stamp - self.window
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(stamp)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class ChatLimiter:
    def __init__(self, per_minute: int, per_hour: int):
        self.minute = SlidingWindow(per_minute, 60)
        self.hour = SlidingWindow(per_hour, 3600)

    def allow(self, key: str, now: float | None = None) -> bool:
        # Check both before recording, so a rejected hour does not consume a
        # minute slot and a rejected minute does not consume an hour slot.
        stamp = time.monotonic() if now is None else now
        if not self._peek(self.minute, key, stamp) or not self._peek(self.hour, key, stamp):
            return False
        self.minute.allow(key, stamp)
        self.hour.allow(key, stamp)
        return True

    @staticmethod
    def _peek(window: SlidingWindow, key: str, now: float) -> bool:
        with window._lock:
            q = window._hits[key]
            cutoff = now - window.window
            while q and q[0] <= cutoff:
                q.popleft()
            return len(q) < window.limit

    def reset(self) -> None:
        self.minute.reset()
        self.hour.reset()
