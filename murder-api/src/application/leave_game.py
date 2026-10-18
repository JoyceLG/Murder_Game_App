"""Use case: a player leaves. Cleans up their claim and any claim targeting them.

If no players remain, the game is deleted and its watchers are disconnected. If the host leaves
but others remain, the host role passes to the next player so the game is never hostless.

Once the game has ENDED, leaving changes nothing: the final ranking is a record shared by every
player, so someone heading back to the home screen must not vanish from it (nor delete the game).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.models import Game, GameStatus
from src.domain.randomness import Picker
from src.domain.rules import reassign_targets_away_from
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class LeaveGame:
    repo: GameRepository
    clock: Clock
    picker: Picker
    notifier: RealtimeNotifier

    async def execute(self, code: str, player_id: str) -> Game:
        game = await get_game_or_404(self.repo, code)
        if settle_end(game, self.clock):
            await self.repo.save(game)
            await self.notifier.publish(game)
        if game.status is GameStatus.ENDED:
            return game

        leaver = game.players.pop(player_id, None)
        game.claims.pop(player_id, None)
        for attacker_id, claim in list(game.claims.items()):
            if claim.target == player_id:
                game.claims.pop(attacker_id, None)

        if not game.players:
            await self.repo.delete(code)
            await self.notifier.close(code)
            return game

        # Hunters who were targeting the leaver must not keep a dangling target_id.
        reassign_targets_away_from(
            game, player_id, self.picker, leaver.target_id if leaver else None
        )

        if game.host_id == player_id:
            game.host_id = next(iter(game.players))

        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
