"""Use case: the host starts the game — assigns targets/missions and starts the clock."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404
from src.domain.errors import GameAlreadyStarted, NotEnoughPlayers, NotTheHost
from src.domain.models import Game, GameStatus
from src.domain.randomness import Picker
from src.domain.rules import assign_targets, clamp_duration_min
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class StartGame:
    repo: GameRepository
    clock: Clock
    picker: Picker
    notifier: RealtimeNotifier

    async def execute(self, code: str, host_id: str, duration_min: int) -> Game:
        game = await get_game_or_404(self.repo, code)
        if game.host_id != host_id:
            raise NotTheHost()
        if game.status is not GameStatus.LOBBY:
            raise GameAlreadyStarted(code)
        if len(game.players) < 2:
            raise NotEnoughPlayers()

        assign_targets(game, self.picker)
        duration_sec = clamp_duration_min(duration_min) * 60
        now = self.clock.now_ms()
        game.status = GameStatus.RUNNING
        game.duration_sec = duration_sec
        game.start_at = now
        game.end_at = now + duration_sec * 1000

        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
