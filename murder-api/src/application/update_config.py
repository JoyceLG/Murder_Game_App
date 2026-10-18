"""Use case: the host configures the game while it is still in the lobby.

Sets the player cap and the optional score cap (the score a player must reach to win). Broadcast
so every player in the lobby sees the rules live. Duration is still chosen at start time.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404
from src.domain.errors import GameAlreadyStarted, NotTheHost
from src.domain.models import Game, GameStatus, MissionMode
from src.domain.rules import configure_game
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class UpdateGameConfig:
    repo: GameRepository
    notifier: RealtimeNotifier

    async def execute(
        self,
        code: str,
        host_id: str,
        max_players: int,
        max_score: int | None,
        mission_mode: MissionMode,
    ) -> Game:
        game = await get_game_or_404(self.repo, code)
        if game.host_id != host_id:
            raise NotTheHost()
        if game.status is not GameStatus.LOBBY:
            raise GameAlreadyStarted(code)
        configure_game(game, max_players, max_score, mission_mode)  # InvalidGameConfig
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
