"""Use case: join an existing game while it is still in the lobby."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404
from src.domain.errors import GameAlreadyStarted
from src.domain.models import Game, GameStatus, Player
from src.ports.clock import Clock
from src.ports.identifiers import IdGenerator
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class JoinGame:
    repo: GameRepository
    ids: IdGenerator
    clock: Clock
    notifier: RealtimeNotifier

    async def execute(self, code: str, name: str) -> tuple[Game, str]:
        game = await get_game_or_404(self.repo, code)
        if game.status is not GameStatus.LOBBY:
            raise GameAlreadyStarted(code)
        player_id = self.ids.new_id()
        game.players[player_id] = Player(id=player_id, name=name, joined_at=self.clock.now_ms())
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game, player_id
