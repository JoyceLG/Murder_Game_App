"""Use case: remove a pooled mission (lobby only). Allowed for the author or the host."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404
from src.domain.errors import (
    GameAlreadyStarted,
    MissionNotFound,
    NotAllowedToRemoveMission,
)
from src.domain.models import Game, GameStatus
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class RemoveMissionFromPool:
    repo: GameRepository
    notifier: RealtimeNotifier

    async def execute(self, code: str, player_id: str, mission_id: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        if game.status is not GameStatus.LOBBY:
            raise GameAlreadyStarted(code)
        mission = next((m for m in game.mission_pool if m.id == mission_id), None)
        if mission is None:
            raise MissionNotFound(mission_id)
        if player_id != mission.by and player_id != game.host_id:
            raise NotAllowedToRemoveMission()

        game.mission_pool = [m for m in game.mission_pool if m.id != mission_id]
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
