"""Use case: the host ends the game early. (Time-based ending is handled lazily on read.)"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404
from src.domain.errors import NotTheHost
from src.domain.models import Game, GameStatus
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class EndGame:
    repo: GameRepository
    notifier: RealtimeNotifier

    async def execute(self, code: str, host_id: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        if game.host_id != host_id:
            raise NotTheHost()
        game.status = GameStatus.ENDED
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
