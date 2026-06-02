"""Use case: a player leaves. Cleans up their claim and any claim targeting them.

If no players remain, the game is deleted (a watcher then sees it as gone). If the host leaves
but others remain, the host role passes to the next player so the game is never hostless.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404
from src.domain.models import Game
from src.domain.randomness import Picker
from src.domain.rules import reassign_targets_away_from
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class LeaveGame:
    repo: GameRepository
    picker: Picker
    notifier: RealtimeNotifier

    async def execute(self, code: str, player_id: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        game.players.pop(player_id, None)
        game.claims.pop(player_id, None)
        for attacker_id, claim in list(game.claims.items()):
            if claim.target == player_id:
                game.claims.pop(attacker_id, None)

        if not game.players:
            await self.repo.delete(code)
            return game

        # Hunters who were targeting the leaver must not keep a dangling target_id.
        reassign_targets_away_from(game, player_id, self.picker)

        if game.host_id == player_id:
            game.host_id = next(iter(game.players))

        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
