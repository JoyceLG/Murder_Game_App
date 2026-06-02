"""Use case: a player swaps their current mission for a -1 score penalty."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.errors import GameNotRunning
from src.domain.models import Game, GameStatus
from src.domain.randomness import Picker
from src.domain.rules import swap_mission
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class SwapMission:
    repo: GameRepository
    clock: Clock
    picker: Picker
    notifier: RealtimeNotifier

    async def execute(self, code: str, player_id: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        settle_end(game, self.clock)
        if game.status is not GameStatus.RUNNING:
            raise GameNotRunning(code)
        swap_mission(game, player_id, self.picker)  # raises PlayerNotFound if absent
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
