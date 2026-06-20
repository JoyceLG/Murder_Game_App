"""Use case: a player adds a custom mission to the game's pool (lobby only).

Any player in the lobby may contribute; the mission is tagged with the contributor's id so the
author (or the host) can later remove it.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404
from src.domain.errors import GameAlreadyStarted, InvalidMission, PlayerNotFound
from src.domain.models import Game, GameStatus, PooledMission
from src.ports.identifiers import IdGenerator
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository

MAX_MISSION_LEN = 200
MAX_POOL_SIZE = 100


@dataclass
class AddMissionToPool:
    repo: GameRepository
    ids: IdGenerator
    notifier: RealtimeNotifier

    async def execute(self, code: str, player_id: str, text: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        if game.status is not GameStatus.LOBBY:
            raise GameAlreadyStarted(code)
        if player_id not in game.players:
            raise PlayerNotFound(player_id)
        cleaned = text.strip()
        if not cleaned or len(cleaned) > MAX_MISSION_LEN:
            raise InvalidMission()
        if len(game.mission_pool) >= MAX_POOL_SIZE:
            raise InvalidMission()

        game.mission_pool.append(PooledMission(id=self.ids.new_id(), text=cleaned, by=player_id))
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
