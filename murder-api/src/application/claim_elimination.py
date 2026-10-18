"""Use case: an attacker opens a claim that they eliminated their target (awaiting confirmation)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.errors import GameNotRunning
from src.domain.models import Claim, GameStatus
from src.domain.rules import open_claim
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class ClaimElimination:
    repo: GameRepository
    clock: Clock
    notifier: RealtimeNotifier

    async def execute(self, code: str, attacker_id: str) -> Claim:
        game = await get_game_or_404(self.repo, code)
        settle_end(game, self.clock)
        if game.status is not GameStatus.RUNNING:
            raise GameNotRunning(code)
        claim = open_claim(game, attacker_id, self.clock.now_ms())
        await self.repo.save(game)
        await self.notifier.publish(game)
        return claim
