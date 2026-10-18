"""Use case: read the current game state, settling a time-expired running game to ENDED.

When the read is what flips the game to ENDED, the new state is also broadcast: there is no
scheduler, so this is how watchers learn that the clock ran out.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.models import Game
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class GetGame:
    repo: GameRepository
    clock: Clock
    notifier: RealtimeNotifier

    async def execute(self, code: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        if settle_end(game, self.clock):
            await self.repo.save(game)
            await self.notifier.publish(game)
        return game
