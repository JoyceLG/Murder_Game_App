"""Use case: create a new game. The host becomes the first player; identity is server-minted."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.errors import DomainError
from src.domain.models import Game, GameStatus, Player
from src.ports.clock import Clock
from src.ports.identifiers import CodeGenerator, IdGenerator
from src.ports.repository import GameRepository


@dataclass
class CreateGame:
    repo: GameRepository
    ids: IdGenerator
    codes: CodeGenerator
    clock: Clock

    async def execute(self, host_name: str) -> tuple[Game, str]:
        code = await self._unique_code()
        host_id = self.ids.new_id()
        game = Game(code=code, host_id=host_id, status=GameStatus.LOBBY)
        game.players[host_id] = Player(id=host_id, name=host_name, joined_at=self.clock.now_ms())
        await self.repo.save(game)
        return game, host_id

    async def _unique_code(self) -> str:
        for _ in range(10):
            code = self.codes.new_code()
            if not await self.repo.exists(code):
                return code
        raise DomainError("could not allocate a unique game code")
