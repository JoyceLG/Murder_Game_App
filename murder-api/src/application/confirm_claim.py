"""Use case: the TARGET confirms or denies a claim — the server-side authoritative resolution.

This is the centerpiece of the migration: in legacy-js the attacker's own browser resolved its
claim ("client-side scoring trust"). Here only the claim's target may confirm/deny, and the
scoring/reassignment happens on the server.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.errors import ClaimNotFound, GameNotRunning, NotTheClaimTarget
from src.domain.models import Game, GameStatus
from src.domain.randomness import Picker
from src.domain.rules import resolve_claim
from src.ports.clock import Clock
from src.ports.notifier import RealtimeNotifier
from src.ports.repository import GameRepository


@dataclass
class ConfirmClaim:
    repo: GameRepository
    clock: Clock
    picker: Picker
    notifier: RealtimeNotifier

    async def execute(
        self, code: str, attacker_id: str, confirmer_id: str, confirmed: bool
    ) -> Game:
        game = await get_game_or_404(self.repo, code)
        # A claim must not score a game that has already ended/expired (consistent with the
        # ClaimElimination / SwapMission guards). The lazy auto-end runs first.
        settle_end(game, self.clock)
        if game.status is not GameStatus.RUNNING:
            raise GameNotRunning(code)
        claim = game.claims.get(attacker_id)
        if claim is None:
            raise ClaimNotFound(attacker_id)
        if claim.target != confirmer_id:
            raise NotTheClaimTarget()

        resolve_claim(game, attacker_id, confirmed, self.picker)
        # A confirmed claim may have pushed the attacker to the score cap — end the game now so
        # the published state already reflects ENDED (lazy end, evaluated after scoring).
        settle_end(game, self.clock)
        await self.repo.save(game)
        await self.notifier.publish(game)
        return game
