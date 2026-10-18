"""Per-client request budgets (token buckets), kept in process memory like the WebSocket rooms.

Used for abuse control: a flood of game creations, and enumeration of the short game codes
(4 characters ≈ 1M combinations), which `lookup_miss_limit_per_minute` makes impractical.
Single-worker, like the rest of the realtime layer; a multi-worker deployment would move this
to the reverse proxy or a shared store.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from starlette.requests import HTTPConnection


def client_key(connection: HTTPConnection) -> str:
    """The caller's address (uvicorn resolves X-Forwarded-For from trusted proxies)."""
    return connection.client.host if connection.client else "unknown"


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """Token bucket per key: `per_minute` tokens, refilled continuously. 0 means unlimited."""

    def __init__(self, per_minute: int, now: Callable[[], float] = time.monotonic) -> None:
        self._capacity = float(per_minute)
        self._refill_per_sec = per_minute / 60.0
        self._now = now
        self._buckets: dict[str, _Bucket] = {}

    MAX_TRACKED_CLIENTS = 10_000

    def _level(self, bucket: _Bucket, now: float) -> float:
        return min(self._capacity, bucket.tokens + (now - bucket.updated) * self._refill_per_sec)

    def _bucket(self, key: str) -> _Bucket:
        now = self._now()
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self.MAX_TRACKED_CLIENTS:
                # Forget clients whose bucket has refilled: they are idle, and a fresh full
                # bucket is exactly what they would get back. Keeps memory bounded.
                self._buckets = {
                    k: b for k, b in self._buckets.items() if self._level(b, now) < self._capacity
                }
            bucket = self._buckets[key] = _Bucket(tokens=self._capacity, updated=now)
        else:
            bucket.tokens = self._level(bucket, now)
            bucket.updated = now
        return bucket

    def allow(self, key: str) -> bool:
        """Spend one token if available."""
        if self._capacity <= 0:
            return True
        bucket = self._bucket(key)
        if bucket.tokens < 1:
            return False
        bucket.tokens -= 1
        return True

    def exhausted(self, key: str) -> bool:
        """True when the key has no token left (without spending one)."""
        return self._capacity > 0 and self._bucket(key).tokens < 1

    def hit(self, key: str) -> None:
        """Spend a token if one is left (used to count failures after the fact)."""
        self.allow(key)
