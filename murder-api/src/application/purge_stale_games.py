"""Use case: delete games older than a time-to-live and disconnect anyone still watching them.

Housekeeping only (no game rule depends on it): without it, finished and abandoned games would
accumulate forever in the database and in the notifier's rooms.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class PurgeStaleGames:
    repo: GameRepository
    clock: Clock
    notifier: RealtimeNotifier
    ttl_ms: int

    async def execute(self) -> list[str]:
        purged = await self.repo.delete_created_before(self.clock.now_ms() - self.ttl_ms)
        for code in purged:
            await self.notifier.close(code)
        return purged
