"""Login throttling: too many failed logins inside a sliding window -> wait before trying again.

In-memory and per-process. That is correct for how this app runs (one uvicorn worker).
With several workers or servers each would count separately, so move the counts to a
shared store (Redis, or a login_attempts table) before scaling out.
"""
import math
import threading
import time
from collections import defaultdict, deque


class LoginLimiter:
    def __init__(self, window_seconds: int, clock=time.monotonic):
        self.window = window_seconds
        self.clock = clock  # tests swap this to move time forward without sleeping
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._failures[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        return q

    def retry_after(self, key: str, limit: int) -> int:
        """Seconds until `key` may try again; 0 means allowed now."""
        with self._lock:
            now = self.clock()
            q = self._prune(key, now)
            if len(q) < limit:
                return 0
            # Allowed again once the oldest failure that keeps us at the limit slides out.
            return max(1, math.ceil(q[-limit] + self.window - now))

    def record_failure(self, *keys: str) -> None:
        with self._lock:
            now = self.clock()
            for key in keys:
                self._prune(key, now).append(now)

    def reset(self, *keys: str) -> None:
        """Forget failures for these keys, or for everyone when called with no keys."""
        with self._lock:
            if not keys:
                self._failures.clear()
            for key in keys:
                self._failures.pop(key, None)
