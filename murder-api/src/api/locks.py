"""One asyncio.Lock per game code, so concurrent requests on a game run one at a time.

Every use case is load -> mutate -> save with awaits in between; without this, two requests on
the same game interleave and one of them hits the repository's optimistic-lock guard (409).
The lock makes that the exception rather than the rule. It only spans this process, which is
fine because the app runs a single worker (see CLAUDE.md); across processes the repository's
version check still guarantees no update is lost.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class GameLocks:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._users: dict[str, int] = {}

    @asynccontextmanager
    async def hold(self, code: str) -> AsyncIterator[None]:
        lock = self._locks.setdefault(code, asyncio.Lock())
        self._users[code] = self._users.get(code, 0) + 1
        try:
            async with lock:
                yield
        finally:
            self._users[code] -= 1
            if self._users[code] == 0:  # nobody holds or waits: drop it so the map stays small
                del self._users[code]
                del self._locks[code]

    def __len__(self) -> int:
        return len(self._locks)
