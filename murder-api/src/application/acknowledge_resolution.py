"""Use case: the ATTACKER acknowledges the target's answer and moves on to their next mission.

After a confirmation the attacker has already scored; acknowledging deals a new target and a new
mission. After a refusal it deals a new mission only. Either way the claim is consumed. Splitting
this from ConfirmClaim lets the attacker see the result before anything else changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.errors import GameNotRunning, NotTheClaimAttacker
from src.domain.models import Game, GameStatus
from src.domain.randomness import Picker
from src.domain.rules import advance_after_resolution
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class AcknowledgeResolution:
    repo: GameRepository
    clock: Clock
    picker: Picker
    notifier: RealtimeNotifier

    async def execute(self, code: str, attacker_id: str, caller_id: str) -> Game:
        if caller_id != attacker_id:
            raise NotTheClaimAttacker()
        game = await get_game_or_404(self.repo, code)
        if settle_end(game, self.clock):  # the end acknowledges every claim by itself
            await self.repo.save(game)
            await self.notifier.publish(game)
        if game.status is not GameStatus.RUNNING:
            raise GameNotRunning(code)
        advance_after_resolution(game, attacker_id, self.picker)  # ClaimNotFound / NotResolved
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
