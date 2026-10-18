"""Driven port: persistence of the Game aggregate (in-memory and Postgres adapters)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import Game


@runtime_checkable
class GameRepository(Protocol):
    async def get(self, code: str) -> Game | None: ...

    async def save(self, game: Game) -> None:
        """Persist `game` if nobody saved it since it was loaded, then bump `game.version`.

        Raises ConcurrentUpdate when the stored version differs from `game.version`.
        """
        ...

    async def delete(self, code: str) -> None: ...
    async def exists(self, code: str) -> bool: ...

    async def delete_created_before(self, cutoff_ms: int) -> list[str]:
        """Delete every game created before `cutoff_ms`; return their codes."""
        ...
