"""Use case: an attacker opens a claim that they eliminated their target (awaiting confirmation)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application._support import get_game_or_404, settle_end
from src.domain.errors import GameNotRunning, NoTargetAssigned, PlayerNotFound
from src.domain.models import Claim, ClaimStatus, GameStatus
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
        attacker = game.players.get(attacker_id)
        if attacker is None:
            raise PlayerNotFound(attacker_id)
        if not attacker.target_id:
            raise NoTargetAssigned()

        claim = Claim(
            atk=attacker_id,
            atk_name=attacker.name,
            target=attacker.target_id,
            mission=attacker.mission,
            status=ClaimStatus.PENDING,
            ts=self.clock.now_ms(),
        )
        game.claims[attacker_id] = claim  # one active claim per attacker (overwrites any prior)
        await self.repo.save(game)
        await self.notifier.publish(game)
        return claim
