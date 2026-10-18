"""Use case: the host ends a running game early. (Time-based ending is handled lazily on read.)"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.errors import GameNotRunning, NotTheHost
from src.domain.models import Game, GameStatus
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class EndGame:
    repo: GameRepository
    clock: Clock
    notifier: RealtimeNotifier

    async def execute(self, code: str, host_id: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        if game.host_id != host_id:
            raise NotTheHost()
        # Only a running game can be ended: not one still in the lobby, nor one already over
        # (which would re-broadcast a finished game for nothing).
        settle_end(game, self.clock)
        if game.status is not GameStatus.RUNNING:
            raise GameNotRunning(code)
        game.status = GameStatus.ENDED
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
