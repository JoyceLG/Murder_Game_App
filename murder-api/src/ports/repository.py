"""Driven port: persistence of the Game aggregate (in-memory and Postgres adapters)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import Game


@runtime_checkable
class GameRepository(Protocol):
    async def get(self, code: str) -> Game | None: ...
    async def save(self, game: Game) -> None: ...
    async def delete(self, code: str) -> None: ...
    async def exists(self, code: str) -> bool: ...
