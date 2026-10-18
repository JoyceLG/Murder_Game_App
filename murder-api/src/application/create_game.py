"""Use case: create a new game. The host becomes the first player; identity is server-minted."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import digest_secret
from src.domain.errors import CodeSpaceExhausted
from src.domain.models import Game, GameStatus, Player
from src.ports.clock import Clock
from src.ports.identifiers import CodeGenerator, IdGenerator, SecretGenerator
from src.ports.repository import GameRepository


@dataclass
class CreateGame:
    repo: GameRepository
    ids: IdGenerator
    codes: CodeGenerator
    clock: Clock
    secrets: SecretGenerator

    async def execute(self, host_name: str) -> tuple[Game, str, str]:
        """Return the game, the host's public id and the host's session secret."""
        code = await self._unique_code()
        host_id = self.ids.new_id()
        secret = self.secrets.new_secret()
        now = self.clock.now_ms()
        game = Game(code=code, host_id=host_id, status=GameStatus.LOBBY, created_at=now)
        game.players[host_id] = Player(
            id=host_id, name=host_name, joined_at=now, token_hash=digest_secret(secret)
        )
        await self.repo.save(game)
        return game, host_id, secret

    async def _unique_code(self) -> str:
        for _ in range(10):
            code = self.codes.new_code()
            if not await self.repo.exists(code):
                return code
        raise CodeSpaceExhausted()
