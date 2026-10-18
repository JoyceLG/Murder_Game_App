"""In-memory GameRepository adapter — the Python equivalent of legacy-js MemoryBackend.

Stores deep copies so reads return detached aggregates (like a real DB): mutating a loaded Game
without calling save() does not leak into the store. This catches "forgot to save" bugs in tests.
Saves are version-checked exactly like the SQL adapter, so stale writes fail the same way.
"""

from __future__ import annotations

import copy

from src.domain.errors import ConcurrentUpdate
from src.domain.models import Game


class InMemoryGameRepository:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}

    async def get(self, code: str) -> Game | None:
        game = self._games.get(code)
        return copy.deepcopy(game) if game is not None else None

    async def save(self, game: Game) -> None:
        stored = self._games.get(game.code)
        if game.version != (stored.version if stored is not None else 0):
            raise ConcurrentUpdate(game.code)
        game.version += 1
        self._games[game.code] = copy.deepcopy(game)

    async def delete(self, code: str) -> None:
        self._games.pop(code, None)

    async def exists(self, code: str) -> bool:
        return code in self._games

    async def delete_created_before(self, cutoff_ms: int) -> list[str]:
        stale = [code for code, game in self._games.items() if game.created_at < cutoff_ms]
        for code in stale:
            del self._games[code]
        return stale
