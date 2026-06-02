"""Use case: read the current game state, settling a time-expired running game to ENDED."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.models import Game
from src.ports.clock import Clock
from src.ports.repository import GameRepository


@dataclass
class GetGame:
    repo: GameRepository
    clock: Clock

    async def execute(self, code: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        if settle_end(game, self.clock):
            await self.repo.save(game)
        return game
